import socket  # 用于获取网络连接信息，这里主要用来获取本机IP地址
import os      # 操作系统接口，用于文件路径处理、环境变量获取等
import hashlib # 哈希算法库，用于计算文件的"指纹"（MD5, SHA256等）
import mimetypes # 用于猜测文件的MIME类型（如 .jpg -> image/jpeg）
import logging # 日志库，用于输出运行时的信息（Info, Error等）
import uuid    # 用于生成唯一的ID（通用唯一识别码）
from io import BytesIO # 在内存中处理二进制数据，像操作文件一样操作内存中的数据
from contextlib import asynccontextmanager # 用于创建异步上下文管理器（比如在应用启动和关闭时执行代码）

# FastAPI 相关导入
# FastAPI: Web框架的核心类
# File, UploadFile: 用于处理文件上传
# HTTPException: 用于抛出HTTP错误（如404 Not Found）
# Cookie: 用于处理浏览器Cookie
# Request, Response: 用于直接访问底层的HTTP请求和响应对象
# Form: 用于获取表单数据
from fastapi import FastAPI, File, UploadFile, HTTPException, Cookie, Request, Response, Form
# JSONResponse: 返回JSON格式的数据
# FileResponse: 直接返回一个文件给前端下载或显示
# StreamingResponse: 流式返回数据（用于大文件或像MinIO这样的流数据）
from fastapi.responses import JSONResponse, FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles # 用于提供静态文件服务（如css, js, 图片）
from PIL import Image # Python Imaging Library，强大的图片处理库
from dotenv import load_dotenv # 用于从 .env 文件加载环境变量

import random
import string

# 导入我们自己写的模块 (使用相对导入)
from . import database # 数据库操作相关代码
from . import storage  # 存储（MinIO）操作相关代码
from . import schemas  # 数据模型定义（用于验证请求数据格式）
from . import email_utils # 邮件发送工具

# Auth imports
from fastapi import Depends, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from passlib.context import CryptContext
from jose import JWTError, jwt
from datetime import datetime, timedelta
from typing import Optional, List
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests

# ==================== 配置常量 ====================

# 服务器配置
DEFAULT_PORT = 8000
DEFAULT_HOST = "0.0.0.0" # 0.0.0.0 表示允许任何IP访问

# 文件上传限制
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB (10 * 1024KB * 1024Bytes)
# 允许上传的文件后缀名集合（使用集合set查询速度更快）
ALLOWED_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.avif', '.heic', '.heif', '.bmp', '.svg', '.ico'}

# 缓存配置
CACHE_MAX_AGE = 31536000  # 浏览器缓存时间，单位秒（这里设为1年），让浏览器记住图片，不用每次都重新下载

# Cookie 配置
# Cookie 配置
DEVICE_ID_COOKIE_NAME = "device_id" # Cookie的名称
DEVICE_ID_COOKIE_MAX_AGE = 365 * 24 * 60 * 60  # Cookie有效期1年

# System Settings (In-memory)
SYSTEM_SETTINGS = {"debug_mode": False}

# Auth Configuration
load_dotenv() # Load env vars before using them
SECRET_KEY = os.getenv("SECRET_KEY", "09d25e094faa6ca2556c818166b7a9563b93f7099f6f0f4caa6cf63b88e8d3e7")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 30 # 30 Days
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "YOUR_GOOGLE_CLIENT_ID")

pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login", auto_error=False) # auto_error=False allow optional auth

# ==================== 初始化 ====================



# 配置日志格式
# level=logging.INFO 表示只记录INFO级别及以上的信息（INFO, WARNING, ERROR, CRITICAL）
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__) # 获取当前模块的日志记录器

# 注册额外的 MIME 类型，确保浏览器能正确识别这些较新的图片格式
mimetypes.add_type("image/avif", ".avif")
mimetypes.add_type("image/heic", ".heic")
mimetypes.add_type("image/webp", ".webp")





# ==================== Auth Utils ====================

def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    return pwd_context.hash(password)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

async def get_current_user_optional(token: str = Depends(oauth2_scheme)):
    """
    Get current user if token is present and valid, else None.
    Does not raise exception (for optional auth).
    """
    if not token:
        return None
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            return None
            
        # [NEW] Validate Session ID if present
        sid = payload.get("sid")
        if sid:
            if not database.validate_session(sid):
                # Session revoked or invalid
                return None
            # Optionally update activity?
            # database.update_session_activity(sid) 
        
    except JWTError:
        return None
    
    user = database.get_user_by_username(username)
    return user

async def get_current_user(token: str = Depends(oauth2_scheme)):
    """
    Enforce auth.
    """
    user = await get_current_user_optional(token)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user

# ==================== 工具函数 ====================

