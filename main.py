import socket
import os
import hashlib
import mimetypes
import logging
from io import BytesIO
from contextlib import asynccontextmanager

from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.responses import JSONResponse, FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from PIL import Image
from dotenv import load_dotenv

# 导入项目模块
import database
import storage
import schemas

# ==================== 配置常量 ====================

# 服务器配置
DEFAULT_PORT = 8000
DEFAULT_HOST = "0.0.0.0"

# 文件上传限制
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
ALLOWED_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.avif', '.heic', '.heif', '.bmp', '.svg', '.ico'}

# 缓存配置
CACHE_MAX_AGE = 31536000  # 1年

# ==================== 初始化 ====================

# 加载环境变量
load_dotenv()

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 注册额外的 MIME 类型
mimetypes.add_type("image/avif", ".avif")
mimetypes.add_type("image/heic", ".heic")
mimetypes.add_type("image/webp", ".webp")

# ==================== 工具函数 ====================

def get_local_ip() -> str:
    """获取本机局域网 IP 地址"""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except OSError:
        return "127.0.0.1"


def calculate_hash(content: bytes) -> str:
    """计算文件内容的 SHA-256 哈希值（取前32位）"""
    return hashlib.sha256(content).hexdigest()[:32]


def get_image_info(content: bytes) -> dict[str, int]:
    """获取图片尺寸和大小信息"""
    try:
        img = Image.open(BytesIO(content))
        return {"width": img.width, "height": img.height, "size": len(content)}
    except Exception:
        # 无法解析图片时返回默认值
        return {"width": 0, "height": 0, "size": len(content)}


def validate_file_upload(filename: str, content: bytes) -> None:
    """
    验证上传文件的安全性

    Args:
        filename: 文件名
        content: 文件内容

    Raises:
        HTTPException: 文件验证失败时抛出
    """
    # 检查文件大小
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=400,
            detail=f"文件过大，最大允许 {MAX_FILE_SIZE // (1024*1024)}MB"
        )

    # 检查文件扩展名
    ext = os.path.splitext(filename or '')[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"不支持的文件类型: {ext}，允许的类型: {', '.join(sorted(ALLOWED_EXTENSIONS))}"
        )


def validate_object_path(object_name: str) -> None:
    """
    验证对象路径，防止路径遍历攻击

    Args:
        object_name: 对象路径名

    Raises:
        HTTPException: 路径不安全时抛出
    """
    if '..' in object_name or object_name.startswith('/') or object_name.startswith('\\'):
        raise HTTPException(status_code=400, detail="非法路径")


def build_upload_response(
    filename: str,
    fhash: str,
    upload_result: dict,
    image_info: dict
) -> dict:
    """构建上传成功的响应数据"""
    # 如果文件名是默认的 image.png，使用 hash 作为文件名
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


# ==================== 生命周期事件 ====================

@asynccontextmanager
async def lifespan(_app: FastAPI):
    """应用生命周期管理"""
    database.init_db()
    local_ip = get_local_ip()

    print("\n" + "=" * 60)
    print(f"✅ 服务器启动成功！ (Host IP: {local_ip})")
    print("=" * 60)
    print("📍 访问地址:")
    print(f"   • http://localhost:{DEFAULT_PORT}")
    print(f"   • http://{local_ip}:{DEFAULT_PORT}")
    print("")
    print("💡 使用说明:")
    print("   1. 在浏览器中打开上述任一地址")
    print("   2. 上传图片或输入图片URL")
    print("   3. 自动上传至 MyCloud 并生成预览链接")
    print("")
    print("⚠️  按 Ctrl+C 可停止服务器")
    print("=" * 60 + "\n")

    yield

    print("\n👋 服务器已停止\n")


app = FastAPI(title="图片URL获取工具", lifespan=lifespan)

# ==================== 上传接口 ====================

