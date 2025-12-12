import os
import hashlib
import mimetypes
import logging
import uuid
from io import BytesIO
from typing import Optional

from fastapi import APIRouter, File, UploadFile, HTTPException, Request, Response, Form, Depends
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

# Setup Logger
logger = logging.getLogger(__name__)

router = APIRouter()

# ==================== 配置常量 (从 config.py 导入) ====================
MAX_FILE_SIZE = config.MAX_FILE_SIZE
ALLOWED_EXTENSIONS = config.ALLOWED_EXTENSIONS
CACHE_MAX_AGE = config.CACHE_MAX_AGE
MIME_TYPE_MAP = config.MIME_TYPE_MAP

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

# ==================== Endpoints ====================

@router.post("/upload")
async def upload_endpoint(
    request: Request,
    response: Response,
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
        
        # 5. Content Audit (NudeNet, CLIP) - Run in threadpool to avoid blocking
        audit_res = await run_in_threadpool(audit.check_image_safety, content)
        if not audit_res["safe"]:
            logger.warning(f"🚫 拦截违规图片: {filename} ({audit_res['reason']})")
            return JSONResponse(
                status_code=400,
                content={
                    "success": False, 
                    "error": f"图片包含违规内容: {audit_res['reason']}",
                    "audit_details": audit_res.get("details")
                }
            )
        
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

        logger.info(f"✅ 上传成功: {filename} -> {url}")
        
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
            "audit_logs": audit_res.get("details", {}),
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

@router.get("/mycloud/{object_name:path}")
def get_mycloud_image(object_name: str) -> StreamingResponse:
    validate_object_path(object_name)

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