def get_local_ip() -> str:
    """
    获取本机在局域网中的 IP 地址。
    原理：尝试连接一个公共IP（这里是Google DNS 8.8.8.8），
    操作系统会自动选择合适的网卡，我们就能知道那个网卡的IP了。
    """
    try:
        # 创建一个UDP socket
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        # 尝试连接，但不会真的发送数据
        s.connect(("8.8.8.8", 80))
        # 获取socket绑定的本地地址
        ip = s.getsockname()[0]
        s.close()
        return ip
    except OSError:
        # 如果没网或报错，就返回本机回环地址
        return "127.0.0.1"


def calculate_hash(content: bytes) -> str:
    """
    计算文件内容的 SHA-256 哈希值（取前32位）。
    哈希值相当于文件的"指纹"，只要文件内容变了一点点，哈希值就会完全不同。
    我们用它来给文件重命名，这样相同内容的文件就会有相同的名字，实现"自动去重"。
    """
    # hashlib.sha256(content) 计算哈希对象
    # .hexdigest() 将哈希值转为16进制字符串
    # [:32] 只取前32个字符，因为完整的太长了，32位足够避免冲突
    return hashlib.sha256(content).hexdigest()[:32]


def get_image_info(content: bytes) -> dict[str, int]:
    """
    使用 PIL 库读取图片的宽、高信息。
    """
    try:
        # BytesIO(content) 把二进制数据伪装成一个文件对象，因为Image.open需要文件对象
        img = Image.open(BytesIO(content))
        return {"width": img.width, "height": img.height, "size": len(content)}
    except Exception:
        # 如果不是图片或无法解析，返回默认值
        return {"width": 0, "height": 0, "size": len(content)}


def validate_file_upload(filename: str, content: bytes) -> None:
    """
    验证上传文件的安全性：大小和类型。
    """
    # 1. 检查文件大小
    if len(content) > MAX_FILE_SIZE:
        # 抛出HTTP 400 错误（Bad Request）
        raise HTTPException(
            status_code=400,
            detail=f"文件过大，最大允许 {MAX_FILE_SIZE // (1024*1024)}MB"
        )

    # 2. 检查文件扩展名
    # os.path.splitext 分离文件名和后缀，例如 "photo.jpg" -> ("photo", ".jpg")
    ext = os.path.splitext(filename or '')[1].lower() # 转为小写比较
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"不支持的文件类型: {ext}，允许的类型: {', '.join(sorted(ALLOWED_EXTENSIONS))}"
        )


def validate_object_path(object_name: str) -> None:
    """
    验证对象路径，防止路径遍历攻击。
    比如用户请求 "../../etc/passwd"，如果不拦截，可能导致服务器敏感文件泄露。
    """
    if '..' in object_name or object_name.startswith('/') or object_name.startswith('\\'):
        raise HTTPException(status_code=400, detail="非法路径")


def build_upload_response(
    filename: str,
    fhash: str,
    upload_result: dict,
    image_info: dict
) -> dict:
    """构建统一的上传成功响应数据格式"""
    # 如果文件名是默认的 'image.png'（通常是粘贴上传导致的），我们用哈希值做文件名，避免混淆
    display_filename = filename if filename != 'image.png' else fhash

    return {
        "success": True,
        "filename": display_filename,
        "hash": fhash,
        "url": upload_result["url"], # 图片访问链接
        "service": upload_result["service"], # 存储服务名称（MyCloud）
        "all_results": [upload_result], # 兼容旧格式
        "failed_list": [],
        "width": image_info["width"],
        "height": image_info["height"],
        "size": image_info["size"],
        "content_type": upload_result["content_type"]
    }


# ==================== 生命周期事件 ====================

@asynccontextmanager
async def lifespan(_app: FastAPI):
    """
    FastAPI 的生命周期管理器。
    yield 之前的代码在服务器启动时执行。
    yield 之后的代码在服务器关闭时执行。
    """
    # 1. 初始化数据库（建表）
    database.init_db()
    
    # 1.5 检查关键配置
    if SECRET_KEY == "09d25e094faa6ca2556c818166b7a9563b93f7099f6f0f4caa6cf63b88e8d3e7":
        print("\n⚠️  警告: SECRET_KEY 使用了默认值！生产环境请在 .env 文件中设置自定义值。\n")
    if GOOGLE_CLIENT_ID == "YOUR_GOOGLE_CLIENT_ID":
        print("⚠️  提示: GOOGLE_CLIENT_ID 未配置，Google 登录功能将不可用。\n")
    
    # 2. 获取本机IP，打印启动提示
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

    yield # 服务器开始运行...

    print("\n👋 服务器已停止\n")


# 创建 FastAPI 应用实例
app = FastAPI(title="图片URL获取工具", lifespan=lifespan)

# ==================== 上传接口 ====================

