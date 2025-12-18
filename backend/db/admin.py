# backend/db/admin.py
# 管理员功能数据库操作 - 喵～这里是管理员的秘密基地

import os
import sqlite3
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
from .connection import get_db_connection

logger = logging.getLogger(__name__)


def get_admin_stats() -> Dict[str, Any]:
    """获取管理后台统计数据"""
    try:
        with get_db_connection() as conn:
            c = conn.cursor()
            
            # 总图片数
            c.execute("SELECT COUNT(*) FROM history")
            total_images = c.fetchone()[0]
            
            # 总用户数
            c.execute("SELECT COUNT(*) FROM users")
            total_users = c.fetchone()[0]
            
            # VIP 用户数
            c.execute("SELECT COUNT(*) FROM users WHERE is_vip=1")
            vip_users = c.fetchone()[0]
            
            # 今日上传数
            today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            c.execute("SELECT COUNT(*) FROM history WHERE created_at >= ?", (today,))
            today_uploads = c.fetchone()[0]
            
            # 待处理举报数
            c.execute("SELECT COUNT(*) FROM abuse_reports WHERE status='pending'")
            pending_reports = c.fetchone()[0]
            
            return {
                "total_images": total_images,
                "total_users": total_users,
                "vip_users": vip_users,
                "today_uploads": today_uploads,
                "pending_reports": pending_reports
            }
    except Exception as e:
        logger.error(f"Get admin stats failed: {e}")
        return {}


def create_abuse_report(image_hash: str = None, image_url: str = None, reason: str = "", 
                        reporter_id: int = None, reporter_device: str = None, reporter_contact: str = None) -> bool:
    """创建举报记录"""
    try:
        with get_db_connection() as conn:
            c = conn.cursor()
            c.execute("""INSERT INTO abuse_reports 
                        (image_hash, image_url, reason, reporter_id, reporter_device, reporter_contact) 
                        VALUES (?, ?, ?, ?, ?, ?)""",
                      (image_hash, image_url, reason, reporter_id, reporter_device, reporter_contact))
            conn.commit()
            return True
    except Exception as e:
        logger.error(f"Create abuse report failed: {e}")
        return False


def get_abuse_reports(page: int = 1, page_size: int = 50, status: str = None) -> Dict[str, Any]:
    """获取举报列表 (支持分页和状态筛选)"""
    try:
        with get_db_connection() as conn:
            conn.row_factory = sqlite3.Row
            c = conn.cursor()
            
            offset = (page - 1) * page_size
            
            query = "SELECT * FROM abuse_reports"
            params = []
            
            if status:
                query += " WHERE status = ?"
                params.append(status)
            
            query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
            params.extend([page_size, offset])
            
            c.execute(query, params)
            data = [dict(row) for row in c.fetchall()]
            
            # 获取总数
            count_query = "SELECT COUNT(*) FROM abuse_reports"
            count_params = []
            if status:
                count_query += " WHERE status = ?"
                count_params.append(status)
            
            c.execute(count_query, count_params)
            total = c.fetchone()[0]
            
            return {"data": data, "total": total, "page": page, "page_size": page_size}
    except Exception as e:
        logger.error(f"Get abuse reports failed: {e}")
        return {"data": [], "total": 0}


def resolve_abuse_report(report_id: int, admin_notes: str = None) -> bool:
    """标记举报为已处理"""
    try:
        with get_db_connection() as conn:
            c = conn.cursor()
            c.execute("UPDATE abuse_reports SET status='resolved', admin_notes=?, resolved_at=CURRENT_TIMESTAMP WHERE id=?",
                      (admin_notes, report_id))
            conn.commit()
            return c.rowcount > 0
    except Exception as e:
        logger.error(f"Resolve abuse report failed: {e}")
        return False


def get_pending_reports_count() -> int:
    """获取待处理举报数量"""
    try:
        with get_db_connection() as conn:
            c = conn.cursor()
            c.execute("SELECT COUNT(*) FROM abuse_reports WHERE status='pending'")
            return c.fetchone()[0]
    except Exception as e:
        logger.error(f"Get pending reports count failed: {e}")
        return 0


def batch_resolve_reports(report_ids: List[int], admin_notes: str = None) -> Dict[str, Any]:
    """批量标记多条举报为已处理"""
    try:
        if not report_ids:
            return {"success": True, "resolved_count": 0}
        
        with get_db_connection() as conn:
            c = conn.cursor()
            placeholders = ','.join('?' * len(report_ids))
            params = [admin_notes] + report_ids
            
            c.execute(f"UPDATE abuse_reports SET status='resolved', admin_notes=?, resolved_at=CURRENT_TIMESTAMP WHERE id IN ({placeholders})",
                      params)
            count = c.rowcount
            conn.commit()
            return {"success": True, "resolved_count": count}
    except Exception as e:
        logger.error(f"Batch resolve reports failed: {e}")
        return {"success": False, "error": str(e)}


def batch_delete_images_by_hashes(hashes: List[str]) -> Dict[str, Any]:
    """批量删除多张图片的数据库记录"""
    try:
        if not hashes:
            return {"success": True, "deleted_count": 0, "failed_hashes": []}
        
        deleted_count = 0
        failed_hashes = []
        
        with get_db_connection() as conn:
            c = conn.cursor()
            for h in hashes:
                try:
                    c.execute("DELETE FROM history WHERE hash = ?", (h,))
                    if c.rowcount > 0:
                        deleted_count += 1
                    else:
                        failed_hashes.append(h)
                except Exception as e:
                    logger.error(f"Delete hash {h} failed: {e}")
                    failed_hashes.append(h)
            conn.commit()
        
        return {"success": True, "deleted_count": deleted_count, "failed_hashes": failed_hashes}
    except Exception as e:
        logger.error(f"Batch delete images failed: {e}")
        return {"success": False, "error": str(e), "deleted_count": 0, "failed_hashes": hashes}


def create_auto_admin() -> bool:
    """
    从环境变量自动创建管理员账户 (仅在应用启动时调用一次)
    
    环境变量:
        AUTO_ADMIN_USERNAME: 管理员用户名
        AUTO_ADMIN_PASSWORD: 管理员密码 (明文，会自动哈希)
    """
    username = os.getenv("AUTO_ADMIN_USERNAME")
    password = os.getenv("AUTO_ADMIN_PASSWORD")
    
    if not username or not password:
        logger.info("ℹ️ 未配置自动管理员环境变量，跳过")
        return False
    
    try:
        with get_db_connection() as conn:
            c = conn.cursor()
            
            # 检查用户是否已存在
            c.execute("SELECT id, is_admin FROM users WHERE username = ?", (username,))
            row = c.fetchone()
            
            if row:
                user_id, is_admin = row
                if is_admin:
                    logger.info(f"✅ 管理员 {username} 已存在")
                else:
                    # 用户存在但不是管理员，升级权限
                    c.execute("UPDATE users SET is_admin = 1 WHERE id = ?", (user_id,))
                    conn.commit()
                    logger.info(f"✅ 已将 {username} 升级为管理员")
                return True
            
            # 创建新管理员
            # 注意：这里需要哈希密码，但为了避免循环导入，我们使用简单的方式
            # 实际哈希应该在调用方完成
            from passlib.context import CryptContext
            pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
            hashed_password = pwd_context.hash(password)
            
            c.execute("INSERT INTO users (username, password_hash, is_admin) VALUES (?, ?, 1)",
                      (username, hashed_password))
            conn.commit()
            logger.info(f"✅ 已创建管理员账户: {username}")
            return True
            
    except Exception as e:
        logger.error(f"❌ 创建自动管理员失败: {e}")
        return False
