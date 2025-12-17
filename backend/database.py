import sqlite3
import os
import logging
import uuid
from contextlib import contextmanager
from typing import List, Dict, Any, Generator, Optional
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

# 数据库文件路径配置
# 1. 优先使用环境变量 DATA_DIR 指定的目录 (用于 Docker 挂载卷: /app/data)
# 2. 否则默认为当前文件同级目录 (用于本地开发)
DATA_DIR = os.getenv("DATA_DIR")
if DATA_DIR:
    # 确保目录存在
    os.makedirs(DATA_DIR, exist_ok=True)
    DB_PATH = os.path.join(DATA_DIR, "history.db")
else:
    DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "history.db")


@contextmanager
def get_db_connection() -> Generator[sqlite3.Connection, None, None]:
    """
    获取数据库连接的上下文管理器。
    
    为什么要用这个？
    数据库连接是一种"资源"，用完必须关闭，否则会占用系统内存甚至导致死锁。
    使用 @contextmanager 和 yield，我们可以这样写代码：
    
    with get_db_connection() as conn:
        # 在这里使用 conn
        ...
    # 离开 with 代码块时，会自动执行 finally 里的 conn.close()
    """
@contextmanager
def get_db_connection() -> Generator[sqlite3.Connection, None, None]:
    """
    获取数据库连接的上下文管理器。
    """
    # [Fix] 增加超时时间到 30秒，防止高并发下 "database is locked" 错误
    conn = sqlite3.connect(DB_PATH, timeout=30.0) 
    try:
        yield conn 
    finally:
        conn.close() 