@app.post("/upload")
async def upload_endpoint(
    request: Request,
    response: Response,
    file: UploadFile = File(...), # 接收上传的文件
    shared_mode: str = Form("false"), # 接收表单字段 shared_mode，默认为 "false"
    token: Optional[str] = Form(None) # Support token in form data for upload
) -> JSONResponse:
    """
    核心上传接口。
    """
    # 将字符串 "true"/"false" 转换为布尔值
    is_shared = shared_mode.lower() == "true"
    logger.info(f"📥 收到上传任务: {file.filename}, 共享模式: {is_shared}")

    # 尝试获取用户身份
    user = None
    if token:
        user = await get_current_user_optional(token)
    else:
        # Try header
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
             user = await get_current_user_optional(auth_header.split(" ")[1])

    user_id = user['id'] if user else None
    
    # [权限控制] 匿名用户只能使用共享模式
    if not user_id and not is_shared:
        raise HTTPException(
            status_code=403, 
            detail="匿名用户只能使用共享模式。请登录后使用私有模式。"
        )

        if user:
             logger.info(f"👤 用户上传: {user['username']}")

    if user:
         logger.info(f"👤 用户上传: {user['username']}")

    # [NEW] Rate Limiting Check (Moved outside try-catch to allow HTTPException to propagate)
    # 1. Gather ID info
    ip_address = request.client.host
    device_id = request.headers.get("X-Device-ID") 
    
    # 2. Check Limit
    limit = 2 # Default Anonymous
    
    if user:
        # Logged in
        if user.get("is_vip"):
            limit = 999999 # VIP
        else:
            limit = 5 # Free User
        
        count = database.get_today_upload_count(user_id=user['id'])
    else:
        # Anonymous
        count = database.get_today_upload_count(ip_address=ip_address, device_id=device_id)
        
    logger.info(f"📊 今日上传统计: User={user['username'] if user else 'Guest'} Count={count} Limit={limit}")
    
    # 调试模式下跳过限额检查
    if SYSTEM_SETTINGS.get("debug_mode") and count >= limit:
        logger.info("⚠️ [DEBUG MODE] 跳过上传限额检查")
    elif count >= limit:
        user_type = "VIP 用户" if user and user.get("is_vip") else ("免费用户" if user else "匿名用户")
        detail_msg = f"{user_type}每日限额 {limit} 张，您已达标。"
        if not user:
             detail_msg += " 请登录以获取更多额度 (5张/日)。"
        elif not user.get("is_vip"):
             detail_msg += " 请激活 VIP 解锁无限上传！"
             
        raise HTTPException(status_code=429, detail=detail_msg)

    try:
        # 1. 读取文件内容到内存
        content = file.file.read()

        # 2. 安全验证
        validate_file_upload(file.filename or '', content)

        # 3. 计算哈希（去重用）
        fhash = calculate_hash(content)
        
        # 4. 获取图片尺寸
        info = get_image_info(content)

        # 5. 上传到 MinIO 存储服务
        # 这一步会把文件真正存到硬盘上（通过MinIO）
        res = storage.upload_to_minio(content, file.filename or '', fhash)

        if not res["success"]:
            logger.error("❌ 上传失败")
            return JSONResponse({
                "success": False,
                "error": res.get("error", "上传失败"),
                "failed_list": [{"service": "MyCloud", "error": res.get("error")}]
            })

        logger.info("✨ 任务完成")

        # 6. 构建响应数据
        object_name = res["key"]
        
        # 构造访问链接
        # /mycloud/xxx.jpg
        url = f"/mycloud/{object_name}"
        
        # 7. 写入数据库
        # 注意: 如果文件已存在(hash相同), save_to_db 会处理 deduplication logic
        db_res = database.save_to_db({
            "url": url,
            "filename": file.filename,
            "hash": fhash,
            "service": "MyCloud",
            "width": info["width"],
            "height": info["height"],
            "size": len(content),
            "content_type": res["content_type"]
        }, device_id=device_id, user_id=user_id, is_shared=is_shared, ip_address=ip_address)
        
        if db_res.get("existing"):
             logger.info("♻️ 文件已存在 (秒传)")
             
        # 返回成功结果
        return JSONResponse({
            "success": True,
            "id": db_res.get("id"),
            "url": url,
            "hash": fhash,
            "filename": file.filename,
            "width": info["width"],
            "height": info["height"],
            "size": len(content),
            "content_type": res["content_type"],
            "all_results": [{
                "service": "MyCloud",
                "success": True,
                "url": url,
                "cost_time": 0 # 假装很快
            }]
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        logger.error(f"上传异常: {e}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": f"服务器内部错误: {str(e)}"}
        )

# ==================== 图片代理接口 ====================

# MIME 类型映射表：告诉浏览器文件是什么类型
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
    """
    代理 MinIO 图片请求。
    用户访问 /mycloud/xxx.jpg 时，这个函数会去 MinIO 取文件，然后转发给用户。
    这样做的好处：
    1. 隐藏了 MinIO 的真实地址和端口。
    2. 解决了跨域问题（CORS）。
    3. URL 看起来更整洁。
    """
    # 安全验证
    validate_object_path(object_name)

    try:
        # 从 MinIO 获取文件对象
        obj = storage.get_minio_object(object_name)
        body = obj["Body"] # 这是一个流对象，可以一点点读取

        # 确定 Content-Type
        lower_name = object_name.lower()
        ext = os.path.splitext(lower_name)[1]

        # 尝试多种方式猜测文件类型
        content_type = MIME_TYPE_MAP.get(ext)
        if not content_type:
            content_type, _ = mimetypes.guess_type(object_name)
        if not content_type:
            content_type = obj.get("ContentType", "application/octet-stream")

        # 设置响应头
        headers = {
            "Content-Disposition": "inline", # 告诉浏览器直接显示，而不是下载
            "Content-Type": content_type,
            "Cache-Control": f"public, max-age={CACHE_MAX_AGE}", # 浏览器缓存
            "X-Content-Type-Options": "nosniff",
        }

        # StreamingResponse 适合返回大文件，它不会一次性把文件读入内存，而是边读边发
        return StreamingResponse(body, media_type=content_type, headers=headers)
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=404, detail="图片未找到")


