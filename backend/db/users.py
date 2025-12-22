# -*- coding: utf-8 -*-
"""
backend/db/users.py
用户相关数据库操作

异常处理最佳实践说明：
1. 优先捕获具体的 sqlite3 异常类型（IntegrityError, OperationalError 等）
2. 在最后使用 Exception 作为兜底，防止未预期的错误导致程序崩溃
3. 日志记录应包含足够的上下文信息以便排查问题
4. 返回值语义应保持一致（成功/失败/None）
"""

import sqlite3
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime
from .connection import get_db_connection

logger = logging.getLogger(__name__)


# ==================== 用户创建与查询 ====================

def create_user(username: str, password_hash: str) -> bool:
    """
    创建新用户
    
    Returns:
        bool: 创建成功返回 True，用户名重复或其他错误返回 False
    """
    try:
        with get_db_connection() as conn:
            with conn:
                c = conn.cursor()
                c.execute("INSERT INTO users (username, password_hash) VALUES (?, ?)", (username, password_hash))
            return True
    except sqlite3.IntegrityError:
        # 用户名已存在（唯一约束冲突）
        logger.warning(f"创建用户失败: 用户名 '{username}' 已存在")
        return False
    except sqlite3.OperationalError as e:
        # 数据库操作错误（锁定、表不存在等）
        logger.error(f"创建用户时数据库操作错误: {e}")
        return False
    except Exception as e:
        # 兜底：其他未预期的错误
        logger.error(f"创建用户时发生未知错误: {e}")
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
    except sqlite3.OperationalError as e:
        logger.error(f"查找用户时数据库操作错误: {e}")
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
    except sqlite3.OperationalError as e:
        logger.error(f"通过 Google ID 查找用户时数据库操作错误: {e}")
    except Exception as e:
        logger.error(f"通过 Google ID 查找用户失败: {e}")
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
    except sqlite3.IntegrityError:
        logger.warning(f"创建 Google 用户失败: 用户名 '{username}' 或 Google ID 已存在")
        return False
    except sqlite3.OperationalError as e:
        logger.error(f"创建 Google 用户时数据库操作错误: {e}")
        return False
    except Exception as e:
        logger.error(f"创建 Google 用户时发生未知错误: {e}")
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
    except sqlite3.OperationalError as e:
        logger.error(f"通过邮箱查找用户时数据库操作错误: {e}")
        return None
    except Exception as e:
        logger.error(f"通过邮箱查找用户失败: {e}")
        return None


# ==================== 验证码管理 ====================

def save_verification_code(email: str, code: str, type: str, expires_at: datetime) -> bool:
    """保存验证码"""
    try:
        with get_db_connection() as conn:
            with conn:
                c = conn.cursor()
                c.execute("DELETE FROM verification_codes WHERE email=? AND type=?", (email, type))
                c.execute("INSERT INTO verification_codes (email, code, type, expires_at) VALUES (?, ?, ?, ?)", (email, code, type, expires_at))
            return True
    except sqlite3.OperationalError as e:
        logger.error(f"保存验证码时数据库操作错误: {e}")
        return False
    except Exception as e:
        logger.error(f"保存验证码失败: {e}")
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
    except sqlite3.OperationalError as e:
        logger.error(f"获取验证码时数据库操作错误: {e}")
        return None
    except Exception as e:
        logger.error(f"获取验证码失败: {e}")
        return None


def delete_verification_code(email: str, type: str) -> bool:
    """删除已使用的验证码"""
    try:
        with get_db_connection() as conn:
            with conn:
                c = conn.cursor()
                c.execute("DELETE FROM verification_codes WHERE email=? AND type=?", (email, type))
            return True
    except sqlite3.OperationalError as e:
        logger.error(f"删除验证码时数据库操作错误: {e}")
        return False
    except Exception as e:
        logger.error(f"删除验证码失败: {e}")
        return False


# ==================== 用户信息更新 ====================

def update_user_password(email: str, hashed_password: str) -> bool:
    """通过邮箱更新密码"""
    try:
        with get_db_connection() as conn:
            with conn:
                c = conn.cursor()
                c.execute("UPDATE users SET password_hash=? WHERE email=?", (hashed_password, email))
            return True
    except sqlite3.OperationalError as e:
        logger.error(f"更新密码时数据库操作错误: {e}")
        return False
    except Exception as e:
        logger.error(f"更新密码失败: {e}")
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
        logger.warning(f"创建邮箱用户失败: 用户名 '{username}' 或邮箱 '{email}' 已存在")
        return False
    except sqlite3.OperationalError as e:
        logger.error(f"创建邮箱用户时数据库操作错误: {e}")
        return False
    except Exception as e:
        logger.error(f"创建邮箱用户时发生未知错误: {e}")
        return False


