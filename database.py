import sqlite3
import os
import logging
from contextlib import contextmanager
from typing import List, Dict, Any, Generator

logger = logging.getLogger(__name__)

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "history.db")


@contextmanager
def get_db_connection() -> Generator[sqlite3.Connection, None, None]:
    """获取数据库连接的上下文管理器，确保连接正确关闭"""
    conn = sqlite3.connect(DB_PATH)
    try:
        yield conn
    finally:
        conn.close()


def init_db() -> None:
    """初始化 SQLite 数据库"""
    try:
        with get_db_connection() as conn:
            c = conn.cursor()
            c.execute('''CREATE TABLE IF NOT EXISTS history
                         (id INTEGER PRIMARY KEY AUTOINCREMENT,
                          url TEXT NOT NULL,
                          filename TEXT,
                          hash TEXT,
                          service TEXT,
                          width INTEGER,
                          height INTEGER,
                          size INTEGER,
                          content_type TEXT,
                          created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')

            # 添加索引以加速搜索
            c.execute("CREATE INDEX IF NOT EXISTS idx_filename ON history (filename)")
            c.execute("CREATE INDEX IF NOT EXISTS idx_url ON history (url)")

            conn.commit()
        logger.info(f"✅ 数据库已就绪: {DB_PATH}")
    except Exception as e:
        logger.error(f"❌ 数据库初始化失败: {e}")

def save_to_db(data: dict) -> None:
    """保存记录到数据库"""
    try:
        with get_db_connection() as conn:
            c = conn.cursor()
            # 检查是否已存在 (根据 hash)
            c.execute("SELECT id FROM history WHERE hash = ?", (data.get("hash"),))
            if c.fetchone():
                # 更新现有记录
                c.execute('''UPDATE history SET
                             url=?, filename=?, service=?, width=?, height=?, size=?, content_type=?, created_at=CURRENT_TIMESTAMP
                             WHERE hash=?''',
                          (data.get("url"), data.get("filename"), data.get("service"),
                           data.get("width"), data.get("height"), data.get("size"), data.get("content_type"),
                           data.get("hash")))
            else:
                # 插入新记录
                c.execute('''INSERT INTO history (url, filename, hash, service, width, height, size, content_type)
                             VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
                          (data.get("url"), data.get("filename"), data.get("hash"), data.get("service"),
                           data.get("width"), data.get("height"), data.get("size"), data.get("content_type")))
            conn.commit()
    except Exception as e:
        logger.error(f"❌ 保存到数据库失败: {e}")

def get_history_list(page: int = 1, page_size: int = 20, keyword: str = "") -> Dict[str, Any]:
    """获取历史记录列表，支持分页和关键词搜索"""
    try:
        with get_db_connection() as conn:
            conn.row_factory = sqlite3.Row
            c = conn.cursor()

            offset = (page - 1) * page_size
            query = "SELECT * FROM history"
            params: list = []

            if keyword:
                query += " WHERE filename LIKE ? OR url LIKE ?"
                params.extend([f"%{keyword}%", f"%{keyword}%"])

            query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
            params.extend([page_size, offset])

            c.execute(query, params)
            rows = c.fetchall()

            # 获取总数
            count_query = "SELECT COUNT(*) FROM history"
            count_params: list = []
            if keyword:
                count_query += " WHERE filename LIKE ? OR url LIKE ?"
                count_params.extend([f"%{keyword}%", f"%{keyword}%"])

            c.execute(count_query, count_params)
            total = c.fetchone()[0]

            data = [dict(row) for row in rows]
            return {"success": True, "data": data, "total": total, "page": page, "page_size": page_size}
    except Exception as e:
        logger.error(f"获取历史记录失败: {e}")
        return {"success": False, "error": str(e)}


def delete_history_items(ids: List[int]) -> Dict[str, Any]:
    """批量删除历史记录"""
    try:
        if not ids:
            return {"success": True, "count": 0}

        with get_db_connection() as conn:
            c = conn.cursor()
            placeholders = ','.join('?' * len(ids))
            c.execute(f"DELETE FROM history WHERE id IN ({placeholders})", ids)
            count = c.rowcount
            conn.commit()
            return {"success": True, "count": count}
    except Exception as e:
        return {"success": False, "error": str(e)}


def clear_all_history() -> Dict[str, Any]:
    """清空所有历史记录"""
    try:
        with get_db_connection() as conn:
            c = conn.cursor()
            c.execute("DELETE FROM history")
            conn.commit()
            return {"success": True}
    except Exception as e:
        return {"success": False, "error": str(e)}


def rename_history_item(url: str, filename: str) -> Dict[str, Any]:
    """重命名历史记录项"""
    try:
        with get_db_connection() as conn:
            c = conn.cursor()

            # 尝试直接匹配 URL
            c.execute("UPDATE history SET filename = ? WHERE url = ?", (filename, url))
            affected = c.rowcount

            # 如果没有匹配到，尝试提取路径部分进行匹配
            if affected == 0 and url.startswith("http"):
                from urllib.parse import urlparse
                parsed = urlparse(url)
                path = parsed.path
                c.execute("UPDATE history SET filename = ? WHERE url = ?", (filename, path))
                affected = c.rowcount

            conn.commit()

            if affected > 0:
                return {"success": True}
            else:
                return {"success": False, "error": "未找到匹配的记录"}
    except Exception as e:
        return {"success": False, "error": str(e)}
