# -*- coding: utf-8 -*-
"""
路由模块包

包含所有 API 路由模块：
- auth: 认证相关（登录、注册、密码重置等）
- upload: 文件上传相关
- user: 用户信息相关
- admin: 管理员后台相关
- captcha: 验证码相关
- notifications: 通知相关
- debug: 调试接口
- pages: 静态页面
"""
from . import auth
from . import upload
from . import user
from . import admin
from . import captcha
from . import notifications
from . import debug
from . import pages

__all__ = [
    "auth",
    "upload", 
    "user",
    "admin",
    "captcha",
    "notifications",
    "debug",
    "pages"
]
