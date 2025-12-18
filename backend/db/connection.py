# backend/db/connection.py
# 数据库连接和初始化 - 喵～这是整个数据库模块的基础设施

import sqlite3
import os
import logging
from contextlib import contextmanager
from typing import Generator

# [Refactor] 从 config 导入 DB_PATH，确保统一
from ..config import DB_PATH
# [Refactor] 导入 schema 定义
from .schema import TABLES, INDEXES

logger = logging.getLogger(__name__)


@contextmanager
def get_db_connection() -> Generator[sqlite3.Connection, None, None]:
    """
    获取数据库连接的上下文管理器。
    """
    # [Fix] 增加 check_same_thread=False 允许在多线程中使用同一个连接对象 (FastAPI 默认是多线程)
    # 虽然最佳实践是每个请求一个连接，但 SQLite 在 read heavy 场景下复用连接有时能提高点性能
    # 不过这里更重要的是配合 FastAPI 的 async/def 混合模式防止报错
    conn = sqlite3.connect(DB_PATH, timeout=30.0, check_same_thread=False)
    # 开启 WAL 模式提高并发性能
    # conn.execute("PRAGMA journal_mode=WAL;") 
    try:
        yield conn 
    finally:
        conn.close() 


def init_db() -> None:
    """
    初始化 SQLite 数据库。
    使用 schema.py 中的定义自动创建表和索引。
    """
    try:
        with get_db_connection() as conn:
            c = conn.cursor()

            # 1. 自动创建所有表
            for table_name, create_sql in TABLES.items():
                c.execute(create_sql)
                # logger.debug(f"检查表: {table_name}")

            # 2. 自动创建所有索引
            for index_sql in INDEXES:
                c.execute(index_sql)
                
            conn.commit()
            
            # 3. 执行迁移逻辑 (检查字段是否缺失)
            migrate_tables(conn)
            
        logger.info(f"✅ 数据库已就绪: {DB_PATH}")
    except Exception as e:
        logger.error(f"❌ 数据库初始化失败: {e}")
        # 如果初始化失败，可能是数据库文件损坏或权限问题，严重错误
        raise e


def migrate_tables(conn: sqlite3.Connection) -> None:
    """
    检查并迁移表结构（添加缺失的字段）。
    """
    c = conn.cursor()
    
    # 1. 检查 history 表字段
    c.execute("PRAGMA table_info(history)")
    history_columns = [col[1] for col in c.fetchall()]
    
    history_updates = {
        "device_id": "TEXT",
        "is_shared": "INTEGER DEFAULT 0",
        "user_id": "INTEGER",
        "ip_address": "TEXT"
    }
    
    for col, dtype in history_updates.items():
        if col not in history_columns:
            try:
                c.execute(f"ALTER TABLE history ADD COLUMN {col} {dtype}")
                logger.info(f"✅ [Migration] history 表已添加 {col} 字段")
            except Exception as e:
                logger.warning(f"⚠️ [Migration] 添加 history.{col} 失败: {e}")

    # 2. 检查 users 表字段
    c.execute("PRAGMA table_info(users)")
    user_columns = [col[1] for col in c.fetchall()]
    
    user_updates = {
        "is_admin": "INTEGER DEFAULT 0",
        "google_id": "TEXT",
        "avatar": "TEXT",
        "email": "TEXT",
        "is_vip": "INTEGER DEFAULT 0",
        "vip_expiry": "DATETIME"
    }
    
    for col, dtype in user_updates.items():
        if col not in user_columns:
            try:
                c.execute(f"ALTER TABLE users ADD COLUMN {col} {dtype}")
                logger.info(f"✅ [Migration] users 表已添加 {col} 字段")
            except Exception as e:
                 logger.warning(f"⚠️ [Migration] 添加 users.{col} 失败: {e}")

    # 3. 补通过 UNIQUE 索引
    # create_index_if_not_exists(c, "users", "google_id", unique=True) # 已包含在 INDEXES 中
    # create_index_if_not_exists(c, "users", "email", unique=True)     # 已包含在 INDEXES 中
    
    conn.commit()