def init_db() -> None:

    """
    初始化 SQLite 数据库。
    在程序启动时调用，确保数据库表已经存在。
    """
    try:
        with get_db_connection() as conn:
            c = conn.cursor() # 获取游标（Cursor），用于执行 SQL 语句

            # 1. 检查表是否存在
            # sqlite_master 是 SQLite 的系统表，记录了所有表的信息
            c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='history'")
            table_exists = c.fetchone() is not None

            if not table_exists:
                # 2. 如果表不存在，创建新表
                # id: 自增主键，每条记录的唯一编号
                # url: 图片访问链接
                # filename: 文件名
                # hash: 文件哈希值（去重用）
                # device_id: 设备ID（区分用户）
                # is_shared: 是否共享（0=私有，1=共享）
                c.execute('''CREATE TABLE history
                             (id INTEGER PRIMARY KEY AUTOINCREMENT,
                              url TEXT NOT NULL,
                              filename TEXT,
                              hash TEXT,
                              service TEXT,
                              width INTEGER,
                              height INTEGER,
                              size INTEGER,
                              content_type TEXT,
                              device_id TEXT,
                              user_id INTEGER,
                              is_shared INTEGER DEFAULT 0,
                              created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                              FOREIGN KEY(user_id) REFERENCES users(id))''')

                # 创建用户表
                c.execute('''CREATE TABLE IF NOT EXISTS users
                             (id INTEGER PRIMARY KEY AUTOINCREMENT,
                              username TEXT UNIQUE NOT NULL,
                              password_hash TEXT NOT NULL,
                              created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
            else:
                # 3. 如果表已存在，检查是否需要"迁移"（添加新字段）
                # 随着功能迭代，我们可能加了新字段，旧数据库需要升级
                c.execute("PRAGMA table_info(history)")
                columns = [col[1] for col in c.fetchall()] # 获取所有列名
                
                if "device_id" not in columns:
                    c.execute("ALTER TABLE history ADD COLUMN device_id TEXT")
                    logger.info("✅ 已添加 device_id 字段")
                if "is_shared" not in columns:
                    c.execute("ALTER TABLE history ADD COLUMN is_shared INTEGER DEFAULT 0")
                    logger.info("✅ 已添加 is_shared 字段")
                if "user_id" not in columns:
                    c.execute("ALTER TABLE history ADD COLUMN user_id INTEGER")
                    logger.info("✅ 已添加 user_id 字段")

            # 检查用户表是否存在(防止老版本只初始化了history)
            c.execute("CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT UNIQUE NOT NULL, password_hash TEXT NOT NULL, is_admin INTEGER DEFAULT 0, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)")
            
            # 检查 users 表是否有 is_admin 字段
            c.execute("PRAGMA table_info(users)")
            user_columns = [col[1] for col in c.fetchall()]
            if "is_admin" not in user_columns:
                c.execute("ALTER TABLE users ADD COLUMN is_admin INTEGER DEFAULT 0")
                logger.info("✅ 已添加 is_admin 字段")

            if "google_id" not in user_columns:
                # SQLite 不支持直接 ALTER TABLE ADD COLUMN ... UNIQUE
                # 需要两步：1. 添加列  2. 创建唯一索引
                c.execute("ALTER TABLE users ADD COLUMN google_id TEXT")
                c.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_google_id ON users (google_id)")
                logger.info("✅ 已添加 google_id 字段")
            if "avatar" not in user_columns:
                c.execute("ALTER TABLE users ADD COLUMN avatar TEXT")
                logger.info("✅ 已添加 avatar 字段")
            
            if "email" not in user_columns:
                c.execute("ALTER TABLE users ADD COLUMN email TEXT")
                c.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_users_email ON users(email)")
                logger.info("✅ 已添加 email 字段")

            if "is_vip" not in user_columns:
                c.execute("ALTER TABLE users ADD COLUMN is_vip INTEGER DEFAULT 0")
                logger.info("✅ 已添加 is_vip 字段")
                
            if "vip_expiry" not in user_columns:
                c.execute("ALTER TABLE users ADD COLUMN vip_expiry DATETIME")
                logger.info("✅ 已添加 vip_expiry 字段")

            # 5. 检查 verification_codes 表是否存在
            c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='verification_codes'")
            if not c.fetchone():
                c.execute('''CREATE TABLE verification_codes
                             (id INTEGER PRIMARY KEY AUTOINCREMENT,
                              email TEXT NOT NULL,
                              code TEXT NOT NULL,
                              type TEXT NOT NULL, -- register / reset
                              expires_at DATETIME NOT NULL,
                              created_at DATETIME DEFAULT CURRENT_TIMESTAMP)''')

            # 5.5. 检查 vip_codes 表是否存在 (VIP 系统)
            c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='vip_codes'")
            if not c.fetchone():
                c.execute('''CREATE TABLE vip_codes
                             (id INTEGER PRIMARY KEY AUTOINCREMENT,
                              code TEXT UNIQUE NOT NULL,
                              days INTEGER NOT NULL, -- 激活天数
                              is_used INTEGER DEFAULT 0,
                              used_by INTEGER, -- 使用者 ID
                              used_at DATETIME,
                              created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                              FOREIGN KEY(used_by) REFERENCES users(id))''')

            # 5.6 检查 history 表是否有 ip_address 字段 (Limit)
            c.execute("PRAGMA table_info(history)")
            history_columns = [col[1] for col in c.fetchall()]
            if "ip_address" not in history_columns:
                c.execute("ALTER TABLE history ADD COLUMN ip_address TEXT")
                logger.info("✅ 已添加 ip_address 字段到 history 表")

            # 4. 创建索引
            # 索引就像书的目录，能大大加快查询速度
            c.execute("CREATE INDEX IF NOT EXISTS idx_filename ON history (filename)")
            c.execute("CREATE INDEX IF NOT EXISTS idx_url ON history (url)")
            c.execute("CREATE INDEX IF NOT EXISTS idx_device_id ON history (device_id)")
            c.execute("CREATE INDEX IF NOT EXISTS idx_is_shared ON history (is_shared)")
            c.execute("CREATE INDEX IF NOT EXISTS idx_user_id ON history (user_id)")
            c.execute("CREATE INDEX IF NOT EXISTS idx_username ON users (username)")

            # 6. Check for user_logs table
            c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='user_logs'")
            if not c.fetchone():
                c.execute('''CREATE TABLE user_logs
                             (id INTEGER PRIMARY KEY AUTOINCREMENT,
                              user_id INTEGER NOT NULL,
                              action TEXT NOT NULL,
                              ip_address TEXT,
                              user_agent TEXT,
                              created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                              FOREIGN KEY(user_id) REFERENCES users(id))''')
                c.execute("CREATE INDEX IF NOT EXISTS idx_logs_user_id ON user_logs(user_id)")

            # 7. Check for user_sessions table
            c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='user_sessions'")
            if not c.fetchone():
                 c.execute('''CREATE TABLE user_sessions
                              (id INTEGER PRIMARY KEY AUTOINCREMENT,
                               user_id INTEGER NOT NULL,
                               session_id TEXT UNIQUE NOT NULL,
                               device_info TEXT,
                               ip_address TEXT,
                               last_active TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                               created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                               FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE)''')

            # 8. 用户通知表 (审核结果、系统消息等)
            c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='user_notifications'")
            if not c.fetchone():
                c.execute('''CREATE TABLE user_notifications
                             (id INTEGER PRIMARY KEY AUTOINCREMENT,
                              user_id INTEGER,
                              device_id TEXT,
                              type TEXT NOT NULL,
                              title TEXT,
                              message TEXT NOT NULL,
                              is_read INTEGER DEFAULT 0,
                              created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                              FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE)''')
                c.execute("CREATE INDEX IF NOT EXISTS idx_notif_user ON user_notifications(user_id)")
                c.execute("CREATE INDEX IF NOT EXISTS idx_notif_device ON user_notifications(device_id)")
                logger.info("✅ 已创建 user_notifications 表")

            # 9. 侵权举报表
            c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='abuse_reports'")
            if not c.fetchone():
                c.execute('''CREATE TABLE abuse_reports
                             (id INTEGER PRIMARY KEY AUTOINCREMENT,
                              image_hash TEXT,
                              image_url TEXT,
                              reporter_id INTEGER,
                              reporter_device TEXT,
                              reporter_contact TEXT,
                              reason TEXT NOT NULL,
                              status TEXT DEFAULT 'pending',
                              admin_notes TEXT,
                              created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                              resolved_at TIMESTAMP,
                              FOREIGN KEY(reporter_id) REFERENCES users(id))''')
                c.execute("CREATE INDEX IF NOT EXISTS idx_report_status ON abuse_reports(status)")
                c.execute("CREATE INDEX IF NOT EXISTS idx_report_hash ON abuse_reports(image_hash)")
                logger.info("✅ 已创建 abuse_reports 表")

            conn.commit() # 提交事务，保存更改
        logger.info(f"✅ 数据库已就绪: {DB_PATH}")
    except Exception as e:
        logger.error(f"❌ 数据库初始化失败: {e}")

def save_to_db(file_info: dict, device_id: str = None, user_id: int = None, is_shared: bool = False, ip_address: str = None) -> dict:
    """保存图片元数据到数据库"""
    try:
        with get_db_connection() as conn:
            c = conn.cursor()
            
            # Deduplication logic (based on Hash AND ownership)
            # 1. Check if hash exists
            #   - If Private Mode (user_id): Check if (hash, user_id) exists.
            #   - If Shared Mode: Check if hash exists.
            
            data = file_info
            
            # Initial Check
            conditions = ["hash = ?"]
            params = [data.get("hash")]
            
            if is_shared:
                # Shared Mode: Globally unique by hash for shared images?
                # Actually, our new requirement says "Shared record independent of Private record".
                # Deduplication in shared mode logic:
                conditions.append("is_shared = 1")
            else:
                 # Private Mode: Unique per user
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
                # 已存在 -> 更新（例如 filename）
                update_fields = '''UPDATE history SET url=?, filename=?, service=?, width=?, height=?, size=?, content_type=?, 
                                     created_at=CURRENT_TIMESTAMP'''
                params = [data.get("url"), data.get("filename"), data.get("service"),
                          data.get("width"), data.get("height"), data.get("size"), data.get("content_type")]
                
                # 检查是否需要"认领"
                should_claim = False
                if is_shared and user_id: # 只有共享模式且当前是登录用户才涉及认领
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
                
            conn.commit()
            return {"success": True, "existing": bool(row_id is not None and c.lastrowid is None), "id": row_id}
    except Exception as e:
        logger.error(f"❌ 保存到数据库失败: {e}")
        return {"success": False, "error": str(e)}

def get_history_list(page: int = 1, page_size: int = 20, keyword: str = "",
                     device_id: str = None, user_id: int = None, is_admin: bool = False, view_mode: str = "private",
                     only_mine: bool = False) -> Dict[str, Any]:
    """
    查询历史记录，支持分页、搜索和权限过滤。
    """
    try:
        with get_db_connection() as conn:
            # 让查询结果像字典一样可以通过列名访问 (row['url'])，而不是只能用索引 (row[1])
            conn.row_factory = sqlite3.Row
            c = conn.cursor()

            # 计算分页偏移量
            # 第1页: offset=0; 第2页: offset=20...
            offset = (page - 1) * page_size
            
            query = "SELECT * FROM history"
            params: list = []
            conditions: list = []

            # === 核心过滤逻辑 ===
            if view_mode == "shared":
                # 共享模式：显示所有 is_shared=1 的记录
                conditions.append("is_shared = 1")
                # 如果勾选了"只看我的"，额外加 device_id 过滤
                if only_mine:
                    # 共享模式下，如果是"只看我的"
                    if user_id:
                        conditions.append("user_id = ?")
                        params.append(user_id)
                    elif device_id:
                        conditions.append("device_id = ?")
                        params.append(device_id)
            elif view_mode == "admin_all":
                # [Admin] 上帝模式：查看所有记录 (私有+共享)
                # 只有管理员能进入此逻辑 (Router层需校验)
                pass 
            else:
                # 私有模式：
                if user_id:
                    # 登录用户只看自己的
                    conditions.append("user_id = ?")
                    # conditions.append("is_shared = 0") # [Change] 私有视图是否应该包含共享？
                    # 通常"我的文件"应该包含我上传的所有文件(无论私有还是共享)
                    # 但原逻辑似乎区分了 Tab。即使是 Private Tab，一般也只显示 is_shared=0
                    # 保持原逻辑：Private Tab 只显示私有文件
                    conditions.append("is_shared = 0")
                    params.append(user_id)
                else:
                    # 未登录用户看设备的
                    conditions.append("device_id = ?")
                    conditions.append("is_shared = 0")
                    # 还要确保 user_id 为空
                    conditions.append("user_id IS NULL")
                    params.append(device_id)

            # 关键词搜索（模糊匹配文件名或URL）
            if keyword:
                conditions.append("(filename LIKE ? OR url LIKE ?)")
                params.extend([f"%{keyword}%", f"%{keyword}%"])

            # 拼接 WHERE 子句
            if conditions:
                query += " WHERE " + " AND ".join(conditions)

            # 排序和分页
            # ORDER BY created_at DESC: 按时间倒序（最新的在前面）
            query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
            params.extend([page_size, offset])

            c.execute(query, params)
            rows = c.fetchall()

            # === 获取总条数（用于前端计算页码） ===
            count_query = "SELECT COUNT(*) FROM history"
            count_params: list = []
            count_conditions: list = []

            # 重复一遍上面的条件逻辑（为了计算总数）
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
                # 标记这条记录是不是"我"上传的（用于前端显示删除按钮等）
                # 标记这条记录是不是"我"上传的
                # [Fix] 需求变更：匿名用户上传的图片（user_id IS NULL）被视为"公共资源"，
                # 登录用户应当有权编辑/删除它们。所以如果 user_id 为空，也视为 is_mine = True
                # [Admin] 管理员拥有一切
                if is_admin:
                    item['is_mine'] = True
                elif user_id:
                    item['is_mine'] = (item['user_id'] == user_id) or (item['user_id'] is None)
                elif device_id:
                    # 匿名用户只看自己的，或者... 匿名用户通常应该只能看自己的? 
                    # 保持原逻辑：匿名用户通过 device_id 认领
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
            c = conn.cursor()
            placeholders = ','.join('?' * len(ids))
            
            query = f"DELETE FROM history WHERE id IN ({placeholders})"
            params = list(ids)
            
            # 权限控制：如果是管理员，跳过所有所有权检查
            if not is_admin:
                if user_id:
                    # 登录用户：可以删除属于自己的 (user_id=?) 或者 匿名的 (user_id IS NULL)
                    query += " AND (user_id = ? OR user_id IS NULL)"
                    params.append(user_id)
                elif device_id:
                    query += " AND device_id = ? AND user_id IS NULL"
                    params.append(device_id)
                else:
                     # 安全兜底
                     return {"success": False, "error": "Missing auth info"}

            c.execute(query, params)
            count = c.rowcount # 获取被删除的行数
            conn.commit()
            return {"success": True, "count": count}
    except Exception as e:
        return {"success": False, "error": str(e)}


def clear_all_history(device_id: str = None, view_mode: str = "private", user_id: int = None, is_admin: bool = False) -> Dict[str, Any]:
    """清空当前模式下的所有历史记录"""
    try:
        with get_db_connection() as conn:
            c = conn.cursor()
            
            if view_mode == "shared":
                query = "DELETE FROM history WHERE is_shared = 1"
                params = []
                
                # 如果不是管理员，只能删自己的
                if not is_admin:
                    if user_id:
                         query += " AND (user_id = ? OR user_id IS NULL)" # 也可以删匿名的
                         params.append(user_id)
                    elif device_id:
                         query += " AND device_id = ? AND user_id IS NULL"
                         params.append(device_id)
                
                c.execute(query, params)

            else:
                # 清空私有记录
                # 即使是管理员，是否要允许清空所有人的私有记录？ 
                # 既然是"全能模式"，允许吧。但是 clear 通常是针对"我的视图"的。
                # 暂且让管理员在私有模式下清除所有私有记录 (慎用)
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
                
            conn.commit()
            return {"success": True}
    except Exception as e:
        return {"success": False, "error": str(e)}


def rename_history_item(item_id: int, filename: str, device_id: str = None, user_id: int = None, is_admin: bool = False) -> Dict[str, Any]:
    """重命名历史记录 (通过 ID)"""
    try:
        with get_db_connection() as conn:
            c = conn.cursor()
            
            # 构建 Query
            query = "UPDATE history SET filename = ? WHERE id = ?"
            params = [filename, item_id]
            
            if not is_admin:
                if user_id:
                     # 登录用户：可以重命名自己的 或 匿名的
                     query += " AND (user_id = ? OR user_id IS NULL)"
                     params.append(user_id)
                elif device_id:
                     # 游客：只能重命名该设备上传且未被认领的
                     query += " AND device_id = ? AND user_id IS NULL"
                     params.append(device_id)
                else:
                     return {"success": False, "error": "Missing auth info"}

            c.execute(query, params)
            if c.rowcount == 0:
                 return {"success": False, "error": "Item not found or permission denied"}
            
            conn.commit()
            return {"success": True}
    except Exception as e:
        return {"success": False, "error": str(e)}


def delete_image_by_hash_system(file_hash: str) -> bool:
    """
    系统级物理删除图片记录 (用于 AI 违规清理)
    包含重试机制，防止数据库锁导致删除失败
    """
    import time
    max_retries = 3
    
    for attempt in range(max_retries):
        try:
            with get_db_connection() as conn:
                c = conn.cursor()
                logger.info(f"🗑️ [Database] 尝试删除 Hash 记录: {file_hash} (Attempt {attempt+1})")
                
                # Check existance first for debugging
                c.execute("SELECT count(*) FROM history WHERE hash = ?", (file_hash,))
                count = c.fetchone()[0]
                if count == 0:
                    logger.info(f"⚠️ [Database] 要删除的记录不存在(可能已被清理): {file_hash}")
                    return True # 视为成功
                
                c.execute("DELETE FROM history WHERE hash = ?", (file_hash,))
                rows = c.rowcount
                conn.commit()
                
                if rows > 0:
                    logger.info(f"✅ [Database] 成功删除 {rows} 条记录: {file_hash}")
                    return True
                else:
                    logger.warning(f"⚠️ [Database] 删除执行成功但影响行数为0: {file_hash}")
                    return True 

        except sqlite3.OperationalError as e:
            if "locked" in str(e):
                logger.warning(f"⚠️ [Database] 数据库被锁定，等待重试... ({e})")
                time.sleep(1) # Wait 1s before retry
            else:
                logger.error(f"❌ [Database] 系统删除失败 (OperationalError): {e}")
                return False
        except Exception as e:
            logger.error(f"❌ [Database] 系统删除失败 ({file_hash}): {e}")
            return False
            
    return False


def create_user(username: str, password_hash: str) -> bool:
    """创建新用户"""
    try:
        with get_db_connection() as conn:
            c = conn.cursor()
            c.execute("INSERT INTO users (username, password_hash) VALUES (?, ?)", (username, password_hash))
            conn.commit()
            return True
    except sqlite3.IntegrityError:
        return False # 用户名已存在
    except Exception as e:
        logger.error(f"创建用户失败: {e}")
        return False


def get_user_by_username(username: str) -> Dict[str, Any]:
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


def get_user_by_google_id(google_id: str) -> Dict[str, Any]:
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
            c = conn.cursor()
            c.execute("INSERT INTO users (username, password_hash, google_id, avatar) VALUES (?, ?, ?, ?)", 
                      (username, "GOOGLE_LOGIN", google_id, avatar))
            conn.commit()
            return True
    except Exception as e:
        logger.error(f"Create google user failed: {e}")
        return False




def get_user_by_email(email: str) -> Dict[str, Any]:
    "get user by email"
    with get_db_connection() as conn:
        c = conn.cursor()
        c.execute("SELECT * FROM users WHERE email=?", (email,))
        row = c.fetchone()
        if row:
            columns = [col[0] for col in c.description]
            return dict(zip(columns, row))
        return None

def save_verification_code(email: str, code: str, type: str, expires_at: datetime) -> bool:
    try:
        with get_db_connection() as conn:
            c = conn.cursor()
            c.execute("DELETE FROM verification_codes WHERE email=? AND type=?", (email, type))
            c.execute("INSERT INTO verification_codes (email, code, type, expires_at) VALUES (?, ?, ?, ?)", (email, code, type, expires_at))
            conn.commit()
            return True
    except Exception as e:
        logger.error(f"Save verification code failed: {e}")
        return False

def get_valid_verification_code(email: str, type: str) -> str:
    with get_db_connection() as conn:
        c = conn.cursor()
        now = datetime.now()
        c.execute("SELECT code FROM verification_codes WHERE email=? AND type=? AND expires_at > ? ORDER BY created_at DESC LIMIT 1", (email, type, now))
        row = c.fetchone()
        return row[0] if row else None

def delete_verification_code(email: str, type: str) -> bool:
    """删除已使用的验证码"""
    try:
        with get_db_connection() as conn:
            c = conn.cursor()
            c.execute("DELETE FROM verification_codes WHERE email=? AND type=?", (email, type))
            conn.commit()
            return True
    except Exception as e:
        logger.error(f"Delete verification code failed: {e}")
        return False

def update_user_password(email: str, hashed_password: str) -> bool:
    try:
        with get_db_connection() as conn:
            c = conn.cursor()
            c.execute("UPDATE users SET password_hash=? WHERE email=?", (hashed_password, email))
            conn.commit()
            return True
    except Exception as e:
        logger.error(f"Update password failed: {e}")
        return False

def create_email_user(username: str, email: str, password_hash: str) -> bool:
    try:
        with get_db_connection() as conn:
            c = conn.cursor()
            c.execute("INSERT INTO users (username, email, password_hash) VALUES (?, ?, ?)", (username, email, password_hash))
            conn.commit()
            return True
    except sqlite3.IntegrityError:
        return False

def update_user_password_by_id(user_id: int, hashed_password: str) -> bool:
    """通过用户ID更新密码"""
    try:
        with get_db_connection() as conn:
            c = conn.cursor()
            c.execute("UPDATE users SET password_hash=? WHERE id=?", (hashed_password, user_id))
            conn.commit()
            return True
    except Exception as e:
        logger.error(f"Update password by ID failed: {e}")
        return False

def update_username(user_id: int, new_username: str) -> bool:
    """更新用户名"""
    try:
        with get_db_connection() as conn:
            c = conn.cursor()
            c.execute("UPDATE users SET username=? WHERE id=?", (new_username, user_id))
            conn.commit()
            return True
    except Exception as e:
        logger.error(f"Update username failed: {e}")
        return False

def delete_user(user_id: int) -> bool:
    """删除用户"""
    try:
        with get_db_connection() as conn:
            c = conn.cursor()
            c.execute("DELETE FROM users WHERE id=?", (user_id,))
            conn.commit()
            return True
    except Exception as e:
        logger.error(f"Delete user failed: {e}")
        return False

def delete_user_history(user_id: int) -> bool:
    """删除用户所有历史记录"""
    try:
        with get_db_connection() as conn:
            c = conn.cursor()
            c.execute("DELETE FROM history WHERE user_id=?", (user_id,))
            conn.commit()
            return True
    except Exception as e:
        logger.error(f"Delete user history failed: {e}")
        return False

def get_user_stats(user_id: int) -> dict:
    """获取用户统计信息"""
    try:
        with get_db_connection() as conn:
            c = conn.cursor()
            # 上传图片数量
            c.execute("SELECT COUNT(*) FROM history WHERE user_id=?", (user_id,))
            upload_count = c.fetchone()[0]
            
            # 获取用户信息
            c.execute("SELECT created_at, email FROM users WHERE id=?", (user_id,))
            row = c.fetchone()
            created_at = row[0] if row else None
            email = row[1] if row else None
            
            return {
                "upload_count": upload_count,
                "created_at": created_at,
                "email": email
            }
    except Exception as e:
        logger.error(f"Get user stats failed: {e}")
        return {"upload_count": 0, "created_at": None, "email": None}


def log_user_activity(user_id: int, action: str, ip_address: str = None, user_agent: str = None) -> bool:
    """记录用户活动"""
    try:
        with get_db_connection() as conn:
            c = conn.cursor()
            c.execute("INSERT INTO user_logs (user_id, action, ip_address, user_agent) VALUES (?, ?, ?, ?)",
                      (user_id, action, ip_address, user_agent))
            conn.commit()
            return True
    except Exception as e:
        logger.error(f"Log activity failed: {e}")
        return False

def get_user_logs(user_id: int, limit: int = 10) -> List[dict]:
    """获取用户最近的活动日志"""
    try:
        with get_db_connection() as conn:
            conn.row_factory = sqlite3.Row
            c = conn.cursor()
            c.execute("SELECT action, ip_address, user_agent, created_at FROM user_logs WHERE user_id = ? ORDER BY created_at DESC LIMIT ?", (user_id, limit))
            columns = [col[0] for col in c.description]
            return [dict(row) for row in c.fetchall()]
    except Exception as e:
        logger.error(f"Get user logs failed: {e}")
        return []

def create_session(user_id: int, device_info: str = None, ip_address: str = None) -> str:
    """创建新的用户会话"""
    session_id = str(uuid.uuid4())
    try:
        with get_db_connection() as conn:
            c = conn.cursor()
            c.execute("INSERT INTO user_sessions (user_id, session_id, device_info, ip_address) VALUES (?, ?, ?, ?)",
                      (user_id, session_id, device_info, ip_address))
            conn.commit()
            return session_id
    except Exception as e:
        logger.error(f"Create session failed: {e}")
        return None

def get_active_sessions(user_id: int) -> List[dict]:
    """获取用户的所有活跃会话"""
    try:
        with get_db_connection() as conn:
            conn.row_factory = sqlite3.Row
            c = conn.cursor()
            c.execute("SELECT * FROM user_sessions WHERE user_id = ? ORDER BY last_active DESC", (user_id,))
            return [dict(row) for row in c.fetchall()]
    except Exception as e:
        logger.error(f"Get active sessions failed: {e}")
        return []

def revoke_session(session_id: str, user_id: int) -> bool:
    """注销会话"""
    try:
        with get_db_connection() as conn:
            c = conn.cursor()
            c.execute("DELETE FROM user_sessions WHERE session_id = ? AND user_id = ?", (session_id, user_id))
            conn.commit()
            # 只有当真正删除了一行时才算成功
            return c.rowcount > 0
    except Exception as e:
        logger.error(f"Revoke session failed: {e}")
        return False

def validate_session(session_id: str) -> bool:
    """验证会话是否有效"""
    try:
        with get_db_connection() as conn:
            c = conn.cursor()
            c.execute("SELECT id FROM user_sessions WHERE session_id = ?", (session_id,))
            return c.fetchone() is not None
    except Exception as e:
        logger.error(f"Validate session failed: {e}")
        return False

def update_session_activity(session_id: str) -> None:
    """更新会话最后活跃时间"""
    try:
        with get_db_connection() as conn:
            c = conn.cursor()
            c.execute("UPDATE user_sessions SET last_active = CURRENT_TIMESTAMP WHERE session_id = ?", (session_id,))
            conn.commit()
    except:
        pass


def activate_vip(user_id: int, code: str) -> dict:
    """激活 VIP"""
    try:
        with get_db_connection() as conn:
            c = conn.cursor()
            
            # 1. 验证激活码
            c.execute("SELECT id, days, is_used FROM vip_codes WHERE code = ?", (code,))
            row = c.fetchone()
            
            if not row:
                return {"success": False, "error": "无效的激活码"}
                
            code_id, days, is_used = row
            
            if is_used:
                return {"success": False, "error": "激活码已被使用"}
                
            # 2. 计算过期时间
            # 先获取当前用户是否已经是 VIP，如果是，则在原过期时间上累加
            c.execute("SELECT is_vip, vip_expiry FROM users WHERE id = ?", (user_id,))
            user_row = c.fetchone()
            
            current_expiry = datetime.now()
            if user_row and user_row[0] and user_row[1]:
                # 如果已经是 VIP 且没过期，从原过期时间开始算
                try:
                    expiry_dt = datetime.strptime(user_row[1], "%Y-%m-%d %H:%M:%S")
                    if expiry_dt > datetime.now():
                        current_expiry = expiry_dt
                except:
                    pass # 解析失败就按当前时间算

            new_expiry = current_expiry + timedelta(days=days)
            new_expiry_str = new_expiry.strftime("%Y-%m-%d %H:%M:%S")
            
            # 3. 更新用户状态
            c.execute("UPDATE users SET is_vip = 1, vip_expiry = ? WHERE id = ?", (new_expiry_str, user_id))
            
            # 4. 标记激活码为已使用
            c.execute("UPDATE vip_codes SET is_used = 1, used_by = ?, used_at = CURRENT_TIMESTAMP WHERE id = ?", (user_id, code_id))
            
            conn.commit()
            return {"success": True, "expiry": new_expiry_str}
            
    except Exception as e:
        logger.error(f"Activate VIP failed: {e}")
        return {"success": False, "error": str(e)}

def create_vip_code(code: str, days: int) -> bool:
    """创建 VIP 激活码 (管理员用)"""
    try:
        with get_db_connection() as conn:
            c = conn.cursor()
            c.execute("INSERT INTO vip_codes (code, days) VALUES (?, ?)", (code, days))
            conn.commit()
            return True
    except Exception as e:
        logger.error(f"Create VIP code failed: {e}")
        return False

def get_today_upload_count(user_id: int = None, device_id: str = None, ip_address: str = None) -> int:
    """
    获取今日上传数量。
    如果是登录用户，按 user_id 统计。
    如果是匿名用户，按 ip_address 或 device_id 统计
    SQL: WHERE (ip_address = ? OR device_id = ?) AND created_at > today
    """
    try:
        with get_db_connection() as conn:
            c = conn.cursor()
            
            # SQLite 的 date('now', 'localtime') 返回 YYYY-MM-DD
            # created_at 是 TIMESTAMP (YYYY-MM-DD HH:MM:SS)
            # 我们只需要比较 created_at >= 今天0点
            
            today_start = datetime.now().strftime("%Y-%m-%d 00:00:00")
            
            if user_id:
                query = "SELECT count(*) FROM history WHERE user_id = ? AND created_at >= ?"
                params = (user_id, today_start)
                c.execute(query, params)
            else:
                # 匿名用户: IP 或 Device ID
                # 很多时候 Device ID 是空的 (如果前端没传)，所以要小心
                conditions = []
                params = []
                
                if ip_address:
                    conditions.append("ip_address = ?")
                    params.append(ip_address)
                
                if device_id:
                    conditions.append("device_id = ?")
                    params.append(device_id)
                    
                if not conditions:
                    return 0 # 没任何身份信息，无法统计
                    
                # WHERE (ip = ? OR device_id = ?) AND created_at >= ?
                clause = " OR ".join(conditions)
                query = f"SELECT count(*) FROM history WHERE ({clause}) AND created_at >= ?"
                
                params.append(today_start)
                
                c.execute(query, tuple(params))
                
            return c.fetchone()[0]
            
    except Exception as e:
        logger.error(f"Get upload count failed: {e}")
        return 0


# ==================== 通知系统 ====================

def create_notification(user_id: int = None, device_id: str = None, 
                        type: str = "system", title: str = None, message: str = "") -> bool:
    """创建用户通知"""
    try:
        with get_db_connection() as conn:
            c = conn.cursor()
            c.execute('''INSERT INTO user_notifications (user_id, device_id, type, title, message)
                         VALUES (?, ?, ?, ?, ?)''', (user_id, device_id, type, title, message))
            conn.commit()
            logger.info(f"📢 已创建通知: {title} -> user={user_id}, device={device_id}")
            return True
    except Exception as e:
        logger.error(f"Create notification failed: {e}")
        return False

def get_notifications(user_id: int = None, device_id: str = None, unread_only: bool = False) -> List[Dict]:
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
            if device_id:
                conditions.append("device_id = ?")
                params.append(device_id)
            
            if not conditions:
                return []
            
            query = "SELECT * FROM user_notifications WHERE (" + " OR ".join(conditions) + ")"
            
            if unread_only:
                query += " AND is_read = 0"
            
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
            c.execute("UPDATE user_notifications SET is_read = 1 WHERE id = ?", (notification_id,))
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
            c.execute('''DELETE FROM user_notifications 
                         WHERE created_at < datetime('now', ?)''', (f'-{days} days',))
            count = c.rowcount
            conn.commit()
            if count > 0:
                logger.info(f"🧹 已清理 {count} 条过期通知")
            return count
    except Exception as e:
        logger.error(f"Cleanup notifications failed: {e}")
        return 0


# ==================== 举报系统 ====================

def create_abuse_report(image_hash: str = None, image_url: str = None, 
                        reporter_id: int = None, reporter_device: str = None,
                        reporter_contact: str = None, reason: str = "") -> Dict:
    """创建侵权举报"""
    try:
        with get_db_connection() as conn:
            c = conn.cursor()
            c.execute('''INSERT INTO abuse_reports 
                         (image_hash, image_url, reporter_id, reporter_device, reporter_contact, reason)
                         VALUES (?, ?, ?, ?, ?, ?)''', 
                      (image_hash, image_url, reporter_id, reporter_device, reporter_contact, reason))
            conn.commit()
            logger.warning(f"🚨 收到举报: hash={image_hash}, url={image_url}, reason={reason[:50]}")
            return {"success": True, "id": c.lastrowid}
    except Exception as e:
        logger.error(f"Create abuse report failed: {e}")
        return {"success": False, "error": str(e)}

def get_abuse_reports(status: str = None, page: int = 1, page_size: int = 20) -> Dict:
    """获取举报列表 (管理员用)"""
    try:
        with get_db_connection() as conn:
            conn.row_factory = sqlite3.Row
            c = conn.cursor()
            
            conditions = []
            params = []
            
            if status:
                conditions.append("status = ?")
                params.append(status)
            
            where_clause = " WHERE " + " AND ".join(conditions) if conditions else ""
            
            # 获取总数
            c.execute(f"SELECT count(*) FROM abuse_reports{where_clause}", params)
            total = c.fetchone()[0]
            
            # 获取分页数据
            offset = (page - 1) * page_size
            query = f"SELECT * FROM abuse_reports{where_clause} ORDER BY created_at DESC LIMIT ? OFFSET ?"
            params.extend([page_size, offset])
            
            c.execute(query, params)
            data = [dict(row) for row in c.fetchall()]
            
            return {"success": True, "data": data, "total": total, "page": page}
    except Exception as e:
        logger.error(f"Get abuse reports failed: {e}")
        return {"success": False, "error": str(e), "data": [], "total": 0}

def resolve_abuse_report(report_id: int, admin_notes: str = "") -> bool:
    """处理举报 (管理员用)"""
    try:
        with get_db_connection() as conn:
            c = conn.cursor()
            c.execute('''UPDATE abuse_reports 
                         SET status = 'resolved', admin_notes = ?, resolved_at = CURRENT_TIMESTAMP 
                         WHERE id = ?''', (admin_notes, report_id))
            conn.commit()
            logger.info(f"✅ 举报 #{report_id} 已处理")
            return True
    except Exception as e:
        logger.error(f"Resolve report failed: {e}")
        return False

def get_pending_reports_count() -> int:
    """获取待处理举报数量"""
    try:
        with get_db_connection() as conn:
            c = conn.cursor()
            c.execute("SELECT count(*) FROM abuse_reports WHERE status = 'pending'")
            return c.fetchone()[0]
    except Exception as e:
        logger.error(f"Get pending reports count failed: {e}")
        return 0

def get_admin_stats() -> Dict[str, int]:
    """获取管理后台统计数据"""
    try:
        with get_db_connection() as conn:
            c = conn.cursor()
            
            # 1. 待处理举报
            c.execute("SELECT COUNT(*) FROM abuse_reports WHERE status = 'pending'")
            pending_reports = c.fetchone()[0]
            
            # 2. 全站图片
            c.execute("SELECT COUNT(*) FROM history")
            total_images = c.fetchone()[0]
            
            # 3. 注册用户
            c.execute("SELECT COUNT(*) FROM users")
            total_users = c.fetchone()[0]
            
            # 4. 今日上传
            c.execute("SELECT COUNT(*) FROM history WHERE date(created_at) = date('now', 'localtime')")
            today_uploads = c.fetchone()[0]
            
            return {
                "pending_reports": pending_reports,
                "total_images": total_images,
                "total_users": total_users,
                "today_uploads": today_uploads
            }
    except Exception as e:
        logger.error(f"获取统计失败: {e}")
        return {}

def get_abuse_reports(page: int = 1, page_size: int = 50, status: str = None) -> Dict[str, Any]:
    """获取举报列表 (支持分页和状态筛选)"""
    try:
        with get_db_connection() as conn:
            conn.row_factory = sqlite3.Row
            c = conn.cursor()
            
            offset = (page - 1) * page_size
            
            # 关联 history 表，获取正确的 /mycloud/xxx URL
            query = """
                SELECT r.*, h.url as actual_image_url 
                FROM abuse_reports r
                LEFT JOIN history h ON r.image_hash = h.hash
            """
            params = []
            
            if status:
                query += " WHERE r.status = ?"
                params.append(status)
            
            query += " ORDER BY r.created_at DESC LIMIT ? OFFSET ?"
            params.extend([page_size, offset])
            
            c.execute(query, params)
            rows = c.fetchall()
            
            data = []
            for row in rows:
                item = dict(row)
                # 如果有 actual_image_url (来自 history 表)，优先使用它
                # 否则保留原始的 image_url (可能是外部链接)
                if item.get('actual_image_url'):
                    item['image_url'] = item['actual_image_url']
                data.append(item)
            
            # 获取总数
            count_query = "SELECT COUNT(*) FROM abuse_reports"
            count_params = []
            if status:
                count_query += " WHERE status = ?"
                count_params.append(status)
                
            c.execute(count_query, count_params)
            total = c.fetchone()[0]
            
            return {
                "success": True,
                "data": data,
                "total": total,
                "page": page,
                "page_size": page_size
            }
    except Exception as e:
        logger.error(f"获取举报列表失败: {e}")
        return {"success": False, "error": str(e)}

def resolve_abuse_report(report_id: int, admin_notes: str = None) -> bool:
    """标记举报为已处理"""
    try:
        with get_db_connection() as conn:
            c = conn.cursor()
            c.execute("""
                UPDATE abuse_reports 
                SET status = 'resolved', resolved_at = CURRENT_TIMESTAMP, admin_notes = ? 
                WHERE id = ?
            """, (admin_notes, report_id))
            conn.commit()
            return True
    except Exception as e:
        logger.error(f"处理举报失败: {e}")
        return False

def create_abuse_report(image_hash: str, image_url: str, reason: str, reporter_id: int = None, reporter_device: str = None, reporter_contact: str = None) -> Dict[str, Any]:
    """创建举报记录"""
    try:
        with get_db_connection() as conn:
            c = conn.cursor()
            c.execute("""
                INSERT INTO abuse_reports (image_hash, image_url, reason, reporter_id, reporter_device, reporter_contact)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (image_hash, image_url, reason, reporter_id, reporter_device, reporter_contact))
            conn.commit()
            return {"success": True, "id": c.lastrowid}
    except Exception as e:
        logger.error(f"创建举报失败: {e}")
        return {"success": False, "error": str(e)}

def get_notifications(user_id: int = None, device_id: str = None, unread_only: bool = False) -> List[Dict[str, Any]]:
    """获取用户通知"""
    try:
        with get_db_connection() as conn:
            conn.row_factory = sqlite3.Row
            c = conn.cursor()
            
            query = "SELECT * FROM user_notifications WHERE 1=1"
            params = []
            
            # 用户或设备至少满足其一 (通常是 OR 关系，但这里简化为分别查)
            # 实际上通知通常是发给特定用户或特定设备的
            # 暂且实现为: 如果有 user_id 查 user_id, 否则查 device_id
            if user_id:
                query += " AND user_id = ?"
                params.append(user_id)
            elif device_id:
                query += " AND device_id = ?"
                params.append(device_id)
            else:
                return []
                
            if unread_only:
                query += " AND is_read = 0"
                
            query += " ORDER BY created_at DESC LIMIT 50"
            
            c.execute(query, params)
            rows = c.fetchall()
            return [dict(row) for row in rows]
    except Exception as e:
        logger.error(f"获取通知失败: {e}")
        return []

def mark_notification_read(notification_id: int) -> bool:
    """标记通知已读"""
    try:
        with get_db_connection() as conn:
            c = conn.cursor()
            c.execute("UPDATE user_notifications SET is_read = 1 WHERE id = ?", (notification_id,))
            conn.commit()
            return True
    except Exception as e:
        return False


# ==================== 批量操作函数 ====================

def batch_resolve_reports(report_ids: List[int], admin_notes: str = None) -> Dict[str, Any]:
    """
    批量标记多条举报为已处理
    
    Args:
        report_ids: 要处理的举报 ID 列表
        admin_notes: 处理备注（可选）
        
    Returns:
        dict: {"success": True, "resolved_count": N}
    """
    if not report_ids:
        return {"success": False, "error": "No IDs provided", "resolved_count": 0}
        
    try:
        with get_db_connection() as conn:
            c = conn.cursor()
            placeholders = ','.join(['?'] * len(report_ids))
            params = [admin_notes] + report_ids
            c.execute(f"""
                UPDATE abuse_reports 
                SET status = 'resolved', resolved_at = CURRENT_TIMESTAMP, admin_notes = ? 
                WHERE id IN ({placeholders})
            """, params)
            conn.commit()
            return {"success": True, "resolved_count": c.rowcount}
    except Exception as e:
        logger.error(f"批量处理举报失败: {e}")
        return {"success": False, "error": str(e), "resolved_count": 0}


def batch_delete_images_by_hashes(hashes: List[str]) -> Dict[str, Any]:
    """
    批量删除多张图片的数据库记录
    
    Args:
        hashes: 要删除的图片 hash 列表
        
    Returns:
        dict: {"success": True, "deleted_count": N, "failed_hashes": [...]}
    
    Note:
        此函数只删除数据库记录，MinIO 文件需在调用方处理
    """
    if not hashes:
        return {"success": False, "error": "No hashes provided", "deleted_count": 0}
        
    deleted_count = 0
    failed_hashes = []
    
    try:
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
                    logger.error(f"删除图片 {h} 失败: {e}")
                    failed_hashes.append(h)
            conn.commit()
            
        return {
            "success": True, 
            "deleted_count": deleted_count,
            "failed_hashes": failed_hashes
        }
    except Exception as e:
        logger.error(f"批量删除图片失败: {e}")
        return {"success": False, "error": str(e), "deleted_count": deleted_count}


def create_auto_admin() -> bool:
    """
    从环境变量自动创建管理员账户 (仅在应用启动时调用一次)
    
    环境变量:
        AUTO_ADMIN_USERNAME: 管理员用户名
        AUTO_ADMIN_PASSWORD: 管理员密码 (明文，会自动哈希)
    
    Returns:
        bool: 是否成功创建或已存在管理员
    """
    from passlib.hash import bcrypt
    
    username = os.getenv("AUTO_ADMIN_USERNAME")
    password = os.getenv("AUTO_ADMIN_PASSWORD")
    
    if not username or not password:
        # 没有配置环境变量，跳过
        return False
    
    try:
        # 检查用户是否已存在
        existing = get_user_by_username(username)
        if existing:
            # 用户已存在，确保是管理员
            if not existing.get("is_admin"):
                with get_db_connection() as conn:
                    c = conn.cursor()
                    c.execute("UPDATE users SET is_admin = 1 WHERE username = ?", (username,))
                    conn.commit()
                logger.info(f"✅ [Auto Admin] 已将用户 '{username}' 提升为管理员")
            else:
                logger.info(f"✅ [Auto Admin] 管理员 '{username}' 已存在")
            return True
        
        # 创建新用户
        password_hash = bcrypt.hash(password)
        with get_db_connection() as conn:
            c = conn.cursor()
            c.execute(
                "INSERT INTO users (username, password_hash, is_admin) VALUES (?, ?, 1)",
                (username, password_hash)
            )
            conn.commit()
        logger.info(f"✅ [Auto Admin] 已自动创建管理员账户: {username}")
        return True
        
    except Exception as e:
        logger.error(f"❌ [Auto Admin] 创建管理员失败: {e}")
        return False
