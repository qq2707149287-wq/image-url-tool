# backend/db/__init__.py
# 数据库操作模块 - 统一导出所有函数，保持向后兼容
# 喵～这样外部的 `from .. import database` 调用方式完全不需要修改！

# 核心连接和初始化
from .connection import get_db_connection, init_db, DB_PATH

# 图片操作
from .images import (
    save_to_db,
    get_history_list,
    delete_history_items,
    clear_all_history,
    rename_history_item,
    delete_image_by_hash_system,
    get_image_by_hash,
    get_image_by_url,
)

# 用户操作
from .users import (
    create_user,
    get_user_by_username,
    get_user_by_google_id,
    create_google_user,
    get_user_by_email,
    save_verification_code,
    get_valid_verification_code,
    delete_verification_code,
    update_user_password,
    create_email_user,
    update_user_password_by_id,
    update_username,
    delete_user,
    delete_user_history,
    get_user_stats,
    log_user_activity,
    get_user_logs,
    set_user_vip,
    set_user_admin,
)

# 会话管理
from .sessions import (
    create_session,
    get_active_sessions,
    revoke_session,
    validate_session,
    update_session_activity,
)

# VIP 系统
from .vip import (
    activate_vip,
    create_vip_code,
    get_today_upload_count,
)

# 通知系统
from .notifications import (
    create_notification,
    get_notifications,
    mark_notification_read,
    cleanup_old_notifications,
)

# 管理员功能
from .admin import (
    get_admin_stats,
    create_abuse_report,
    get_abuse_reports,
    resolve_abuse_report,
    get_pending_reports_count,
    batch_resolve_reports,
    batch_delete_images_by_hashes,
    create_auto_admin,
)

# 导出所有公共接口
__all__ = [
    # 连接
    'get_db_connection', 'init_db', 'DB_PATH',
    # 图片
    'save_to_db', 'get_history_list', 'delete_history_items', 'clear_all_history',
    'rename_history_item', 'delete_image_by_hash_system', 'get_image_by_hash', 'get_image_by_url',
    # 用户
    'create_user', 'get_user_by_username', 'get_user_by_google_id', 'create_google_user',
    'get_user_by_email', 'save_verification_code', 'get_valid_verification_code', 'delete_verification_code',
    'update_user_password', 'create_email_user', 'update_user_password_by_id', 'update_username',
    'delete_user', 'delete_user_history', 'get_user_stats', 'log_user_activity', 'get_user_logs',
    'set_user_vip', 'set_user_admin',
    # 会话
    'create_session', 'get_active_sessions', 'revoke_session', 'validate_session', 'update_session_activity',
    # VIP
    'activate_vip', 'create_vip_code', 'get_today_upload_count',
    # 通知
    'create_notification', 'get_notifications', 'mark_notification_read', 'cleanup_old_notifications',
    # 管理员
    'get_admin_stats', 'create_abuse_report', 'get_abuse_reports', 'resolve_abuse_report',
    'get_pending_reports_count', 'batch_resolve_reports', 'batch_delete_images_by_hashes', 'create_auto_admin',
]

