# backend/db/users.py
# 用户相关数据库操作 - 喵～这里是用户管理的大本营

import sqlite3
import logging
from typing import Dict, Any, Optional
from datetime import datetime
from .connection import get_db_connection

logger = logging.getLogger(__name__)


def create_user(username: str, password_hash: str) -> bool:
    """创建新用户"""
    try:
        with get_db_connection() as conn:
            with conn:
                c = conn.cursor()
                c.execute("INSERT INTO users (username, password_hash) VALUES (?, ?)", (username, password_hash))
            return True
    except sqlite3.IntegrityError:
        return False  # 用户名已存在
    except Exception as e:
        logger.error(f"创建用户失败: {e}")
        return False


def get_user_by_username(username: str) -> Optional[Dict[str, Any]]:
    """根据用户名查找用户"""
    try:
        with get_db_connection() as conn:
            conn.row_factory = sqlite3.Row
            c = conn.cursor()
            c.execute("SELECT * FROM users WHERE username = ?", (username,))
            row = c.fetchone()
            if row:
                return dict(row)
            return None
    except Exception as e:
        logger.error(f"查找用户失败: {e}")
        return None


def get_user_by_google_id(google_id: str) -> Optional[Dict[str, Any]]:
    """通过 Google ID 获取用户"""
    try:
        with get_db_connection() as conn:
            conn.row_factory = sqlite3.Row
            c = conn.cursor()
            c.execute("SELECT * FROM users WHERE google_id = ?", (google_id,))
            row = c.fetchone()
            if row:
                return dict(row)
    except Exception as e:
        logger.error(f"Failed to get user by google id: {e}")
    return None


def create_google_user(username: str, google_id: str, avatar: str) -> bool:
    """创建 Google 用户 (无需密码)"""
    try:
        with get_db_connection() as conn:
            with conn:
                c = conn.cursor()
                c.execute("INSERT INTO users (username, password_hash, google_id, avatar) VALUES (?, ?, ?, ?)", 
                          (username, "GOOGLE_LOGIN", google_id, avatar))
            return True
    except Exception as e:
        logger.error(f"Create google user failed: {e}")
        return False


def get_user_by_email(email: str) -> Optional[Dict[str, Any]]:
    """根据邮箱查找用户"""
    try:
        with get_db_connection() as conn:
            c = conn.cursor()
            c.execute("SELECT * FROM users WHERE email=?", (email,))
            row = c.fetchone()
            if row:
                columns = [col[0] for col in c.description]
                return dict(zip(columns, row))
            return None
    except Exception as e:
        logger.error(f"Get user by email failed: {e}")
        return None


def save_verification_code(email: str, code: str, type: str, expires_at: datetime) -> bool:
    """保存验证码"""
    try:
        with get_db_connection() as conn:
            with conn:
                c = conn.cursor()
                c.execute("DELETE FROM verification_codes WHERE email=? AND type=?", (email, type))
                c.execute("INSERT INTO verification_codes (email, code, type, expires_at) VALUES (?, ?, ?, ?)", (email, code, type, expires_at))
            return True
    except Exception as e:
        logger.error(f"Save verification code failed: {e}")
        return False


def get_valid_verification_code(email: str, type: str) -> Optional[str]:
    """获取有效的验证码"""
    try:
        with get_db_connection() as conn:
            c = conn.cursor()
            now = datetime.now()
            c.execute("SELECT code FROM verification_codes WHERE email=? AND type=? AND expires_at > ? ORDER BY created_at DESC LIMIT 1", (email, type, now))
            row = c.fetchone()
            return row[0] if row else None
    except Exception as e:
        logger.error(f"Get verification code failed: {e}")
        return None


def delete_verification_code(email: str, type: str) -> bool:
    """删除已使用的验证码"""
    try:
        with get_db_connection() as conn:
            with conn:
                c = conn.cursor()
                c.execute("DELETE FROM verification_codes WHERE email=? AND type=?", (email, type))
            return True
    except Exception as e:
        logger.error(f"Delete verification code failed: {e}")
        return False


def update_user_password(email: str, hashed_password: str) -> bool:
    """通过邮箱更新密码"""
    try:
        with get_db_connection() as conn:
            with conn:
                c = conn.cursor()
                c.execute("UPDATE users SET password_hash=? WHERE email=?", (hashed_password, email))
            return True
    except Exception as e:
        logger.error(f"Update password failed: {e}")
        return False