# ==================== 验证接口 ====================

@app.post("/validate")
def validate_url(request: schemas.ValidateRequest) -> dict:
    """
    简单的 URL 格式验证接口。
    """
    url = request.url.strip()

    if not url:
        return {"success": False, "error": "URL 不能为空", "url": url}

    if not (url.startswith('http://') or url.startswith('https://') or url.startswith('/')):
        return {"success": False, "error": "无效的 URL 格式", "url": url}

    logger.info(f"验证 URL 请求: {url}")
    return {"success": True, "url": url}

# ==================== Auth Endpoints ====================

@app.post("/auth/register", response_model=schemas.Token)
async def register(request: Request, user: schemas.UserCreate):
    # check if user exists
    if database.get_user_by_username(user.username):
        raise HTTPException(status_code=400, detail="Username already registered")
    
    hashed_password = get_password_hash(user.password)
    if not database.create_user(user.username, hashed_password):
         raise HTTPException(status_code=500, detail="Registration failed")
    
    # Auto login
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    
    # 获取新创建的用户ID (因为 create_user 只返回 bool)
    new_user = database.get_user_by_username(user.username)
    if new_user:
        # [NEW] Create Session
        sid = database.create_session(new_user['id'], request.headers.get("user-agent"), request.client.host)

        access_token = create_access_token(
            data={"sub": user.username, "sid": sid}, expires_delta=access_token_expires
        )
        
        # Log Activity
        # Request object is needed, update signature
        database.log_user_activity(new_user['id'], "REGISTER", request.client.host, request.headers.get("user-agent"))
        database.log_user_activity(new_user['id'], "LOGIN", request.client.host, request.headers.get("user-agent"))

    return {"access_token": access_token, "token_type": "bearer", "username": user.username}

@app.post("/auth/login", response_model=schemas.Token)
async def login(request: Request, form_data: OAuth2PasswordRequestForm = Depends(), remember_me: bool = True):
    # 支持用户名或邮箱登录
    user = database.get_user_by_username(form_data.username)
    if not user:
        # 尝试用邮箱查询
        user = database.get_user_by_email(form_data.username)
    
    if not user or not verify_password(form_data.password, user['password_hash']):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    expires_minutes = ACCESS_TOKEN_EXPIRE_MINUTES if remember_me else 60 * 24 # 1 Day if not remembered
    access_token_expires = timedelta(minutes=expires_minutes)

    # [NEW] Create Database Session
    device_info = request.headers.get("user-agent")
    ip = request.client.host
    sid = database.create_session(user['id'], device_info, ip)

    access_token = create_access_token(
        data={"sub": user['username'], "sid": sid}, expires_delta=access_token_expires
    )
    
    # Log Activity
    # Update activity log to use more info if needed, but session tracks IP/UA too.
    database.log_user_activity(user['id'], "LOGIN", request.client.host, request.headers.get("user-agent"))

    return {"access_token": access_token, "token_type": "bearer", "username": user['username']}

