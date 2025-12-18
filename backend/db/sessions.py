# backend/db/sessions.py
# 会话管理数据库操作 - 喵～这里是设备管理的大本营

import sqlite3
import logging
import uuid
from typing import Dict, Any, List, Optional
from .connection import get_db_connection

logger = logging.getLogger(__name__)


def create_session(user_id: int, device_info: str = None, ip_address: str = None) -> str:
    """创建新的用户会话"""
    try:
        session_id = str(uuid.uuid4())
        with get_db_connection() as conn:
            c = conn.cursor()
            c.execute("INSERT INTO user_sessions (user_id, session_id, device_info, ip_address) VALUES (?, ?, ?, ?)",
                      (user_id, session_id, device_info, ip_address))
            conn.commit()
            return session_id
    except Exception as e:
        logger.error(f"Create session failed: {e}")
        return None


def get_active_sessions(user_id: int) -> List[Dict[str, Any]]:
    """获取用户的所有活跃会话"""
    try:
        with get_db_connection() as conn:
            conn.row_factory = sqlite3.Row
            c = conn.cursor()
            c.execute("SELECT * FROM user_sessions WHERE user_id=? ORDER BY last_active DESC", (user_id,))
            return [dict(row) for row in c.fetchall()]
    except Exception as e:
        logger.error(f"Get active sessions failed: {e}")
        return []


def revoke_session(session_id: str, user_id: int) -> bool:
    """注销会话"""
    try:
        with get_db_connection() as conn:
            c = conn.cursor()
            c.execute("DELETE FROM user_sessions WHERE session_id=? AND user_id=?", (session_id, user_id))
            conn.commit()
            return c.rowcount > 0
    except Exception as e:
        logger.error(f"Revoke session failed: {e}")
        return False


def validate_session(session_id: str) -> Optional[Dict[str, Any]]:
    """验证会话是否有效"""
    try:
        with get_db_connection() as conn:
            conn.row_factory = sqlite3.Row
            c = conn.cursor()
            c.execute("SELECT * FROM user_sessions WHERE session_id=?", (session_id,))
            row = c.fetchone()
            return dict(row) if row else None
    except Exception as e:
        logger.error(f"Validate session failed: {e}")
        return None


def update_session_activity(session_id: str) -> bool:
    """更新会话最后活跃时间"""
    try:
        with get_db_connection() as conn:
            c = conn.cursor()
            c.execute("UPDATE user_sessions SET last_active=CURRENT_TIMESTAMP WHERE session_id=?", (session_id,))
            conn.commit()
            return True
    except Exception as e:
        logger.error(f"Update session activity failed: {e}")
        return False
