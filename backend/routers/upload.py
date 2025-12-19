import os
import hashlib
import mimetypes
import logging
import uuid
from io import BytesIO
from typing import Optional

from fastapi import APIRouter, File, UploadFile, HTTPException, Request, Response, Form, Depends, BackgroundTasks
from fastapi.responses import JSONResponse, StreamingResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.responses import JSONResponse, StreamingResponse
from PIL import Image

from .. import database
from .. import storage
from .. import schemas
from .. import audit
from .. import config
from ..routers.auth import get_current_user_optional

# 从 main 导入系统设置（避免循环导入，使用函数获取）
def get_debug_mode():
    try:
        from ..main import SYSTEM_SETTINGS
        return SYSTEM_SETTINGS.get("debug_mode", False)
    except ImportError:
        return False

# 设置日志记录器
logger = logging.getLogger(__name__)

router = APIRouter()

# ==================== 配置常量 (从 config.py 导入) ====================
MAX_FILE_SIZE = config.MAX_FILE_SIZE
ALLOWED_EXTENSIONS = config.ALLOWED_EXTENSIONS
CACHE_MAX_AGE = config.CACHE_MAX_AGE
MIME_TYPE_MAP = config.MIME_TYPE_MAP

# 设置模板引擎
templates = Jinja2Templates(directory="frontend")

# ==================== 工具函数 ====================

def calculate_hash(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()[:32]

def get_image_info(content: bytes) -> dict[str, int]:
    try:
        img = Image.open(BytesIO(content))
        return {"width": img.width, "height": img.height, "size": len(content)}
    except Exception:
        return {"width": 0, "height": 0, "size": len(content)}

def validate_file_upload(filename: str, content: bytes) -> None:
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=400,
            detail=f"文件过大，最大允许 {MAX_FILE_SIZE // (1024*1024)}MB"
        )
    ext = os.path.splitext(filename or '')[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"不支持的文件类型: {ext}，允许的类型: {', '.join(sorted(ALLOWED_EXTENSIONS))}"
        )

def validate_object_path(object_name: str) -> None:
    if '..' in object_name or object_name.startswith('/') or object_name.startswith('\\'):
        raise HTTPException(status_code=400, detail="非法路径")

def build_upload_response(
    filename: str,
    fhash: str,
    upload_result: dict,
    image_info: dict
) -> dict:
    display_filename = filename if filename != 'image.png' else fhash
    return {
        "success": True,
        "filename": display_filename,
        "hash": fhash,
        "url": upload_result["url"],
        "service": upload_result["service"],
        "all_results": [upload_result],
        "failed_list": [],
        "width": image_info["width"],
        "height": image_info["height"],
        "size": image_info["size"],
        "content_type": upload_result["content_type"]
    }

# ==================== Background Tasks ====================
def background_audit_task(
    content: bytes, 
    filename: str, 
    fhash: str, 
    object_name: str,
    user_id: int = None,
    device_id: str = None
) -> None:
    """后台异步审核任务"""
    try:
        logger.info(f"🔍 [BackAudit] 开始后台审核: {filename} ({fhash})")
        
        # 执行审核 (同步执行即可，因为已经在后台线程中)
        audit_res = audit.check_image_safety(content)
        
        if not audit_res["safe"]:
            logger.warning(f"🚫 [BackAudit] 发现违规: {filename} - {audit_res['reason']}")
            
            # 1. 删除 MinIO 文件
            # 从 object_name 中提取文件名 (其实 object_name 就是文件名Key)
            del_minio = storage.delete_from_minio(object_name)
            if del_minio:
                logger.info(f"🗑️ [BackAudit] MinIO 文件已清理: {object_name}")
            else:
                logger.error(f"❌ [BackAudit] MinIO 清理失败: {object_name}")
                
            # 2. 删除数据库记录
            del_db = database.delete_image_by_hash_system(fhash)
            if del_db:
                logger.info(f"🗑️ [BackAudit] DB 记录已清理: {fhash}")
            else:
                logger.error(f"❌ [BackAudit] DB 清理失败: {fhash}")
            
            # 3. [NEW] 发送通知给用户
            if user_id or device_id:
                database.create_notification(
                    user_id=user_id,
                    device_id=device_id,
                    type="moderation_reject",
                    title="图片已被系统删除",
                    message=f"您上传的图片 '{filename}' 因违规已被系统自动删除。原因：{audit_res['reason']}"
                )
                logger.info(f"📢 [BackAudit] 已发送通知: user={user_id}, device={device_id}")
                
        else:
            logger.info(f"✅ [BackAudit] 审核通过: {filename}")
            
    except Exception as e:
        logger.error(f"❌ [BackAudit] 任务异常: {e}", exc_info=True)


# ==================== Endpoints ====================