@app.post("/auth/google", response_model=schemas.Token)
async def google_login(req_obj: Request, request: schemas.GoogleLoginRequest):
    token = request.token
    try:
        # Verify the token
        id_info = id_token.verify_oauth2_token(
            token, 
            google_requests.Request(), 
            GOOGLE_CLIENT_ID if GOOGLE_CLIENT_ID != "YOUR_GOOGLE_CLIENT_ID" else None,
            clock_skew_in_seconds=10
        )

        google_id = id_info['sub']
        email = id_info.get('email')
        name = id_info.get('name', 'Google User')
        picture = id_info.get('picture')

        # Check if user exists
        user = database.get_user_by_google_id(google_id)
        
        if not user:
            # Create new user
            username = email if email else f"google_{google_id[:8]}"
            # Simple conflict resolution
            if database.get_user_by_username(username):
                username = f"{username}_{uuid.uuid4().hex[:4]}"
                
            success = database.create_google_user(username, google_id, picture)
            if not success:
               raise HTTPException(status_code=500, detail="Failed to create user")
            user = database.get_user_by_username(username)

        # Create access token
        access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        
        # [NEW] Create Session
        sid = database.create_session(user['id'], req_obj.headers.get("user-agent"), req_obj.client.host)

        access_token = create_access_token(
            data={"sub": user["username"], "sid": sid}, 
            expires_delta=access_token_expires
        )
        
        # Log Login
        database.log_user_activity(user['id'], "LOGIN_GOOGLE", req_obj.client.host, req_obj.headers.get("user-agent"))

        return {
            "access_token": access_token,
            "token_type": "bearer",
            "username": user["username"],
            "is_admin": bool(user.get("is_admin"))
        }

    except ValueError as e:
        logger.error(f"Invalid Google Token: {e}")
        raise HTTPException(status_code=400, detail="Invalid Google Token")
    except Exception as e:
        logger.error(f"Google Login Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/auth/me")
async def read_users_me(current_user: dict = Depends(get_current_user)):
    return {
        "id": current_user["id"],
        "username": current_user["username"],
        "is_admin": current_user.get("is_admin", 0),
        "avatar": current_user.get("avatar"),
        "created_at": current_user["created_at"],
        "is_vip": bool(current_user.get("is_vip")),
        "vip_expiry": current_user.get("vip_expiry")
    }

@app.get("/auth/config")
async def get_auth_config():
    """
    返回公开的认证配置信息，比如 Google Client ID。
    这允许前端动态获取配置，而不需要写死在代码里。
    """
    return {
        "google_client_id": GOOGLE_CLIENT_ID if GOOGLE_CLIENT_ID != "YOUR_GOOGLE_CLIENT_ID" else None
    }

@app.post("/auth/send-code")
async def send_verification_code(request: schemas.SendCodeRequest):
    """发送验证码 (注册或重置密码)"""
    email = request.email
    code_type = request.type
    
    if code_type not in ["register", "reset"]:
        raise HTTPException(status_code=400, detail="Invalid code type")

    # 生成 6 位随机验证码
    code = ''.join(random.choices(string.digits, k=6))
    expires_at = datetime.now() + timedelta(minutes=10)
    
    # 保存到数据库
    if not database.save_verification_code(email, code, code_type, expires_at):
         raise HTTPException(status_code=500, detail="Failed to save verification code")

    # 发送邮件
    try:
        if code_type == "register":
            # 检查邮箱是否已被注册
            if database.get_user_by_email(email):
                raise HTTPException(status_code=400, detail="Email already registered")
            await email_utils.send_verification_code(email, code)
        elif code_type == "reset":
            # 检查邮箱是否存在
            if not database.get_user_by_email(email):
                raise HTTPException(status_code=404, detail="Email not found")
            await email_utils.send_password_reset_code(email, code)
            
        return {"success": True, "message": "Code sent"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Send email failed: {e}")
        # In dev mode, maybe print code?
        logger.info(f"DEV MODE CODE: {code}") 
        raise HTTPException(status_code=500, detail=f"Failed to send email: {str(e)}")

@app.post("/auth/register-email")
async def register_email(req_obj: Request, request: schemas.EmailRegisterRequest):
    """邮箱注册 - 注册成功后自动登录"""
    # 1. 验证码校验
    # 如果开启调试模式，且验证码为空，则跳过验证
    bypass_verify = SYSTEM_SETTINGS.get("debug_mode", False) and (not request.code or request.code.strip() == "")
    
    if not bypass_verify:
        valid_code = database.get_valid_verification_code(request.email, "register")
        if not valid_code or valid_code != request.code:
            raise HTTPException(status_code=400, detail="Invalid or expired verification code")
        
    # 2. 检查用户名
    if database.get_user_by_username(request.username):
        raise HTTPException(status_code=400, detail="Username already exists")

    # 3. 创建用户
    password_hash = get_password_hash(request.password)
    
    # 调试模式下，如果邮箱为空，自动生成虚假邮箱以满足唯一性约束
    final_email = request.email
    if bypass_verify and (not final_email or final_email.strip() == ""):
        final_email = f"{request.username}@debug.local"

    success = database.create_email_user(request.username, final_email, password_hash)
    
    if not success:
         raise HTTPException(status_code=400, detail="Register failed (Username or Email may exist)")
    
    # 4. 删除已使用的验证码
    if not bypass_verify:
        database.delete_verification_code(request.email, "register")
    
    # 5. 自动登录 - 生成 Token
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    
    # Fetch user for ID
    user = database.get_user_by_username(request.username)
    sid = database.create_session(user['id'], req_obj.headers.get("user-agent"), req_obj.client.host)

    access_token = create_access_token(
        data={"sub": request.username, "sid": sid}, 
        expires_delta=access_token_expires
    )
         
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "username": request.username
    }

