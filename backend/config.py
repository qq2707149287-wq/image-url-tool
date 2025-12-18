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
# 生产环境必须在 .env 中设置此值！
_secret_key = os.getenv("SECRET_KEY")
if not _secret_key:
    logger.warning("⚠️ [Config] 未配置 SECRET_KEY! 使用随机生成的临时密钥。")
    _secret_key = "".join(random.choices(string.ascii_letters + string.digits, k=64))
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
MAX_FILE_SIZE = 10 * 1024 * 1024  # 最大文件大小：10MB
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


