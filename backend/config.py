# config.py - 集中管理配置常量
# 将硬编码的"魔法数字"移到这里，便于维护和修改

import os
from dotenv import load_dotenv

load_dotenv()

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
