import socket  # 用于获取网络连接信息，这里主要用来获取本机IP地址
import os      # 操作系统接口，用于文件路径处理、环境变量获取等
import hashlib # 哈希算法库，用于计算文件的"指纹"（MD5, SHA256等）
import mimetypes # 用于猜测文件的MIME类型（如 .jpg -> image/jpeg）
import logging # 日志库，用于输出运行时的信息（Info, Error等）
import uuid    # 用于生成唯一的ID（通用唯一识别码）
from io import BytesIO # 在内存中处理二进制数据，像操作文件一样操作内存中的数据
from datetime import datetime, timedelta  # 日期时间处理
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
from . import audit      # [NEW] 图片内容审计
from . import captcha_utils  # [NEW] 验证码工具

# 认证相关导入
# 认证相关导入
from fastapi import Depends, status, Response, Request
# CORS
from fastapi.middleware.cors import CORSMiddleware

# [Refactor] Import Auth Router and Dependencies
from .routers import auth, upload, user
from .routers.auth import get_current_user, get_current_user_optional, get_password_hash, create_access_token
from .config import (
    SECRET_KEY, GOOGLE_CLIENT_ID, 
    DEFAULT_PORT, DEFAULT_HOST,
    DEVICE_ID_COOKIE_NAME, DEVICE_ID_COOKIE_MAX_AGE,
    ACCESS_TOKEN_EXPIRE_MINUTES
)

# 系统设置 (内存中存储)
from .global_state import SYSTEM_SETTINGS

# [Refactor] Auth Config moved to config.py

# ==================== 初始化 ====================

# 配置日志格式
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# [Refactor] Auth Utils moved to routers.auth

# 注册额外的 MIME 类型，确保浏览器能正确识别这些较新的图片格式
mimetypes.add_type("image/avif", ".avif")
mimetypes.add_type("image/heic", ".heic")
mimetypes.add_type("image/webp", ".webp")

# [Refactor] Auth Utils moved to routers.auth

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
    
    # 1.1 自动创建管理员 (如果配置了环境变量)
    database.create_auto_admin()
    
    # 1.5 检查关键配置
    if not SECRET_KEY or SECRET_KEY == "09d25e094faa6ca2556c818166b7a9563b93f7099f6f0f4caa6cf63b88e8d3e7":
        print("\n⚠️  警告: SECRET_KEY 未配置或使用了默认值！生产环境请在 .env 文件中设置自定义值。\n")
    if not GOOGLE_CLIENT_ID:
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
app.include_router(auth.router)
app.include_router(upload.router)
app.include_router(user.router)

# [NEW] 导入并注册管理员路由
from .routers import admin
app.include_router(admin.router)

# [SECURITY] 添加 CORS 中间件
# 允许来自任何源的跨域请求 (生产环境建议限制 origins)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 允许所有来源
    allow_credentials=True,
    allow_methods=["*"],  # 允许所有方法
    allow_headers=["*"],  # 允许所有头
)

# [SECURITY] 解决 Google Login "Cross-Origin-Opener-Policy" 报错
# 1. Cross-Origin-Opener-Policy: unsafe-none (允许与 Google 弹窗通信，禁用隔离)
# 2. Referrer-Policy: no-referrer-when-downgrade (这是 Google OAuth 推荐的设置)
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    # 强制允许跨域弹窗通信
    response.headers["Cross-Origin-Opener-Policy"] = "unsafe-none" 
    response.headers["Referrer-Policy"] = "no-referrer-when-downgrade"
    # 可选: 如果需要更严格的安全，可以尝试 "same-origin-allow-popups"，但 "unsafe-none" 兼容性最好
    return response

# ==================== 系统设置 ====================

@app.get("/system/settings")
async def get_system_settings():
    """获取系统设置"""
    return SYSTEM_SETTINGS

@app.post("/system/settings")
async def update_system_settings(settings: dict):
    """更新系统设置"""
    if "debug_mode" in settings:
        SYSTEM_SETTINGS["debug_mode"] = bool(settings["debug_mode"])
        logger.info(f"Debug Mode set to: {SYSTEM_SETTINGS['debug_mode']}")
    return SYSTEM_SETTINGS