def create_email_user(username: str, email: str, password_hash: str) -> bool:
    """创建邮箱用户"""
    try:
        with get_db_connection() as conn:
            with conn:
                c = conn.cursor()
                c.execute("INSERT INTO users (username, email, password_hash) VALUES (?, ?, ?)", (username, email, password_hash))
            return True
    except sqlite3.IntegrityError:
        return False


def update_user_password_by_id(user_id: int, hashed_password: str) -> bool:
    """通过用户ID更新密码"""
    try:
        with get_db_connection() as conn:
            with conn:
                c = conn.cursor()
                c.execute("UPDATE users SET password_hash=? WHERE id=?", (hashed_password, user_id))
            return True
    except Exception as e:
        logger.error(f"Update password by ID failed: {e}")
        return False


def update_username(user_id: int, new_username: str) -> bool:
    """更新用户名"""
    try:
        with get_db_connection() as conn:
            with conn:
                c = conn.cursor()
                c.execute("UPDATE users SET username=? WHERE id=?", (new_username, user_id))
            return True
    except Exception as e:
        logger.error(f"Update username failed: {e}")
        return False


def delete_user(user_id: int) -> bool:
    """删除用户"""
    try:
        with get_db_connection() as conn:
            with conn:
                c = conn.cursor()
                c.execute("DELETE FROM users WHERE id=?", (user_id,))
            return True
    except Exception as e:
        logger.error(f"Delete user failed: {e}")
        return False


def delete_user_history(user_id: int) -> bool:
    """删除用户所有历史记录"""
    try:
        with get_db_connection() as conn:
            with conn:
                c = conn.cursor()
                c.execute("DELETE FROM history WHERE user_id=?", (user_id,))
            return True
    except Exception as e:
        logger.error(f"Delete user history failed: {e}")
        return False


def get_user_stats(user_id: int) -> Dict[str, Any]:
    """获取用户统计信息"""
    try:
        with get_db_connection() as conn:
            c = conn.cursor()
            # 总上传数
            c.execute("SELECT COUNT(*) FROM history WHERE user_id=?", (user_id,))
            total_uploads = c.fetchone()[0]
            # 总大小
            c.execute("SELECT SUM(size) FROM history WHERE user_id=?", (user_id,))
            total_size = c.fetchone()[0] or 0
            return {
                "total_uploads": total_uploads,
                "total_size": total_size
            }
    except Exception as e:
        logger.error(f"Get user stats failed: {e}")
        return {"total_uploads": 0, "total_size": 0}


def log_user_activity(user_id: int, action: str, ip_address: str = None, user_agent: str = None) -> bool:
    """记录用户活动"""
    try:
        with get_db_connection() as conn:
            with conn:
                c = conn.cursor()
                c.execute("INSERT INTO user_logs (user_id, action, ip_address, user_agent) VALUES (?, ?, ?, ?)",
                          (user_id, action, ip_address, user_agent))
            return True
    except Exception as e:
        logger.error(f"Log user activity failed: {e}")
        return False


def get_user_logs(user_id: int, limit: int = 10) -> list:
    """获取用户最近的活动日志"""
    try:
        with get_db_connection() as conn:
            conn.row_factory = sqlite3.Row
            c = conn.cursor()
            c.execute("SELECT * FROM user_logs WHERE user_id=? ORDER BY created_at DESC LIMIT ?", (user_id, limit))
            return [dict(row) for row in c.fetchall()]
    except Exception as e:
        logger.error(f"Get user logs failed: {e}")
        return []


def set_user_vip(username: str, is_vip: bool) -> bool:
    """设置用户 VIP 状态"""
    try:
        with get_db_connection() as conn:
            with conn:
                c = conn.cursor()
                c.execute("UPDATE users SET is_vip=? WHERE username=?", (1 if is_vip else 0, username))
            return True
    except Exception as e:
        logger.error(f"Set user VIP failed: {e}")
        return False


def set_user_admin(username: str, is_admin: bool) -> bool:
    """设置用户管理员状态"""
    try:
        with get_db_connection() as conn:
            with conn:
                c = conn.cursor()
                c.execute("UPDATE users SET is_admin=? WHERE username=?", (1 if is_admin else 0, username))
            return True
    except Exception as e:
        logger.error(f"Set user admin failed: {e}")
        return False
