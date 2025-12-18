# backend/db/notifications.py
# 通知系统数据库操作 - 喵～这里是消息通知的大本营

import sqlite3
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from .connection import get_db_connection

logger = logging.getLogger(__name__)


def create_notification(user_id: int = None, device_id: str = None, 
                        type: str = "system", title: str = None, message: str = "") -> bool:
    """创建用户通知"""
    try:
        with get_db_connection() as conn:
            c = conn.cursor()
            c.execute("INSERT INTO user_notifications (user_id, device_id, type, title, message) VALUES (?, ?, ?, ?, ?)",
                      (user_id, device_id, type, title, message))
            conn.commit()
            return True
    except Exception as e:
        logger.error(f"Create notification failed: {e}")
        return False


def get_notifications(user_id: int = None, device_id: str = None, unread_only: bool = False) -> List[Dict[str, Any]]:
    """获取用户通知列表"""
    try:
        with get_db_connection() as conn:
            conn.row_factory = sqlite3.Row
            c = conn.cursor()
            
            conditions = []
            params = []
            
            if user_id:
                conditions.append("user_id = ?")
                params.append(user_id)
            elif device_id:
                conditions.append("device_id = ?")
                params.append(device_id)
            else:
                return []
            
            if unread_only:
                conditions.append("is_read = 0")
            
            query = "SELECT * FROM user_notifications"
            if conditions:
                query += " WHERE " + " AND ".join(conditions)
            query += " ORDER BY created_at DESC LIMIT 50"
            
            c.execute(query, params)
            return [dict(row) for row in c.fetchall()]
    except Exception as e:
        logger.error(f"Get notifications failed: {e}")
        return []


def mark_notification_read(notification_id: int) -> bool:
    """标记通知为已读"""
    try:
        with get_db_connection() as conn:
            c = conn.cursor()
            c.execute("UPDATE user_notifications SET is_read=1 WHERE id=?", (notification_id,))
            conn.commit()
            return True
    except Exception as e:
        logger.error(f"Mark notification read failed: {e}")
        return False


def cleanup_old_notifications(days: int = 7) -> int:
    """清理超过指定天数的通知"""
    try:
        with get_db_connection() as conn:
            c = conn.cursor()
            cutoff = datetime.now() - timedelta(days=days)
            c.execute("DELETE FROM user_notifications WHERE created_at < ?", (cutoff,))
            count = c.rowcount
            conn.commit()
            logger.info(f"🧹 清理了 {count} 条过期通知")
            return count
    except Exception as e:
        logger.error(f"Cleanup old notifications failed: {e}")
        return 0
