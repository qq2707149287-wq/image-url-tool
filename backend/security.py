# -*- coding: utf-8 -*-
import hmac
import hashlib
import time
import os
from typing import Optional

# 从环境变量获取 SECRET_KEY，如果没有则使用默认值（仅开发环境）
# 注意：生产环境必须设置 SECRET_KEY，否则每次重启签名都会失效
SECRET_KEY = os.getenv("SECRET_KEY", "dev_secret_key_change_me")

def generate_url_signature(object_name: str, expires_at: int) -> str:
    """
    生成 URL 签名
    :param object_name: 对象路径 (e.g. "image.jpg")
    :param expires_at: 过期时间戳 (Unix timestamp)
    :return: 签名字符串 (Hex)
    """
    data = f"{object_name}:{expires_at}"
    signature = hmac.new(
        SECRET_KEY.encode('utf-8'),
        data.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
    return signature

def verify_url_signature(object_name: str, signature: str, expires_at: int) -> bool:
    """
    验证 URL 签名
    :param object_name: 对象路径
    :param signature: 待验证的签名
    :param expires_at: 过期时间戳
    :return: 是否有效
    """
    if not signature or not expires_at:
        return False
        
    # 1. 检查是否过期
    if int(time.time()) > expires_at:
        return False
        
    # 2. 重新计算签名并比对
    expected_signature = generate_url_signature(object_name, expires_at)
    
    # 使用 hmac.compare_digest 防止时序攻击
    return hmac.compare_digest(expected_signature, signature)
