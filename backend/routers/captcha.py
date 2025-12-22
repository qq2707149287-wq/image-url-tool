# -*- coding: utf-8 -*-
"""
验证码路由模块

提供图形验证码的生成和验证功能，用于防止自动化注册等滥用行为。
"""
import base64
import logging
from typing import Dict, Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from .. import captcha_utils

# 设置日志记录器
logger = logging.getLogger(__name__)

# 创建路由器
router = APIRouter(prefix="/captcha", tags=["验证码"])


class CaptchaVerifyRequest(BaseModel):
    """验证码验证请求模型"""
    captcha_id: str
    captcha_code: str


@router.get("/generate")
async def generate_captcha() -> Dict[str, str]:
    """
    生成图形验证码
    
    生成一个新的图形验证码图片，返回验证码ID和Base64编码的图片数据。
    验证码有效期为5分钟。
    
    Returns:
        Dict[str, str]: 包含以下字段：
            - captcha_id: 验证码唯一标识，用于后续验证
            - image: Base64编码的PNG验证码图片 (data:image/png;base64,...)
    
    Example:
        >>> response = await generate_captcha()
        >>> print(response["captcha_id"])  # "abc123..."
        >>> print(response["image"][:30])  # "data:image/png;base64,iVBOR..."
    """
    captcha_id, image_bytes = captcha_utils.generate_captcha()
    image_base64 = base64.b64encode(image_bytes).decode('utf-8')
    
    logger.debug(f"🖼️ 生成验证码: {captcha_id[:8]}...")
    
    return {
        "captcha_id": captcha_id,
        "image": f"data:image/png;base64,{image_base64}"
    }


@router.post("/verify")
async def verify_captcha(data: CaptchaVerifyRequest) -> Dict[str, Any]:
    """
    验证用户输入的验证码
    
    验证用户提交的验证码是否正确。验证码为一次性使用，验证后自动失效。
    
    Args:
        data: 验证请求数据
            - captcha_id: 验证码ID（来自generate接口）
            - captcha_code: 用户输入的验证码文本
    
    Returns:
        Dict[str, Any]: 验证结果
            - valid: 是否验证成功 (True)
            - message: 成功提示信息
    
    Raises:
        HTTPException (400): 验证码错误或已过期
    
    Example:
        >>> data = CaptchaVerifyRequest(captcha_id="abc123", captcha_code="A1B2")
        >>> result = await verify_captcha(data)
        >>> print(result)  # {"valid": True, "message": "验证成功"}
    """
    is_valid = captcha_utils.verify_captcha(data.captcha_id, data.captcha_code)
    
    if not is_valid:
        logger.warning(f"❌ 验证码验证失败: {data.captcha_id[:8]}...")
        raise HTTPException(status_code=400, detail="验证码错误或已过期")
    
    logger.info(f"✅ 验证码验证成功: {data.captcha_id[:8]}...")
    return {"valid": True, "message": "验证成功"}