# ==================== 验证码接口 ====================

@app.get("/captcha/generate")
async def generate_captcha_endpoint():
    """
    生成图形验证码
    Returns:
        captcha_id: 验证码ID（用于后续验证）
        image: Base64编码的验证码图片
    """
    import base64
    captcha_id, image_bytes = captcha_utils.generate_captcha()
    image_base64 = base64.b64encode(image_bytes).decode('utf-8')
    return {
        "captcha_id": captcha_id,
        "image": f"data:image/png;base64,{image_base64}"
    }

@app.post("/captcha/verify")
async def verify_captcha_endpoint(data: dict):
    """
    验证用户输入的验证码
    Args:
        captcha_id: 验证码ID
        captcha_code: 用户输入的验证码
    Returns:
        valid: 是否验证成功
    """
    captcha_id = data.get("captcha_id", "")
    user_input = data.get("captcha_code", "")
    
    is_valid = captcha_utils.verify_captcha(captcha_id, user_input)
    
    if not is_valid:
        raise HTTPException(status_code=400, detail="验证码错误或已过期")
    
    return {"valid": True, "message": "验证成功"}


# ==================== 通知 API ====================

from pydantic import BaseModel
from typing import Optional

class ReportRequest(BaseModel):
    image_hash: Optional[str] = None
    image_url: Optional[str] = None
    reason: str
    contact: Optional[str] = None

@app.get("/api/notifications")
async def get_notifications_api(
    request: Request,
    unread: bool = False,
    current_user: dict = Depends(get_current_user_optional)
):
    """获取当前用户的通知"""
    user_id = current_user.get("id") if current_user else None
    device_id = request.cookies.get(DEVICE_ID_COOKIE_NAME)
    
    if not user_id and not device_id:
        return {"notifications": []}
    
    notifications = database.get_notifications(
        user_id=user_id, 
        device_id=device_id, 
        unread_only=unread
    )
    return {"notifications": notifications}

@app.post("/api/notifications/{notification_id}/read")
async def mark_notification_read_api(
    notification_id: int,
    current_user: dict = Depends(get_current_user_optional)
):
    """标记通知为已读"""
    success = database.mark_notification_read(notification_id)
    return {"success": success}

@app.post("/api/report")
async def submit_report_api(
    request: Request,
    data: ReportRequest,
    current_user: dict = Depends(get_current_user_optional)
):
    """提交侵权举报"""
    user_id = current_user.get("id") if current_user else None
    device_id = request.cookies.get(DEVICE_ID_COOKIE_NAME)
    
    result = database.create_abuse_report(
        image_hash=data.image_hash,
        image_url=data.image_url,
        reporter_id=user_id,
        reporter_device=device_id,
        reporter_contact=data.contact,
        reason=data.reason
    )
    
    if result.get("success"):
        return {"success": True, "message": "感谢您的举报，我们会尽快处理"}
    else:
        raise HTTPException(status_code=500, detail="举报提交失败")


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


# ==================== 健康检查 ====================

@app.get("/health")
def health_check() -> dict:
    """
    健康检查接口。
    监控工具（如Coolify, K8s）会定时访问这个接口，
    如果返回200 OK，说明服务还活着。
    """
    from datetime import datetime
    
    status = {
        "status": "healthy",
        "service": "image-url-tool",
        "timestamp": datetime.now().isoformat(),
        "components": {}
    }
    
    # 检查数据库连接
    try:
        with database.get_db_connection() as conn:
            conn.execute("SELECT 1")
        status["components"]["database"] = "ok"
    except Exception as e:
        status["components"]["database"] = f"error: {str(e)}"
        status["status"] = "degraded"
    
    # 检查存储连接 (MinIO)
    try:
        if storage.minio_client:
            storage.minio_client.list_buckets()
            status["components"]["storage"] = "ok"
        else:
            status["components"]["storage"] = "not_configured"
    except Exception as e:
        status["components"]["storage"] = f"error: {str(e)}"
        status["status"] = "degraded"
    
    return status


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

@app.get("/admin")
def admin_page() -> FileResponse:
    """管理员后台页面"""
    return FileResponse(os.path.join("frontend", "admin.html"))




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
