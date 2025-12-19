# -*- coding: utf-8 -*-
# backend/database.py
# ============================================================
# 喵～ 重构后的兼容层
# ============================================================
# 这个文件现在是一个"代理"，将所有调用转发到新的 db/ 模块
# 外部的 `from .. import database` 调用方式完全不需要修改！
#
# 新的模块结构:
#   backend/db/
#   ├── __init__.py       # 统一导出
#   ├── connection.py     # 数据库连接和初始化
#   ├── images.py         # 图片相关操作
#   ├── users.py          # 用户相关操作
#   ├── sessions.py       # 会话管理
#   ├── vip.py            # VIP 系统
#   ├── notifications.py  # 通知系统
#   └── admin.py          # 管理员功能
# ============================================================

# 从新模块导入所有函数，保持向后兼容
from .db import *

# 重新导出 __all__，确保 `from backend.database import *` 也能正常工作
from .db import __all__