def update_user_password_by_id(user_id: int, hashed_password: str) -> bool:
    """通过用户ID更新密码"""
    try:
        with get_db_connection() as conn:
            with conn:
                c = conn.cursor()
                c.execute("UPDATE users SET password_hash=? WHERE id=?", (hashed_password, user_id))
            return True
    except sqlite3.OperationalError as e:
        logger.error(f"通过 ID 更新密码时数据库操作错误: {e}")
        return False
    except Exception as e:
        logger.error(f"通过 ID 更新密码失败: {e}")
        return False


def update_username(user_id: int, new_username: str) -> bool:
    """更新用户名"""
    try:
        with get_db_connection() as conn:
            with conn:
                c = conn.cursor()
                c.execute("UPDATE users SET username=? WHERE id=?", (new_username, user_id))
            return True
    except sqlite3.IntegrityError:
        logger.warning(f"更新用户名失败: 用户名 '{new_username}' 已被占用")
        return False
    except sqlite3.OperationalError as e:
        logger.error(f"更新用户名时数据库操作错误: {e}")
        return False
    except Exception as e:
        logger.error(f"更新用户名失败: {e}")
        return False


# ==================== 用户删除与统计 ====================

def delete_user(user_id: int) -> bool:
    """删除用户"""
    try:
        with get_db_connection() as conn:
            with conn:
                c = conn.cursor()
                c.execute("DELETE FROM users WHERE id=?", (user_id,))
            return True
    except sqlite3.OperationalError as e:
        logger.error(f"删除用户时数据库操作错误: {e}")
        return False
    except Exception as e:
        logger.error(f"删除用户失败: {e}")
        return False


def delete_user_history(user_id: int) -> bool:
    """删除用户所有历史记录"""
    try:
        with get_db_connection() as conn:
            with conn:
                c = conn.cursor()
                c.execute("DELETE FROM history WHERE user_id=?", (user_id,))
            return True
    except sqlite3.OperationalError as e:
        logger.error(f"删除用户历史记录时数据库操作错误: {e}")
        return False
    except Exception as e:
        logger.error(f"删除用户历史记录失败: {e}")
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
    except sqlite3.OperationalError as e:
        logger.error(f"获取用户统计信息时数据库操作错误: {e}")
        return {"total_uploads": 0, "total_size": 0}
    except Exception as e:
        logger.error(f"获取用户统计信息失败: {e}")
        return {"total_uploads": 0, "total_size": 0}


# ==================== 用户活动日志 ====================

def log_user_activity(user_id: int, action: str, ip_address: str = None, user_agent: str = None) -> bool:
    """记录用户活动"""
    try:
        with get_db_connection() as conn:
            with conn:
                c = conn.cursor()
                c.execute("INSERT INTO user_logs (user_id, action, ip_address, user_agent) VALUES (?, ?, ?, ?)",
                          (user_id, action, ip_address, user_agent))
            return True
    except sqlite3.OperationalError as e:
        logger.error(f"记录用户活动时数据库操作错误: {e}")
        return False
    except Exception as e:
        logger.error(f"记录用户活动失败: {e}")
        return False


def get_user_logs(user_id: int, limit: int = 10) -> List[Dict[str, Any]]:
    """获取用户最近的活动日志"""
    try:
        with get_db_connection() as conn:
            conn.row_factory = sqlite3.Row
            c = conn.cursor()
            c.execute("SELECT * FROM user_logs WHERE user_id=? ORDER BY created_at DESC LIMIT ?", (user_id, limit))
            return [dict(row) for row in c.fetchall()]
    except sqlite3.OperationalError as e:
        logger.error(f"获取用户活动日志时数据库操作错误: {e}")
        return []
    except Exception as e:
        logger.error(f"获取用户活动日志失败: {e}")
        return []


# ==================== 权限管理 ====================

def set_user_vip(username: str, is_vip: bool) -> bool:
    """设置用户 VIP 状态"""
    try:
        with get_db_connection() as conn:
            with conn:
                c = conn.cursor()
                c.execute("UPDATE users SET is_vip=? WHERE username=?", (1 if is_vip else 0, username))
            return True
    except sqlite3.OperationalError as e:
        logger.error(f"设置用户 VIP 状态时数据库操作错误: {e}")
        return False
    except Exception as e:
        logger.error(f"设置用户 VIP 状态失败: {e}")
        return False


def set_user_admin(username: str, is_admin: bool) -> bool:
    """设置用户管理员状态"""
    try:
        with get_db_connection() as conn:
            with conn:
                c = conn.cursor()
                c.execute("UPDATE users SET is_admin=? WHERE username=?", (1 if is_admin else 0, username))
            return True
    except sqlite3.OperationalError as e:
        logger.error(f"设置用户管理员状态时数据库操作错误: {e}")
        return False
    except Exception as e:
        logger.error(f"设置用户管理员状态失败: {e}")
        return False
