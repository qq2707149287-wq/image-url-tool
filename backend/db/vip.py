# -*- coding: utf-8 -*-
# backend/db/vip.py
# VIP 系统数据库操作 - 喵～这里是 VIP 大本营

import sqlite3
import logging
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
from .connection import get_db_connection

logger = logging.getLogger(__name__)

def generate_vip_code_str(length: int = 16) -> str:
    """生成格式化的 VIP 激活码 (XXXX-XXXX-XXXX-XXXX)"""
    import secrets
    import string
    chars = string.ascii_uppercase + string.digits
    raw = ''.join(secrets.choice(chars) for _ in range(length))
    return '-'.join(raw[i:i+4] for i in range(0, length, 4))



def activate_vip(user_id: int, code: str) -> Dict[str, Any]:
    """激活 VIP"""
    try:
            with get_db_connection() as conn:
                with conn:
                    c = conn.cursor()
                    
                    # 检查激活码是否存在且未使用
                    c.execute("SELECT id, days FROM vip_codes WHERE code=? AND is_used=0", (code,))
                    row = c.fetchone()
                    if not row:
                        return {"success": False, "error": "激活码无效或已被使用"}
                    
                    code_id, days = row
                    
                    # 获取当前用户信息
                    c.execute("SELECT is_vip, vip_expiry FROM users WHERE id=?", (user_id,))
                    user_row = c.fetchone()
                    if not user_row:
                        return {"success": False, "error": "用户不存在"}
                    
                    is_vip, vip_expiry = user_row
                    
                    # 计算新的过期时间
                    now = datetime.now()
                    if is_vip and vip_expiry:
                        # 如果已经是 VIP，在现有基础上延长
                        try:
                            current_expiry = datetime.fromisoformat(vip_expiry) if isinstance(vip_expiry, str) else vip_expiry
                            if current_expiry > now:
                                new_expiry = current_expiry + timedelta(days=days)
                            else:
                                new_expiry = now + timedelta(days=days)
                        except:
                            new_expiry = now + timedelta(days=days)
                    else:
                        new_expiry = now + timedelta(days=days)
                    
                    # 更新用户 VIP 状态
                    c.execute("UPDATE users SET is_vip=1, vip_expiry=? WHERE id=?", (new_expiry.isoformat(), user_id))
                    
                    # 标记激活码已使用
                    c.execute("UPDATE vip_codes SET is_used=1, used_by=?, used_at=CURRENT_TIMESTAMP WHERE id=?", (user_id, code_id))
            return {"success": True, "days": days, "expiry": new_expiry.isoformat()}
    except Exception as e:
        logger.error(f"Activate VIP failed: {e}")
        return {"success": False, "error": str(e)}


def create_vip_code(code: str, days: int) -> bool:
    """创建 VIP 激活码 (管理员用)"""
    try:
        with get_db_connection() as conn:
            with conn:
                c = conn.cursor()
                c.execute("INSERT INTO vip_codes (code, days) VALUES (?, ?)", (code, days))
            return True
    except Exception as e:
        logger.error(f"Create VIP code failed: {e}")
        return False


def get_today_upload_count(user_id: int = None, device_id: str = None, ip_address: str = None) -> int:
    """
    获取今日上传数量。
    如果是登录用户，按 user_id 统计。
    如果是匿名用户，按 ip_address 或 device_id 统计
    """
    try:
        with get_db_connection() as conn:
            c = conn.cursor()
            
            # 获取今天的开始时间
            today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            
            if user_id:
                # 登录用户：按 user_id 统计
                c.execute("SELECT COUNT(*) FROM history WHERE user_id=? AND created_at >= ?", (user_id, today))
            elif ip_address:
                # 匿名用户：优先按 IP 统计
                c.execute("SELECT COUNT(*) FROM history WHERE ip_address=? AND user_id IS NULL AND created_at >= ?", (ip_address, today))
            elif device_id:
                # 降级：按 device_id 统计
                c.execute("SELECT COUNT(*) FROM history WHERE device_id=? AND user_id IS NULL AND created_at >= ?", (device_id, today))
            else:
                return 0
            
            return c.fetchone()[0]
    except Exception as e:
        logger.error(f"Get today upload count failed: {e}")
        return 0
