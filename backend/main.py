# -*- coding: utf-8 -*-
"""
图床工具主应用模块

这是应用的入口点，负责：
- FastAPI 应用初始化
- 路由注册
- 中间件配置
- 生命周期管理
- 静态文件服务

路由逻辑已拆分到 routers/ 目录下的各个模块。
"""
import os
import socket
import shutil
import mimetypes
import logging
from typing import Dict, Any
from datetime import datetime
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

# 限流配置
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

# 项目内部模块
from . import database
from . import storage
from .limiter import limiter
from .config import (
    SECRET_KEY, GOOGLE_CLIENT_ID,
    DEFAULT_PORT, DEFAULT_HOST,
    DEBUG_MODE
)
from .global_state import SYSTEM_SETTINGS
from .logging_config import setup_logging
from .exceptions import ImageToolException

# 路由模块
from .routers import auth, upload, user, admin
from .routers import captcha, notifications, debug, pages


# ==================== 日志初始化 ====================
# 配置日志轮转
logger = setup_logging()

# 注册额外的 MIME 类型
mimetypes.add_type("image/avif", ".avif")
mimetypes.add_type("image/heic", ".heic")
mimetypes.add_type("image/webp", ".webp")


# ==================== 工具函数 ====================

def get_local_ip() -> str:
    """
    获取本机在局域网中的 IP 地址
    
    原理：尝试连接一个公共IP（Google DNS 8.8.8.8），
    操作系统会自动选择合适的网卡，我们就能知道那个网卡的IP了。
    
    Returns:
        str: 本机局域网 IP 地址，获取失败时返回 "127.0.0.1"
    """
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except OSError:
        return "127.0.0.1"


def get_disk_usage() -> Dict[str, Any]:
    """
    获取磁盘使用情况
    
    Returns:
        Dict[str, Any]: 磁盘使用信息，包含状态、剩余空间等
    """
    try:
        total, used, free = shutil.disk_usage(".")
        free_gb = free / (1024 ** 3)
        used_percent = (used / total) * 100
        
        # 剩余空间小于1GB时警告
        status = "ok" if free_gb > 1 else "warning"
        
        return {
            "status": status,
            "free_gb": round(free_gb, 2),
            "used_percent": round(used_percent, 1)
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}


# ==================== 生命周期管理 ====================

@asynccontextmanager
async def lifespan(_app: FastAPI):
    """
    FastAPI 生命周期管理器
    
    - yield 之前：服务器启动时执行的初始化代码
    - yield 之后：服务器关闭时执行的清理代码
    """
    # 1. 初始化数据库
    database.init_db()
    database.create_auto_admin()

    # 1.5 同步调试模式配置
    SYSTEM_SETTINGS["debug_mode"] = DEBUG_MODE
    if DEBUG_MODE:
        logger.info("🔧 Debug Mode 已通过环境变量启用 (Enable Simple Registration)")
    
    # 2. 检查关键配置
    if not SECRET_KEY or SECRET_KEY == "09d25e094faa6ca2556c818166b7a9563b93f7099f6f0f4caa6cf63b88e8d3e7":
        logger.warning("⚠️ SECRET_KEY 未配置或使用了默认值！生产环境请在 .env 文件中设置自定义值。")
    if not GOOGLE_CLIENT_ID:
        logger.info("💡 GOOGLE_CLIENT_ID 未配置，Google 登录功能将不可用。")
    
    # 3. 打印启动提示
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
    print("⚠️ 按 Ctrl+C 可停止服务器")
    print("=" * 60 + "\n")

    yield  # 服务器运行中...

    logger.info("👋 服务器已停止")


# ==================== 应用实例创建 ====================

app = FastAPI(
    title="图片URL获取工具",
    description="一站式图片托管与分享服务",
    version="2.0.0",
    lifespan=lifespan
)

# ==================== 中间件配置 ====================

# 1. 限流中间件
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