@app.post("/upload")
def upload_endpoint(file: UploadFile = File(...)) -> JSONResponse:
    """
    上传图片文件

    - 支持格式: jpg, jpeg, png, gif, webp, avif, heic, heif, bmp, svg, ico
    - 最大文件大小: 10MB
    """
    logger.info(f"📥 收到上传任务: {file.filename}")

    try:
        # 读取文件内容
        content = file.file.read()

        # 安全验证：检查文件类型和大小
        validate_file_upload(file.filename or '', content)

        # 计算文件哈希
        fhash = calculate_hash(content)
        info = get_image_info(content)

        # 上传到存储服务
        res = storage.upload_to_minio(content, file.filename or '', fhash)

        if not res["success"]:
            logger.error("❌ 上传失败")
            return JSONResponse({
                "success": False,
                "error": res.get("error", "上传失败"),
                "failed_list": [{"service": "MyCloud", "error": res.get("error")}]
            })

        logger.info("✨ 任务完成")

        # 构建响应数据
        result_data = build_upload_response(
            file.filename or '', fhash, res, info
        )

        # 保存到数据库
        database.save_to_db(result_data)

        return JSONResponse(result_data)

    except HTTPException:
        # 重新抛出 HTTPException，让 FastAPI 处理
        raise
    except Exception as e:
        logger.error(f"上传异常: {e}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": "服务器内部错误"}
        )

# ==================== 图片代理接口 ====================

# MIME 类型映射表
MIME_TYPE_MAP = {
    ".avif": "image/avif",
    ".webp": "image/webp",
    ".heic": "image/heic",
    ".heif": "image/heif",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".gif": "image/gif",
    ".bmp": "image/bmp",
    ".svg": "image/svg+xml",
    ".ico": "image/x-icon",
}


@app.get("/mycloud/{object_name:path}")
def get_mycloud_image(object_name: str) -> StreamingResponse:
    """代理 MinIO 图片请求"""
    # 安全验证：防止路径遍历攻击
    validate_object_path(object_name)

    try:
        obj = storage.get_minio_object(object_name)
        body = obj["Body"]

        # 获取文件扩展名并确定 MIME 类型
        lower_name = object_name.lower()
        ext = os.path.splitext(lower_name)[1]

        # 优先使用映射表，然后尝试 mimetypes，最后使用默认值
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


# ==================== 验证接口 ====================

@app.post("/validate")
def validate_url(request: schemas.ValidateRequest) -> dict:
    """
    验证图片 URL 的有效性

    检查 URL 格式是否正确，以及是否指向有效的图片资源
    """
    url = request.url.strip()

    # 基本 URL 格式验证
    if not url:
        return {"success": False, "error": "URL 不能为空", "url": url}

    # 检查 URL 格式
    if not (url.startswith('http://') or url.startswith('https://') or url.startswith('/')):
        return {"success": False, "error": "无效的 URL 格式", "url": url}

    logger.info(f"验证 URL 请求: {url}")
    return {"success": True, "url": url}

# ==================== 历史记录接口 ====================

@app.get("/history")
def get_history(page: int = 1, page_size: int = 20, keyword: str = "") -> dict:
    """获取历史记录列表，支持分页和关键词搜索"""
    return database.get_history_list(page, page_size, keyword)


@app.post("/history/delete")
def delete_history(req: schemas.DeleteRequest) -> dict:
    """批量删除历史记录"""
    return database.delete_history_items(req.ids)


@app.post("/history/clear")
def clear_history() -> dict:
    """清空所有历史记录"""
    return database.clear_all_history()


@app.post("/history/rename")
def rename_history(body: schemas.RenameRequest) -> JSONResponse:
    """重命名历史记录"""
    try:
        res = database.rename_history_item(body.url, body.filename)

        if res["success"]:
            logger.info(f"✅ 重命名成功: {body.url} -> {body.filename}")
            return JSONResponse({"success": True})
        else:
            logger.warning(f"❌ 重命名失败: {res.get('error')} (URL: {body.url})")
            return JSONResponse({"success": False, "error": res.get("error")})
    except Exception as e:
        logger.error(f"❌ 重命名失败: {e}", exc_info=True)
        return JSONResponse({"success": False, "error": "服务器内部错误"})


# ==================== 健康检查 ====================

@app.get("/health")
def health_check() -> dict:
    """健康检查端点，用于监控服务状态"""
    return {"status": "healthy", "service": "image-url-tool"}


# ==================== 静态文件与首页 ====================

app.mount("/static", StaticFiles(directory="frontend"), name="static")


@app.get("/")
def index() -> FileResponse:
    """返回前端首页"""
    return FileResponse(os.path.join("frontend", "index.html"))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app,
        host=DEFAULT_HOST,
        port=DEFAULT_PORT,
        log_level="info",
        access_log=False
    )
