# backend/db/images.py
# 图片相关数据库操作 - 喵～这里是图片记录的大本营

import sqlite3
import logging
import time
from typing import List, Dict, Any, Optional
from .connection import get_db_connection

logger = logging.getLogger(__name__)


def save_to_db(file_info: dict, device_id: str = None, user_id: int = None, is_shared: bool = False, ip_address: str = None) -> dict:
    """保存图片元数据到数据库"""
    try:
        with get_db_connection() as conn:
            with conn:
                c = conn.cursor()
                
                data = file_info
                
                # 去重逻辑
                conditions = ["hash = ?"]
                params = [data.get("hash")]
                
                if is_shared:
                    conditions.append("is_shared = 1")
                else:
                    conditions.append("is_shared = 0")
                    if user_id:
                        conditions.append("user_id = ?")
                        params.append(user_id)
                    else:
                        conditions.append("device_id = ?")
                        params.append(device_id)

                query = "SELECT id FROM history WHERE " + " AND ".join(conditions)
                c.execute(query, params)
                row = c.fetchone()
                row_id = row[0] if row else None
                
                if row_id:
                    # 已存在 -> 更新
                    update_fields = '''UPDATE history SET url=?, filename=?, service=?, width=?, height=?, size=?, content_type=?, 
                                         created_at=CURRENT_TIMESTAMP'''
                    params = [data.get("url"), data.get("filename"), data.get("service"),
                              data.get("width"), data.get("height"), data.get("size"), data.get("content_type")]
                    
                    # 检查是否需要"认领"
                    should_claim = False
                    if is_shared and user_id:
                         c.execute("SELECT user_id FROM history WHERE id = ?", (row_id,))
                         existing_owner = c.fetchone()[0]
                         if existing_owner is None:
                             should_claim = True
                    
                    if should_claim:
                        update_fields += ", user_id=?"
                        params.append(user_id)
                        logger.info(f"👑 用户 {user_id} 认领了匿名图片 {data.get('hash')}")

                    update_fields += " WHERE id=?"
                    params.append(row_id)

                    c.execute(update_fields, params)
                else:
                    # 不存在 -> 插入新记录
                    c.execute('''INSERT INTO history (url, filename, hash, service, width, height, size, content_type, device_id, user_id, is_shared, ip_address)
                                 VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                              (data.get("url"), data.get("filename"), data.get("hash"), data.get("service"),
                               data.get("width"), data.get("height"), data.get("size"), data.get("content_type"),
                               device_id, user_id, 1 if is_shared else 0, ip_address))
                    row_id = c.lastrowid
                
            return {"success": True, "existing": bool(row_id is not None and c.lastrowid is None), "id": row_id}
    except Exception as e:
        logger.error(f"❌ 保存到数据库失败: {e}")
        return {"success": False, "error": str(e)}


def get_history_list(page: int = 1, page_size: int = 20, keyword: str = "",
                     device_id: str = None, user_id: int = None, is_admin: bool = False, view_mode: str = "private",
                     only_mine: bool = False) -> Dict[str, Any]:
    """查询历史记录，支持分页、搜索和权限过滤。"""
    try:
        with get_db_connection() as conn:
            conn.row_factory = sqlite3.Row
            c = conn.cursor()

            offset = (page - 1) * page_size
            
            query = "SELECT * FROM history"
            params: list = []
            conditions: list = []

            # 核心过滤逻辑
            if view_mode == "shared":
                conditions.append("is_shared = 1")
                if only_mine:
                    if user_id:
                        conditions.append("user_id = ?")
                        params.append(user_id)
                    elif device_id:
                        conditions.append("device_id = ?")
                        params.append(device_id)
            elif view_mode == "admin_all":
                pass 
            else:
                if user_id:
                    conditions.append("user_id = ?")
                    conditions.append("is_shared = 0")
                    params.append(user_id)
                else:
                    conditions.append("device_id = ?")
                    conditions.append("is_shared = 0")
                    conditions.append("user_id IS NULL")
                    params.append(device_id)

            if keyword:
                conditions.append("(filename LIKE ? OR url LIKE ?)")
                params.extend([f"%{keyword}%", f"%{keyword}%"])

            if conditions:
                query += " WHERE " + " AND ".join(conditions)

            query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
            params.extend([page_size, offset])

            c.execute(query, params)
            rows = c.fetchall()

            # 获取总条数
            count_query = "SELECT COUNT(*) FROM history"
            count_params: list = []
            count_conditions: list = []

            if view_mode == "shared":
                count_conditions.append("is_shared = 1")
                if only_mine:
                    if user_id:
                        count_conditions.append("user_id = ?")
                        count_params.append(user_id)
                    elif device_id:
                        count_conditions.append("device_id = ?")
                        count_params.append(device_id)
            elif view_mode == "admin_all":
                pass
            else:
                if user_id:
                    count_conditions.append("user_id = ?")
                    count_conditions.append("is_shared = 0")
                    count_params.append(user_id)
                else:
                    count_conditions.append("device_id = ?")
                    count_conditions.append("is_shared = 0")
                    count_conditions.append("user_id IS NULL")
                    count_params.append(device_id)

            if keyword:
                count_conditions.append("(filename LIKE ? OR url LIKE ?)")
                count_params.extend([f"%{keyword}%", f"%{keyword}%"])

            if count_conditions:
                count_query += " WHERE " + " AND ".join(count_conditions)

            c.execute(count_query, count_params)
            total = c.fetchone()[0]

            # 转换结果格式
            data = []
            for row in rows:
                item = dict(row)
                if is_admin:
                    item['is_mine'] = True
                elif user_id:
                    item['is_mine'] = (item['user_id'] == user_id) or (item['user_id'] is None)
                elif device_id:
                    item['is_mine'] = (item['device_id'] == device_id)
                else:
                    item['is_mine'] = False
                data.append(item)
            
            return {"success": True, "data": data, "total": total, "page": page, "page_size": page_size}
    except Exception as e:
        logger.error(f"获取历史记录失败: {e}")
        return {"success": False, "error": str(e)}


def delete_history_items(ids: List[int], device_id: str = None, user_id: int = None, is_admin: bool = False) -> Dict[str, Any]:
    """批量删除历史记录"""
    try:
        if not ids:
            return {"success": True, "count": 0}

        with get_db_connection() as conn:
            with conn:
                c = conn.cursor()
                placeholders = ','.join('?' * len(ids))
                
                query = f"DELETE FROM history WHERE id IN ({placeholders})"
                params = list(ids)
                
                if not is_admin:
                    if user_id:
                        query += " AND (user_id = ? OR user_id IS NULL)"
                        params.append(user_id)
                    elif device_id:
                        query += " AND device_id = ? AND user_id IS NULL"
                        params.append(device_id)
                    else:
                         return {"success": False, "error": "Missing auth info"}

                c.execute(query, params)
                count = c.rowcount
            return {"success": True, "count": count}
    except Exception as e:
        return {"success": False, "error": str(e)}


def clear_all_history(device_id: str = None, view_mode: str = "private", user_id: int = None, is_admin: bool = False) -> Dict[str, Any]:
    """清空当前模式下的所有历史记录"""
    try:
        with get_db_connection() as conn:
            with conn:
                c = conn.cursor()
                
                if view_mode == "shared":
                    query = "DELETE FROM history WHERE is_shared = 1"
                    params = []
                    
                    if not is_admin:
                        if user_id:
                            query += " AND (user_id = ? OR user_id IS NULL)"
                            params.append(user_id)
                        elif device_id:
                             query += " AND device_id = ? AND user_id IS NULL"
                             params.append(device_id)
                    
                    c.execute(query, params)
                else:
                    query = "DELETE FROM history WHERE is_shared = 0"
                    params = []

                    if not is_admin:
                         if user_id:
                             query += " AND user_id = ?"
                             params.append(user_id)
                         else:
                             query += " AND device_id = ? AND user_id IS NULL"
                             params.append(device_id)

                    c.execute(query, params)
                
            return {"success": True}
    except Exception as e:
        return {"success": False, "error": str(e)}


def rename_history_item(item_id: int, filename: str, device_id: str = None, user_id: int = None, is_admin: bool = False) -> Dict[str, Any]:
    """重命名历史记录 (通过 ID)"""
    try:
        with get_db_connection() as conn:
            with conn:
                c = conn.cursor()
                
                query = "UPDATE history SET filename = ? WHERE id = ?"
                params = [filename, item_id]
                
                if not is_admin:
                    if user_id:
                        query += " AND (user_id = ? OR user_id IS NULL)"
                        params.append(user_id)
                    elif device_id:
                        query += " AND device_id = ? AND user_id IS NULL"
                        params.append(device_id)
                    else:
                        return {"success": False, "error": "Missing auth info"}

                c.execute(query, params)
                if c.rowcount == 0:
                    # 如果未找到，抛出异常以触发回滚（尽管select rowcount不会改变数据，但保持逻辑一致）
                    # 不过这里直接返回错误信息更合适，因为可能只是没找到
                    # 如果不抛出异常，就不会回滚（虽然也没做修改）
                    pass
            
            # 这里的 check 放在 with block 外面或者里面都可以，因为 rowcount 已经确定
            # 但是由于 rowcount 检查是在 `execute` 后，如果放在 `exit` 之前，可以更早知道结果
            # 为了简单，保持原逻辑，只是去掉了 commit
            
            if c.rowcount == 0:
                 return {"success": False, "error": "Item not found or permission denied"}

            return {"success": True}
    except Exception as e:
        return {"success": False, "error": str(e)}


def delete_image_by_hash_system(file_hash: str) -> bool:
    """
    系统级物理删除图片记录 (用于 AI 违规清理)
    包含重试机制，防止数据库锁导致删除失败
    """
    max_retries = 3
    
    for attempt in range(max_retries):
        try:
            with get_db_connection() as conn:
                with conn:
                    c = conn.cursor()
                    logger.info(f"🗑️ [Database] 尝试删除 Hash 记录: {file_hash} (Attempt {attempt+1})")
                    
                    c.execute("SELECT count(*) FROM history WHERE hash = ?", (file_hash,))
                    count = c.fetchone()[0]
                    if count == 0:
                        logger.info(f"⚠️ [Database] 要删除的记录不存在(可能已被清理): {file_hash}")
                        return True
                    
                    c.execute("DELETE FROM history WHERE hash = ?", (file_hash,))
                    rows = c.rowcount
                
                if rows > 0:
                    logger.info(f"✅ [Database] 成功删除 {rows} 条记录: {file_hash}")
                    return True
                else:
                    logger.warning(f"⚠️ [Database] 删除执行成功但影响行数为0: {file_hash}")
                    return True 

        except sqlite3.OperationalError as e:
            if "locked" in str(e):
                logger.warning(f"⚠️ [Database] 数据库被锁定，等待重试... ({e})")
                time.sleep(1)
            else:
                logger.error(f"❌ [Database] 系统删除失败 (OperationalError): {e}")
                return False
        except Exception as e:
            logger.error(f"❌ [Database] 系统删除失败 ({file_hash}): {e}")
            return False
            
    return False


def get_image_by_hash(file_hash: str) -> Optional[Dict[str, Any]]:
    """根据 Hash 查找图片记录"""
    try:
        with get_db_connection() as conn:
            conn.row_factory = sqlite3.Row
            c = conn.cursor()
            c.execute("SELECT * FROM history WHERE hash = ?", (file_hash,))
            row = c.fetchone()
            if row:
                return dict(row)
    except Exception as e:
        logger.error(f"查找图片失败(Hash): {e}")
    return None


def get_image_by_url(url: str) -> Optional[Dict[str, Any]]:
    """根据 URL 查找图片记录"""
    try:
        with get_db_connection() as conn:
            conn.row_factory = sqlite3.Row
            c = conn.cursor()
            c.execute("SELECT * FROM history WHERE url = ?", (url,))
            row = c.fetchone()
            if row:
                return dict(row)
    except Exception as e:
        logger.error(f"查找图片失败: {e}")
    return None