@app.post("/auth/reset-password")
async def reset_password(request: schemas.ResetPasswordRequest):
    """重置密码"""
    # 1. 验证码校验
    valid_code = database.get_valid_verification_code(request.email, "reset")
    if not valid_code or valid_code != request.code:
        raise HTTPException(status_code=400, detail="Invalid or expired verification code")
        
    # 2. 更新密码
    password_hash = get_password_hash(request.new_password)
    success = database.update_user_password(request.email, password_hash)
    
    if not success:
        raise HTTPException(status_code=500, detail="Failed to reset password")
    
    # 3. 删除已使用的验证码
    database.delete_verification_code(request.email, "reset")
        
    return {"success": True, "message": "Password reset successfully"}

@app.post("/auth/change-password")
async def change_password(
    request: schemas.ChangePasswordRequest,
    current_user: dict = Depends(get_current_user)
):
    """已登录状态下修改密码"""
    # 1. 验证旧密码
    if not verify_password(request.old_password, current_user['password_hash']):
        raise HTTPException(status_code=400, detail="旧密码不正确")
    
    # 2. 更新密码
    password_hash = get_password_hash(request.new_password)
    # 需要通过 email 或 username 更新
    if current_user.get('email'):
        success = database.update_user_password(current_user['email'], password_hash)
    else:
        # 没有 email 的用户（如早期注册的）需要通过 ID 更新
        success = database.update_user_password_by_id(current_user['id'], password_hash)
    
    if not success:
        raise HTTPException(status_code=500, detail="修改密码失败")
    
    return {"success": True, "message": "密码修改成功"}

@app.post("/auth/change-username")
async def change_username(
    request: schemas.ChangeUsernameRequest,
    current_user: dict = Depends(get_current_user)
):
    """修改用户名"""
    new_username = request.new_username.strip()
    
    # 1. 格式验证
    if len(new_username) < 2 or len(new_username) > 20:
        raise HTTPException(status_code=400, detail="用户名长度需在2-20个字符之间")
    
    # 2. 检查是否已存在
    if database.get_user_by_username(new_username):
        raise HTTPException(status_code=400, detail="用户名已被占用")
    
    # 3. 更新
    success = database.update_username(current_user['id'], new_username)
    if not success:
        raise HTTPException(status_code=500, detail="修改用户名失败")
    
    # 4. 返回新的 Token（因为 Token 中存储了用户名）
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": new_username}, 
        expires_delta=access_token_expires
    )
    
    return {
        "success": True,
        "access_token": access_token,
        "username": new_username
    }

@app.delete("/auth/delete-account")
async def delete_account(current_user: dict = Depends(get_current_user)):
    """注销账号 - 删除用户及其所有数据"""
    user_id = current_user['id']
    
    # 1. 删除用户的历史记录
    database.delete_user_history(user_id)
    
    # 2. 删除用户
    success = database.delete_user(user_id)
    
    if not success:
        raise HTTPException(status_code=500, detail="账号注销失败")
    
    return {"success": True, "message": "账号已注销"}

@app.get("/auth/user-stats")
async def get_user_stats(current_user: dict = Depends(get_current_user)):
    """获取用户统计信息"""
    stats = database.get_user_stats(current_user['id'])
    return stats

@app.get("/auth/logs", response_model=List[schemas.UserLog])
async def get_logs(current_user: dict = Depends(get_current_user)):
    """获取登录日志"""
    return database.get_user_logs(current_user['id'])

@app.get("/auth/sessions")
async def get_active_sessions(current_user: dict = Depends(get_current_user)):
    """获取当前所有活跃会话"""
    return database.get_active_sessions(current_user['id'])

@app.delete("/auth/sessions/{session_id}")
async def revoke_session(session_id: str, current_user: dict = Depends(get_current_user)):
    """注销指定会话 (踢下线)"""
    # 验证该会话是否属于当前用户
    sessions = database.get_active_sessions(current_user['id'])
    # 注意: sessions是dict (Row) list
    if not any(s['session_id'] == session_id for s in sessions):
        raise HTTPException(status_code=404, detail="Session not found")
        
    success = database.revoke_session(session_id, current_user['id'])
    if not success:
        raise HTTPException(status_code=500, detail="Failed to revoke session")
        
    return {"success": True}

