# -*- coding: utf-8 -*-
"""
静态页面路由模块

提供静态HTML页面的路由，如服务条款、隐私政策、举报页面等。
"""
import os
import logging
from typing import Union

from fastapi import APIRouter
from fastapi.responses import FileResponse

# 设置日志记录器
logger = logging.getLogger(__name__)

# 创建路由器
router = APIRouter(tags=["页面"])

# 前端目录路径
FRONTEND_DIR = "frontend"
PAGES_DIR = os.path.join(FRONTEND_DIR, "pages")


def _serve_page(filepath: str, disable_cache: bool = False) -> FileResponse:
    """
    服务静态页面的通用函数
    
    Args:
        filepath: 页面文件路径
        disable_cache: 是否禁用缓存
    
    Returns:
        FileResponse: 文件响应对象
    """
    response = FileResponse(filepath)
    
    if disable_cache:
        # 禁止缓存，确保前端更新立即生效
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    
    return response


@router.get("/terms")
def terms_page() -> FileResponse:
    """
    服务条款页面
    
    返回服务条款HTML页面。
    
    Returns:
        FileResponse: 服务条款页面
    """
    return _serve_page(os.path.join(PAGES_DIR, "terms.html"))


@router.get("/privacy")
def privacy_page() -> FileResponse:
    """
    隐私政策页面
    
    返回隐私政策HTML页面。
    
    Returns:
        FileResponse: 隐私政策页面
    """
    return _serve_page(os.path.join(PAGES_DIR, "privacy.html"))


@router.get("/report")
def report_page() -> FileResponse:
    """
    举报页面
    
    返回内容举报HTML页面。
    
    Returns:
        FileResponse: 举报页面
    """
    return _serve_page(os.path.join(PAGES_DIR, "report.html"))


@router.get("/admin")
def admin_page() -> FileResponse:
    """
    管理员后台页面
    
    返回管理员后台HTML页面。
    禁用缓存以确保前端更新立即生效。
    
    Returns:
        FileResponse: 管理员后台页面（无缓存）
    """
    return _serve_page(os.path.join(FRONTEND_DIR, "admin.html"), disable_cache=True)