@router.post("/upload")
async def upload_endpoint(
    request: Request,
    response: Response,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    shared_mode: str = Form("false"),
    current_user: Optional[dict] = Depends(get_current_user_optional)
) -> JSONResponse:
    from fastapi.concurrency import run_in_threadpool
    
    try:
        content = await file.read()
        filename = file.filename or f"upload_{uuid.uuid4().hex[:8]}.png"
        is_shared = shared_mode.lower() == 'true'
        
        # 0. User & Permission Check
        user_id = current_user['id'] if current_user else None
        ip_address = request.client.host
        device_id = request.cookies.get("device_id") if not user_id else None
        
        # [Rule] 匿名用户只能用共享模式
        if not user_id and not is_shared:
            raise HTTPException(
                status_code=403, 
                detail="匿名用户只能使用共享模式。请登录后使用私有模式。"
            )
        
        # 1. [IMPORTANT] Rate Limiting FIRST (before expensive AI checks)
        limit = config.UPLOAD_LIMIT_ANONYMOUS  # 匿名用户
        if user_id:
            if current_user.get("is_vip"):
                limit = config.UPLOAD_LIMIT_VIP  # VIP
            else:
                limit = config.UPLOAD_LIMIT_FREE  # 免费用户
            count = database.get_today_upload_count(user_id=user_id)
        else:
            count = database.get_today_upload_count(ip_address=ip_address, device_id=device_id)
        
        logger.info(f"📊 今日上传统计: User={current_user['username'] if current_user else 'Guest'} Count={count} Limit={limit} VIP={current_user.get('is_vip') if current_user else 'N/A'} DebugMode={get_debug_mode()}")
        
        # 调试模式下跳过限额检查
        if get_debug_mode() and count >= limit:
            logger.info("⚠️ [DEBUG MODE] 跳过上传限额检查")
        elif count >= limit:
            user_type = "VIP 用户" if current_user and current_user.get("is_vip") else ("免费用户" if current_user else "匿名用户")
            detail_msg = f"{user_type}每日限额 {limit} 张，您已达标。"
            if not current_user:
                 detail_msg += " 请登录以获取更多额度 (5张/日)。"
            elif not current_user.get("is_vip"):
                 detail_msg += " 请激活 VIP 解锁无限上传！"
            raise HTTPException(status_code=429, detail=detail_msg)
        
        # 2. Basic Validation
        validate_file_upload(filename, content)
        
        # 3. Hashing
        fhash = calculate_hash(content)
        
        # 4. Image Info
        info = get_image_info(content)
        
        # 5. Content Audit (已移至后台异步处理)
        # audit_res = await run_in_threadpool(audit.check_image_safety, content)
        # (移除了同步阻塞逻辑)
        
        # 6. Upload to Storage (MinIO) - Sync function
        content_type = file.content_type or "application/octet-stream"
        object_name = f"{fhash}{os.path.splitext(filename)[1].lower()}"
        
        upload_result = storage.upload_to_minio(content, filename, fhash)
        if not upload_result["success"]:
             return JSONResponse(status_code=500, content={"success": False, "error": upload_result.get("error", "上传失败")})
        
        url = f"/mycloud/{upload_result['key']}"
        
        # 7. Save to Database
        if not user_id and not device_id:
            device_id = str(uuid.uuid4())
            response.set_cookie(key="device_id", value=device_id, max_age=CACHE_MAX_AGE, httponly=True)
        
        db_res = database.save_to_db(
            file_info={
                "filename": filename,
                "hash": fhash,
                "url": url,
                "width": info["width"],
                "height": info["height"],
                "size": info["size"],
                "content_type": content_type,
                "service": "MyCloud"
            },
            device_id=device_id,
            user_id=user_id,
            is_shared=is_shared,
            ip_address=ip_address
        )
        
        # 8. Log Activity
        if user_id:
            database.log_user_activity(user_id, "UPLOAD", ip_address, request.headers.get("user-agent"))

        # 8. Trigger Background Audit
        # 传递必要参数用于后续清理和通知
        background_tasks.add_task(
            background_audit_task, 
            content=content, 
            filename=filename, 
            fhash=fhash, 
            object_name=upload_result['key'],
            user_id=user_id,
            device_id=device_id
        )

        logger.info(f"✅ 上传成功(已入库，审核后台运行中): {filename} -> {url}")
        
        return JSONResponse({
            "success": True,
            "id": db_res.get("id"),
            "url": url,
            "hash": fhash,
            "filename": filename,
            "width": info["width"],
            "height": info["height"],
            "size": info["size"],
            "content_type": content_type,
            "content_type": content_type,
            # "audit_logs": ... (异步模式下不返回审核结果)
            "all_results": [{
                "service": "MyCloud",
                "success": True,
                "url": url,
                "cost_time": 0
            }]
        })

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"上传异常: {e}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": f"服务器内部错误: {str(e)}"}
        )