@app.post("/auth/vip/activate")
async def activate_vip(
    req: schemas.VIPCodeRequest,
    current_user: dict = Depends(get_current_user)
):
    """激活 VIP"""
    code = req.code.strip()
    if not code:
        raise HTTPException(status_code=400, detail="激活码不能为空")
        
    res = database.activate_vip(current_user['id'], code)
    if not res["success"]:
        raise HTTPException(status_code=400, detail=res.get("error"))
        
    return {
        "success": True, 
        "message": "VIP 激活成功", 
        "expiry": res["expiry"]
    }

@app.post("/admin/vip/generate")
async def generate_vip_code_endpoint(
    days: int = Form(...),
    count: int = Form(1),
    current_user: dict = Depends(get_current_user)
):
    """(管理员) 生成 VIP 激活码"""
    if not current_user.get("is_admin"):
        raise HTTPException(status_code=403, detail="需要管理员权限")
        
    codes = []
    for _ in range(count):
        # 生成 16 位随机激活码 (XXXX-XXXX-XXXX-XXXX)
        raw_code = uuid.uuid4().hex[:16].upper()
        formatted_code = f"{raw_code[:4]}-{raw_code[4:8]}-{raw_code[8:12]}-{raw_code[12:]}"
        
        if database.create_vip_code(formatted_code, days):
            codes.append(formatted_code)
            
    return {"success": True, "codes": codes}


@app.get("/history")
def get_history(
    request: Request,
    response: Response,
    page: int = 1,
    page_size: int = 20,
    keyword: str = "",
    view_mode: str = "private",
    only_mine: bool = False,
    current_user: Optional[dict] = Depends(get_current_user_optional)
) -> dict:
    """
    获取历史记录列表。
    """
    user_id = current_user['id'] if current_user else None
    is_admin = current_user.get('is_admin', False) if current_user else False

    # 匿名用户强转为 shared 模式
    final_view_mode = view_mode
    if not user_id:
        final_view_mode = "shared"
    
    return database.get_history_list(page, page_size, keyword, device_id=None, user_id=user_id, is_admin=is_admin, view_mode=final_view_mode, only_mine=only_mine)


@app.post("/history/delete")
def delete_history(
    request: Request, 
    response: Response, 
    req: schemas.DeleteRequest,
    current_user: Optional[dict] = Depends(get_current_user_optional)
) -> dict:
    """批量删除历史记录"""
    user_id = current_user['id'] if current_user else None
    is_admin = current_user.get('is_admin', False) if current_user else False

    if not user_id:
        return {"success": False, "error": "Login required explicitly for deletion"}
        
    return database.delete_history_items(req.ids, device_id=None, user_id=user_id, is_admin=is_admin)

# ==================== 系统设置 ====================

@app.get("/system/settings")
async def get_system_settings():
    """获取系统设置"""
    return SYSTEM_SETTINGS

@app.post("/system/settings")
async def update_system_settings(settings: dict):
    """更新系统设置"""
    global SYSTEM_SETTINGS
    if "debug_mode" in settings:
        SYSTEM_SETTINGS["debug_mode"] = bool(settings["debug_mode"])
        logger.info(f"Debug Mode set to: {SYSTEM_SETTINGS['debug_mode']}")
    return SYSTEM_SETTINGS

# ==================== 调试辅助接口 (仅限 debug_mode) ====================

@app.post("/debug/reset-upload-count")
async def debug_reset_upload_count():
    """[DEBUG] 清空今日上传记录，方便测试限额"""
    if not SYSTEM_SETTINGS.get("debug_mode"):
        raise HTTPException(status_code=403, detail="Debug mode is disabled")
    
    try:
        with database.get_db_connection() as conn:
            conn.execute("DELETE FROM history WHERE date(created_at) = date('now', 'localtime')")
            conn.commit()
        logger.info("🔧 [DEBUG] 已重置今日上传记录")
        return {"success": True, "message": "Today's upload count reset"}
    except Exception as e:
        return {"success": False, "error": str(e)}