# 2. CORS 中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    """
    添加安全相关的 HTTP 头
    
    解决 Google Login 的 Cross-Origin-Opener-Policy 问题
    """
    response = await call_next(request)
    response.headers["Cross-Origin-Opener-Policy"] = "unsafe-none"
    response.headers["Referrer-Policy"] = "no-referrer-when-downgrade"
    return response


# ==================== 全局异常处理 ====================

@app.exception_handler(ImageToolException)
async def image_tool_exception_handler(request: Request, exc: ImageToolException):
    """
    处理自定义业务异常
    
    将业务异常转换为标准格式的 JSON 响应
    """
    logger.warning(f"业务异常: [{exc.code}] {exc.message}")
    return JSONResponse(
        status_code=exc.status_code,
        content=exc.to_response()
    )


# ==================== 路由注册 ====================

# 核心业务路由
app.include_router(auth.router)
app.include_router(upload.router)
app.include_router(user.router)
app.include_router(admin.router)

# 新拆分的路由模块
app.include_router(captcha.router)
app.include_router(notifications.router)
app.include_router(debug.router)
app.include_router(pages.router)


# ==================== 系统设置 API ====================

@app.get("/system/settings", tags=["系统"])
async def get_system_settings() -> Dict[str, Any]:
    """
    获取系统设置
    
    Returns:
        Dict[str, Any]: 当前系统设置，包括调试模式等
    """
    return SYSTEM_SETTINGS


@app.post("/system/settings", tags=["系统"])
async def update_system_settings(settings: dict) -> Dict[str, Any]:
    """
    更新系统设置
    
    Args:
        settings: 要更新的设置项
    
    Returns:
        Dict[str, Any]: 更新后的系统设置
    """
    if "debug_mode" in settings:
        SYSTEM_SETTINGS["debug_mode"] = bool(settings["debug_mode"])
        logger.info(f"🔧 Debug Mode 已设置为: {SYSTEM_SETTINGS['debug_mode']}")
    return SYSTEM_SETTINGS


# ==================== 健康检查 ====================

@app.get("/health", tags=["系统"])
@app.get("/healthz", tags=["系统"])
def health_check() -> Dict[str, Any]:
    """
    健康检查接口
    
    用于监控工具（如 Coolify, K8s, Docker）检测服务状态。
    检查项包括：数据库连接、存储连接、磁盘空间。
    
    Returns:
        Dict[str, Any]: 健康状态信息
            - status: "healthy" | "degraded" | "unhealthy"
            - service: 服务名称
            - timestamp: 检查时间
            - components: 各组件状态详情
    
    Example:
        >>> GET /health
        >>> {
        ...     "status": "healthy",
        ...     "components": {
        ...         "database": "ok",
        ...         "storage": "ok",
        ...         "disk": {"status": "ok", "free_gb": 50.2}
        ...     }
        ... }
    """
    result = {
        "status": "healthy",
        "service": "image-url-tool",
        "version": "2.0.0",
        "timestamp": datetime.now().isoformat(),
        "components": {}
    }
    
    # 1. 检查数据库连接
    try:
        with database.get_db_connection() as conn:
            conn.execute("SELECT 1")
        result["components"]["database"] = "ok"
    except Exception as e:
        result["components"]["database"] = f"error: {str(e)}"
        result["status"] = "degraded"
    
    # 2. 检查存储连接 (MinIO)
    try:
        if storage.minio_client:
            storage.minio_client.list_buckets()
            result["components"]["storage"] = "ok"
        else:
            result["components"]["storage"] = "not_configured"
    except Exception as e:
        result["components"]["storage"] = f"error: {str(e)}"
        result["status"] = "degraded"
    
    # 3. 检查磁盘空间
    result["components"]["disk"] = get_disk_usage()
    if result["components"]["disk"].get("status") == "warning":
        if result["status"] == "healthy":
            result["status"] = "degraded"
    
    return result


# ==================== 静态文件与首页 ====================

# 挂载静态文件目录
app.mount("/static", StaticFiles(directory="frontend"), name="static")


@app.get("/", tags=["页面"])
def index() -> FileResponse:
    """
    首页
    
    返回主页面 index.html
    """
    return FileResponse(os.path.join("frontend", "index.html"))


# ==================== 主程序入口 ====================

if __name__ == "__main__":
    import sys
    import uvicorn
    
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
        print("正在退出程序...")
        sys.exit(0)
