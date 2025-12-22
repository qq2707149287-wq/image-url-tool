# -*- coding: utf-8 -*-
# config.py - 集中管理配置常量
# 将硬编码的"魔法数字"移到这里，便于维护和修改

import os
import random
import string
import logging
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

# ==================== 安全配置 ====================
# [SECURITY] SECRET_KEY 用于 JWT 签名和其他加密操作
# 优先级: 环境变量 > .secret_key 文件 > 随机生成并保存
_secret_file_path = os.path.join(os.getenv("DATA_DIR") or os.path.dirname(os.path.abspath(__file__)), ".secret_key")
_secret_key = os.getenv("SECRET_KEY")

if not _secret_key:
    # 尝试从文件读取
    if os.path.exists(_secret_file_path):
        try:
            with open(_secret_file_path, "r", encoding="utf-8") as f:
                _secret_key = f.read().strip()
                if _secret_key:
                    logger.info(f"🔑 [Config] 从文件加载了 SECRET_KEY: {_secret_file_path}")
        except Exception as e:
            logger.error(f"❌ [Config] 读取密钥文件失败: {e}")

    # 如果还是没有，生成并保存
    if not _secret_key:
        logger.warning("⚠️ [Config] 未配置 SECRET_KEY! 正在生成持久化密钥...")
        _secret_key = "".join(random.choices(string.ascii_letters + string.digits, k=64))
        try:
            with open(_secret_file_path, "w", encoding="utf-8") as f:
                f.write(_secret_key)
            logger.info(f"✅ [Config] 已将新生成的 SECRET_KEY 保存至: {_secret_file_path}")
            # Windows下尝试隐藏文件 (可选)
            if os.name == 'nt':
                try:
                    import ctypes
                    ctypes.windll.kernel32.SetFileAttributesW(_secret_file_path, 2) # FILE_ATTRIBUTE_HIDDEN
                except:
                    pass
        except Exception as e:
            logger.error(f"❌ [Config] 保存密钥文件失败: {e}")

SECRET_KEY = _secret_key

# JWT 算法
JWT_ALGORITHM = "HS256"

# Token 过期时间（分钟）: 30天
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 30

# Bcrypt 加盐轮数 (越高越安全，但越慢)
# 推荐值: 10-12 之间，12 是一个较好的平衡点
BCRYPT_ROUNDS = 12

# 谷歌 OAuth 配置
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")

# ==================== 上传限额配置 ====================
# 每日上传限额（张/天）
UPLOAD_LIMIT_ANONYMOUS = 2      # 匿名用户
UPLOAD_LIMIT_FREE = 5           # 免费注册用户
UPLOAD_LIMIT_VIP = 999999       # VIP 用户（相当于无限）

# ==================== 文件配置 ====================
MAX_FILE_SIZE = 10 * 1024 * 1024  # 免费/匿名用户最大文件大小：10MB
MAX_FILE_SIZE_VIP = 50 * 1024 * 1024  # VIP用户最大文件大小：50MB
ALLOWED_EXTENSIONS = {
    '.jpg', '.jpeg', '.png', '.gif', '.webp', 
    '.avif', '.heic', '.heif', '.bmp', '.svg', '.ico'
}

# ==================== Cookie 配置 ====================
DEVICE_ID_COOKIE_NAME = "device_id"
DEVICE_ID_COOKIE_MAX_AGE = 365 * 24 * 60 * 60  # 1年

# ==================== 服务器配置 ====================
DEFAULT_HOST = "0.0.0.0"
DEFAULT_PORT = int(os.getenv("PORT", 8000))

# ==================== 缓存配置 ====================
CACHE_MAX_AGE = 31536000  # 图片缓存时间：1年 (秒)

# ==================== MIME 类型映射 ====================
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

# ==================== AI 审核配置 ====================
# 低内存服务器设为 true 以禁用 AI 审核 (节省 ~2GB 内存)
DISABLE_AI_AUDIT = os.getenv("DISABLE_AI_AUDIT", "false").lower() == "true"

# ==================== 数据库配置 ====================
# 数据目录（Docker 部署时挂载到 /app/data）
DATA_DIR = os.getenv("DATA_DIR")

# ==================== 调试模式 ====================
DEBUG_MODE = os.getenv("DEBUG_MODE", "false").lower() == "true"


# ==================== 数据库配置扩展 ====================
# [Refactor] 将 DB_PATH 逻辑集中到这里
if DATA_DIR:
    # 确保目录存在
    os.makedirs(DATA_DIR, exist_ok=True)
    DB_PATH = os.path.join(DATA_DIR, "history.db")
else:
    # 默认为项目根目录下的 history.db
    # 注意：这里我们假设 config.py 在 backend/ 目录下，项目根目录是 backend/ 的上一级
    # backend/config.py -> backend/ -> project_root/
    _current_dir = os.path.dirname(os.path.abspath(__file__))
    _project_root = os.path.dirname(_current_dir)
    DB_PATH = os.path.join(_project_root, "history.db")

# ==================== 业务逻辑配置 ====================
VERIFICATION_CODE_LENGTH = 6
VERIFICATION_CODE_EXPIRY_MINUTES = 10
DEBUG_CAPTCHA_CODE = "abcd"
SHORT_TOKEN_EXPIRE_MINUTES = 60 * 24  # 1天
VIP_LINK_EXPIRE_DAYS = 365

# ==================== CORS 跨域配置 ====================
# 允许的来源列表，用逗号分隔
# - 开发环境: "*" 允许所有来源
# - 生产环境: 应配置具体域名，如 "https://example.com,https://api.example.com"
_cors_origins_str = os.getenv("CORS_ALLOWED_ORIGINS", "*")
if _cors_origins_str == "*":
    CORS_ALLOWED_ORIGINS = ["*"]
else:
    CORS_ALLOWED_ORIGINS = [origin.strip() for origin in _cors_origins_str.split(",") if origin.strip()]

