# -*- coding: utf-8 -*-
"""
调试路由模块

提供仅在调试模式下可用的辅助接口，用于开发和测试。
生产环境中这些接口会返回403错误。
"""
import logging
from datetime import datetime, timedelta
from typing import Dict, Any

from fastapi import APIRouter, HTTPException, Request, Depends

from .. import database
from ..config import ACCESS_TOKEN_EXPIRE_MINUTES
from ..global_state import SYSTEM_SETTINGS
from ..routers.auth import get_current_user, get_password_hash, create_access_token

# 设置日志记录器
logger = logging.getLogger(__name__)

# 创建路由器
router = APIRouter(prefix="/debug", tags=["调试"])


def require_debug_mode() -> None:
    """
    检查调试模式是否启用
    
    Raises:
        HTTPException (403): 调试模式未启用
    """
    if not SYSTEM_SETTINGS.get("debug_mode"):
        raise HTTPException(status_code=403, detail="调试模式已禁用")


@router.post("/reset-upload-count")
async def reset_upload_count() -> Dict[str, Any]:
    """
    [DEBUG] 清空今日上传记录
    
    重置当天的上传计数，方便测试上传限额功能。
    仅在调试模式下可用。
    
    Returns:
        Dict[str, Any]: 操作结果
            - success: 是否成功
            - message: 提示信息
    
    Raises:
        HTTPException (403): 调试模式未启用
    
    Example:
        >>> POST /debug/reset-upload-count
        >>> {"success": true, "message": "今日上传计数已重置"}
    """
    require_debug_mode()
    
    try:
        with database.get_db_connection() as conn:
            conn.execute("DELETE FROM history WHERE date(created_at) = date('now', 'localtime')")
            conn.commit()
        
        logger.info("🔧 [DEBUG] 已重置今日上传记录")
        return {"success": True, "message": "今日上传计数已重置"}
    except Exception as e:
        logger.error(f"❌ [DEBUG] 重置上传计数失败: {e}")
        return {"success": False, "error": str(e)}


@router.post("/quick-login")
async def quick_login(
    request: Request, 
    username: str = "test", 
    password: str = "test"
) -> Dict[str, str]:
    """
    [DEBUG] 快速登录/注册测试账号
    
    自动创建或登录测试账号，跳过邮箱验证等流程。
    仅在调试模式下可用。
    
    Args:
        request: HTTP请求对象
        username: 测试用户名，默认"test"
        password: 测试密码，默认"test"
    
    Returns:
        Dict[str, str]: 登录凭证
            - access_token: JWT访问令牌
            - token_type: 令牌类型 ("bearer")
            - username: 用户名
    
    Raises:
        HTTPException (403): 调试模式未启用
    
    Example:
        >>> POST /debug/quick-login?username=dev&password=dev123
    """
    require_debug_mode()
    
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
    
    logger.info(f"🔧 [DEBUG] 快速登录成功: {username}")
    return {"access_token": access_token, "token_type": "bearer", "username": user['username']}


@router.post("/toggle-vip")
async def toggle_vip(
    current_user: dict = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    [DEBUG] 快速切换当前用户的 VIP 状态
    
    在普通用户和VIP用户之间切换，方便测试VIP功能。
    仅在调试模式下可用。
    
    Args:
        current_user: 当前登录用户
    
    Returns:
        Dict[str, Any]: 切换结果
            - success: 是否成功
            - is_vip: 新的VIP状态
            - message: 提示信息
    
    Raises:
        HTTPException (403): 调试模式未启用
        HTTPException (401): 用户未登录
    
    Example:
        >>> POST /debug/toggle-vip
        >>> {"success": true, "is_vip": true, "message": "VIP 已开启"}
    """
    require_debug_mode()
    
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
        logger.error(f"❌ [DEBUG] 切换VIP失败: {e}")
        return {"success": False, "error": str(e)}