@app.post("/debug/quick-login")
async def debug_quick_login(request: Request, username: str = "test", password: str = "test"):
    """[DEBUG] 快速登录/注册测试账号"""
    if not SYSTEM_SETTINGS.get("debug_mode"):
        raise HTTPException(status_code=403, detail="Debug mode is disabled")
    
    # 检查用户是否存在，不存在就创建
    user = database.get_user_by_username(username)
    if not user:
        hashed = get_password_hash(password)
        database.create_user(username, hashed)
        user = database.get_user_by_username(username)
        logger.info(f"🔧 [DEBUG] 自动创建测试用户: {username}")
    
    # 生成 Token
    sid = database.create_session(user['id'], request.headers.get("user-agent"), request.client.host)
    access_token = create_access_token(
        data={"sub": user['username'], "sid": sid}, 
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    
    return {"access_token": access_token, "token_type": "bearer", "username": user['username']}

@app.post("/debug/toggle-vip")
async def debug_toggle_vip(current_user: dict = Depends(get_current_user)):
    """[DEBUG] 快速切换当前用户的 VIP 状态"""
    if not SYSTEM_SETTINGS.get("debug_mode"):
        raise HTTPException(status_code=403, detail="Debug mode is disabled")
    
    try:
        with database.get_db_connection() as conn:
            c = conn.cursor()
            # 获取当前 VIP 状态
            c.execute("SELECT is_vip FROM users WHERE id = ?", (current_user['id'],))
            row = c.fetchone()
            new_vip = 0 if row and row[0] else 1
            
            # 切换状态
            expiry = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d %H:%M:%S") if new_vip else None
            c.execute("UPDATE users SET is_vip = ?, vip_expiry = ? WHERE id = ?", (new_vip, expiry, current_user['id']))
            conn.commit()
            
        status = "VIP 已开启" if new_vip else "VIP 已关闭"
        logger.info(f"🔧 [DEBUG] 用户 {current_user['username']} {status}")
        return {"success": True, "is_vip": bool(new_vip), "message": status}
    except Exception as e:
        return {"success": False, "error": str(e)}

@app.post("/history/clear")
def clear_history(
    request: Request, 
    response: Response,
    view_mode: str = "private",
    current_user: Optional[dict] = Depends(get_current_user_optional)
) -> dict:
    """清空历史记录"""
    user_id = current_user['id'] if current_user else None
    is_admin = current_user.get('is_admin', False) if current_user else False
    
    if not user_id:
         return {"success": False, "error": "Login required"}
         
    return database.clear_all_history(device_id=None, view_mode=view_mode, user_id=user_id, is_admin=is_admin)


@app.post("/history/rename")
def rename_history(
    request: Request, 
    response: Response, 
    body: schemas.RenameRequest,
    current_user: Optional[dict] = Depends(get_current_user_optional)
) -> JSONResponse:
    """重命名历史记录"""
    user_id = current_user['id'] if current_user else None
    is_admin = current_user.get('is_admin', False) if current_user else False

    if not user_id:
        return JSONResponse({"success": False, "error": "Login required"})

    try:
        # Use body.id instead of body.url
        res = database.rename_history_item(body.id, body.filename, device_id=None, user_id=user_id, is_admin=is_admin)

        if res["success"]:
            logger.info(f"✅ 重命名成功: ID={body.id} -> {body.filename}")
            return JSONResponse({"success": True})
        else:
            logger.warning(f"❌ 重命名失败: {res.get('error')} (ID: {body.id})")
            return JSONResponse({"success": False, "error": res.get("error")})
    except Exception as e:
        logger.error(f"❌ 重命名失败: {e}", exc_info=True)
        return JSONResponse({"success": False, "error": "服务器内部错误"})


# ==================== 健康检查 ====================

@app.get("/health")
def health_check() -> dict:
    """
    健康检查接口。
    监控工具（如Coolify, K8s）会定时访问这个接口，
    如果返回200 OK，说明服务还活着。
    """
    return {"status": "healthy", "service": "image-url-tool"}


# ==================== 静态文件与首页 ====================

# 挂载静态文件目录，让 /static/xxx 可以访问 frontend/xxx 下的文件
app.mount("/static", StaticFiles(directory="frontend"), name="static")


@app.get("/terms")
def terms() -> FileResponse:
    """服务条款页面"""
    return FileResponse(os.path.join("frontend", "pages", "terms.html"))

@app.get("/privacy")
def privacy() -> FileResponse:
    """隐私政策页面"""
    return FileResponse(os.path.join("frontend", "pages", "privacy.html"))

@app.get("/report")
def report() -> FileResponse:
    """举报页面"""
    return FileResponse(os.path.join("frontend", "pages", "report.html"))


@app.get("/")
def index() -> FileResponse:
    """
    访问根路径 / 时，返回 index.html 页面。
    """
    return FileResponse(os.path.join("frontend", "index.html"))


if __name__ == "__main__":
    # 如果直接运行此文件 (python main.py)，则启动 uvicorn 服务器
    import uvicorn
    import sys
    
    try:
        uvicorn.run(
            app,
            host=DEFAULT_HOST,
            port=DEFAULT_PORT,
            log_level="info",
            access_log=False
        )
    except KeyboardInterrupt:
        pass
    finally:
        print("正在强制退出程序...")
        sys.exit(0)
