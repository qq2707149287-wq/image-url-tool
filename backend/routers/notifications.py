# -*- coding: utf-8 -*-
"""
通知路由模块

提供用户通知的获取、标记已读功能，以及侵权举报接口。
"""
import logging
from typing import Dict, Any, List, Optional

from fastapi import APIRouter, HTTPException, Request, Depends
from pydantic import BaseModel

from .. import database
from ..config import DEVICE_ID_COOKIE_NAME
from ..routers.auth import get_current_user_optional

# 设置日志记录器
logger = logging.getLogger(__name__)

# 创建路由器
router = APIRouter(prefix="/api", tags=["通知"])


class ReportRequest(BaseModel):
    """侵权举报请求模型"""
    image_hash: Optional[str] = None
    image_url: Optional[str] = None
    reason: str
    contact: Optional[str] = None


@router.get("/notifications")
async def get_notifications(
    request: Request,
    unread: bool = False,
    current_user: Optional[dict] = Depends(get_current_user_optional)
) -> Dict[str, List[Dict[str, Any]]]:
    """
    获取当前用户的通知列表
    
    根据用户登录状态或设备ID获取相关通知。
    支持只获取未读通知。
    
    Args:
        request: HTTP请求对象
        unread: 是否只返回未读通知，默认False返回全部
        current_user: 当前登录用户（可选）
    
    Returns:
        Dict[str, List]: 包含通知列表
            - notifications: 通知对象数组
    
    Example:
        >>> # 获取所有通知
        >>> GET /api/notifications
        >>> # 只获取未读通知
        >>> GET /api/notifications?unread=true
    """
    user_id = current_user.get("id") if current_user else None
    device_id = request.cookies.get(DEVICE_ID_COOKIE_NAME)
    
    if not user_id and not device_id:
        return {"notifications": []}
    
    notifications = database.get_notifications(
        user_id=user_id, 
        device_id=device_id, 
        unread_only=unread
    )
    
    logger.debug(f"📬 获取通知: user={user_id}, device={device_id[:8] if device_id else None}..., count={len(notifications)}")
    
    return {"notifications": notifications}


@router.post("/notifications/{notification_id}/read")
async def mark_notification_read(
    notification_id: int,
    current_user: Optional[dict] = Depends(get_current_user_optional)
) -> Dict[str, bool]:
    """
    标记通知为已读
    
    将指定ID的通知标记为已读状态。
    
    Args:
        notification_id: 通知的唯一ID
        current_user: 当前登录用户（可选）
    
    Returns:
        Dict[str, bool]: 操作结果
            - success: 是否成功
    """
    success = database.mark_notification_read(notification_id)
    
    if success:
        logger.info(f"✅ 通知已读: id={notification_id}")
    else:
        logger.warning(f"⚠️ 标记通知失败: id={notification_id}")
    
    return {"success": success}


@router.post("/report")
async def submit_report(
    request: Request,
    data: ReportRequest,
    current_user: Optional[dict] = Depends(get_current_user_optional)
) -> Dict[str, Any]:
    """
    提交侵权举报
    
    用户可以通过此接口举报违规图片内容。
    支持通过图片hash或URL进行举报。
    
    Args:
        request: HTTP请求对象
        data: 举报请求数据
            - image_hash: 图片哈希值（可选）
            - image_url: 图片URL（可选）
            - reason: 举报原因（必填）
            - contact: 联系方式（可选）
        current_user: 当前登录用户（可选）
    
    Returns:
        Dict[str, Any]: 举报结果
            - success: 是否成功
            - message: 提示信息
    
    Raises:
        HTTPException (500): 举报提交失败
    
    Example:
        >>> data = {"image_hash": "abc123", "reason": "侵权内容", "contact": "email@example.com"}
        >>> POST /api/report
    """
    user_id = current_user.get("id") if current_user else None
    device_id = request.cookies.get(DEVICE_ID_COOKIE_NAME)
    
    success = database.create_abuse_report(
        image_hash=data.image_hash,
        image_url=data.image_url,
        reporter_id=user_id,
        reporter_device=device_id,
        reporter_contact=data.contact,
        reason=data.reason
    )
    
    if success:
        logger.info(f"📢 收到举报: hash={data.image_hash}, reason={data.reason[:20]}...")
        return {"success": True, "message": "感谢您的举报，我们会尽快处理"}
    else:
        logger.error(f"❌ 举报提交失败: 数据库操作错误")
        raise HTTPException(status_code=500, detail="举报提交失败")
