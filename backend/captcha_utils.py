# -*- coding: utf-8 -*-
# captcha_utils.py - 图形验证码生成和验证
# 使用 captcha 库生成图片验证码，无需外部服务

import uuid
import time
import logging
from io import BytesIO
from typing import Optional, Dict, Tuple
from captcha.image import ImageCaptcha

logger = logging.getLogger(__name__)

# ==================== 验证码存储 ====================
# 内存存储 (生产环境建议使用 Redis)
# 格式: {captcha_id: (answer, expire_time)}
_captcha_store: Dict[str, Tuple[str, float]] = {}

# 配置
CAPTCHA_LENGTH = 4          # 验证码长度
CAPTCHA_EXPIRE_SECONDS = 300  # 验证码有效期（5分钟）
CAPTCHA_CLEANUP_THRESHOLD = 1000  # 触发清理的阈值

# 验证码字符集（排除容易混淆的字符：0O, 1lI）
CAPTCHA_CHARS = "23456789ABCDEFGHJKLMNPQRSTUVWXYZ"


def _cleanup_expired():
    """清理过期的验证码"""
    global _captcha_store
    now = time.time()
    expired_keys = [k for k, v in _captcha_store.items() if v[1] < now]
    for k in expired_keys:
        del _captcha_store[k]
    if expired_keys:
        logger.debug(f"🧹 清理了 {len(expired_keys)} 个过期验证码")


def generate_captcha() -> Tuple[str, bytes]:
    """
    生成验证码
    Returns:
        (captcha_id, image_bytes) - 验证码ID和图片二进制数据
    """
    # 定期清理过期验证码
    if len(_captcha_store) > CAPTCHA_CLEANUP_THRESHOLD:
        _cleanup_expired()
    
    # 生成随机验证码文本
    import random
    text = "".join(random.choices(CAPTCHA_CHARS, k=CAPTCHA_LENGTH))
    
    # 生成唯一ID
    captcha_id = uuid.uuid4().hex
    
    # 存储验证码答案和过期时间
    expire_time = time.time() + CAPTCHA_EXPIRE_SECONDS
    _captcha_store[captcha_id] = (text.upper(), expire_time)
    
    # 生成验证码图片
    image = ImageCaptcha(width=160, height=60)
    data = image.generate(text)
    
    logger.debug(f"🔐 生成验证码: ID={captcha_id[:8]}...")
    
    return captcha_id, data.read()


def verify_captcha(captcha_id: str, user_input: str) -> bool:
    """
    验证用户输入的验证码
    Args:
        captcha_id: 验证码ID
        user_input: 用户输入的验证码
    Returns:
        验证是否成功
    """
    if not captcha_id or not user_input:
        return False
    
    stored = _captcha_store.get(captcha_id)
    if not stored:
        logger.warning(f"⚠️ 验证码不存在: ID={captcha_id[:8]}...")
        return False
    
    answer, expire_time = stored
    
    # 检查是否过期
    if time.time() > expire_time:
        del _captcha_store[captcha_id]
        logger.warning(f"⚠️ 验证码已过期: ID={captcha_id[:8]}...")
        return False
    
    # 验证后删除（一次性使用）
    del _captcha_store[captcha_id]
    
    # 不区分大小写比较
    is_valid = user_input.upper().strip() == answer
    
    if is_valid:
        logger.info(f"✅ 验证码验证成功: ID={captcha_id[:8]}...")
    else:
        logger.warning(f"❌ 验证码错误: ID={captcha_id[:8]}... 期望={answer}, 输入={user_input.upper()}")
    
    return is_valid