@router.get("/view/{image_identifier}", response_class=HTMLResponse)
async def view_image_page(request: Request, image_identifier: str):
    """
    广告落地页 (Landing Page)
    :param image_identifier: 图片的 hash 或者 filename
    """
    try:
        # 1. 尝试从数据库查找图片信息
        # 我们需要先根据 identifier 找到对应的记录
        # database.py 目前没有直接根据 hash 或 filename 查找单条记录的公开函数 (只有 list)
        # 所以我们得手写一段 SQL 或者修改 database.py。
        # 这里为了不改动 database.py, 我们直接在这里查询 (虽然不太优雅，但最快)
        
        with database.get_db_connection() as conn:
            conn.row_factory = database.sqlite3.Row
            c = conn.cursor()
            
            # 尝试匹配 hash 或 filename
            # filename 可能是 URL 编码的，也可能包含后缀
            # 优先匹配 hash (通常是无后缀的)
            c.execute("SELECT * FROM history WHERE hash = ? OR filename = ?", (image_identifier, image_identifier))
            row = c.fetchone()
            
            if not row:
                # 可能是带后缀的文件名，尝试去掉后缀再查 hash? 或者是 filename
                # 暂时只支持精确匹配
                return templates.TemplateResponse("view.html", {
                    "request": request,
                    "filename": "404 Not Found",
                    "raw_url": "/static/404.png", # 只有你有这个图
                    "width": 0,
                    "height": 0,
                    "size_str": "0 KB",
                    "created_at": "-",
                    "page_url": str(request.url)
                }, status_code=404)

            item = dict(row)
            
            # 格式化文件大小
            size_bytes = item.get("size", 0)
            if size_bytes < 1024:
                size_str = f"{size_bytes} B"
            elif size_bytes < 1024 * 1024:
                size_str = f"{size_bytes / 1024:.1f} KB"
            else:
                size_str = f"{size_bytes / 1024 / 1024:.1f} MB"

            return templates.TemplateResponse("view.html", {
                "request": request,
                "filename": item.get("filename"),
                "raw_url": item.get("url"),
                "width": item.get("width"),
                "height": item.get("height"),
                "size_str": size_str,
                "created_at": item.get("created_at"),
                "page_url": str(request.url)
            })

    except Exception as e:
        logger.error(f"❌ [MyCloud] 渲染落地页失败: {e}")
        return HTMLResponse(content=f"<h1>Error: {e}</h1>", status_code=500)

from .. import security

@router.get("/mycloud/{object_name:path}")
def get_mycloud_image(
    object_name: str, 
    token: Optional[str] = None, 
    expires: Optional[int] = None
) -> StreamingResponse:
    validate_object_path(object_name)

    # [SECURITY] 核心鉴权逻辑
    # 1. 查询图片属性
    target_url = f"/mycloud/{object_name}"
    image_record = database.get_image_by_url(target_url)

    # [SECURITY] 核心鉴权逻辑修改:
    # 私有图片仅仅是不出现在公共列表 (Shared Mode) 中
    # 但通过 URL (直链) 仍然是可以直接访问的，不需要强制签名
    # 只有 VIP 专属签名 (用于防盗链有效期控制) 才是可选的增强功能
    # 所以这里不再拦截无签名的私有图片访问
    
    # if image_record:
    #     is_shared = image_record.get("is_shared", 0)
    #     # 原逻辑: 私有图片必须签名 -> 删除
    
    # 但保留对 token/expires 的校验 (如果 URL 里带了签名参数，我们就校验它，防止伪造的签名)
    if token and expires:
        if not security.verify_url_signature(object_name, token, expires):
            raise HTTPException(status_code=403, detail="直链签名无效或已过期")

    try:
        obj = storage.get_minio_object(object_name)
        body = obj["Body"]

        lower_name = object_name.lower()
        ext = os.path.splitext(lower_name)[1]

        content_type = MIME_TYPE_MAP.get(ext)
        if not content_type:
            content_type, _ = mimetypes.guess_type(object_name)
        if not content_type:
            content_type = obj.get("ContentType", "application/octet-stream")

        headers = {
            "Content-Disposition": "inline",
            "Content-Type": content_type,
            "Cache-Control": f"public, max-age={CACHE_MAX_AGE}",
            "X-Content-Type-Options": "nosniff",
        }

        return StreamingResponse(body, media_type=content_type, headers=headers)
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=404, detail="图片未找到")

@router.post("/validate")
def validate_url(request: schemas.ValidateRequest) -> dict:
    url = request.url.strip()
    if not url:
        return {"success": False, "error": "URL 不能为空", "url": url}

    if not (url.startswith('http://') or url.startswith('https://') or url.startswith('/')):
        return {"success": False, "error": "无效的 URL 格式", "url": url}

    logger.info(f"验证 URL 请求: {url}")
    return {"success": True, "url": url}
