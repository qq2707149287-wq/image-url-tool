# -*- coding: utf-8 -*-
# backend/db/schema.py
# 数据库结构定义

# 表结构定义
TABLES = {
    "history": """
        CREATE TABLE IF NOT EXISTS history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
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
            ip_address TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
    """,
    "users": """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            email TEXT UNIQUE,
            is_admin INTEGER DEFAULT 0,
            is_vip INTEGER DEFAULT 0,
            vip_expiry DATETIME,
            google_id TEXT UNIQUE,
            avatar TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """,
    "verification_codes": """
        CREATE TABLE IF NOT EXISTS verification_codes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT NOT NULL,
            code TEXT NOT NULL,
            type TEXT NOT NULL,
            expires_at DATETIME NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """,
    "vip_codes": """
        CREATE TABLE IF NOT EXISTS vip_codes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT UNIQUE NOT NULL,
            days INTEGER NOT NULL,
            is_used INTEGER DEFAULT 0,
            used_by INTEGER,
            used_at DATETIME,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(used_by) REFERENCES users(id)
        )
    """,
    "user_logs": """
        CREATE TABLE IF NOT EXISTS user_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            action TEXT NOT NULL,
            ip_address TEXT,
            user_agent TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
    """,
    "user_sessions": """
        CREATE TABLE IF NOT EXISTS user_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            session_id TEXT UNIQUE NOT NULL,
            device_info TEXT,
            ip_address TEXT,
            last_active TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
        )
    """,
    "user_notifications": """
        CREATE TABLE IF NOT EXISTS user_notifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            device_id TEXT,
            type TEXT NOT NULL,
            title TEXT,
            message TEXT NOT NULL,
            is_read INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
        )
    """,
    "abuse_reports": """
        CREATE TABLE IF NOT EXISTS abuse_reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
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
            FOREIGN KEY(reporter_id) REFERENCES users(id)
        )
    """
}

# 索引定义
INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_filename ON history (filename)",
    "CREATE INDEX IF NOT EXISTS idx_url ON history (url)",
    "CREATE INDEX IF NOT EXISTS idx_device_id ON history (device_id)",
    "CREATE INDEX IF NOT EXISTS idx_is_shared ON history (is_shared)",
    "CREATE INDEX IF NOT EXISTS idx_user_id ON history (user_id)",
    "CREATE INDEX IF NOT EXISTS idx_username ON users (username)",
    "CREATE UNIQUE INDEX IF NOT EXISTS idx_google_id ON users (google_id)",
    "CREATE UNIQUE INDEX IF NOT EXISTS idx_users_email ON users(email)",
    "CREATE INDEX IF NOT EXISTS idx_logs_user_id ON user_logs(user_id)",
    "CREATE INDEX IF NOT EXISTS idx_notif_user ON user_notifications(user_id)",
    "CREATE INDEX IF NOT EXISTS idx_notif_device ON user_notifications(device_id)",
    "CREATE INDEX IF NOT EXISTS idx_report_status ON abuse_reports(status)",
    "CREATE INDEX IF NOT EXISTS idx_report_hash ON abuse_reports(image_hash)",
]
