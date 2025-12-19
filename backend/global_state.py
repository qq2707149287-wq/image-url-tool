# -*- coding: utf-8 -*-

# backend/global_state.py
# 全局状态管理，用于在不同模块间共享运行时配置 (打破循环依赖)

# 默认设置
SYSTEM_SETTINGS = {
    "debug_mode": False
}
