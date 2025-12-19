# -*- coding: utf-8 -*-
from slowapi import Limiter
from slowapi.util import get_remote_address

# 初始化 Limiter, 使用 IP 地址作为 Key
# 默认限流：每分钟 200 次
limiter = Limiter(key_func=get_remote_address, default_limits=["200/minute"])
