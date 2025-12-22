# -*- coding: utf-8 -*-
"""
日志配置模块

提供结构化的日志配置，支持：
- 按文件大小轮转（RotatingFileHandler）
- 同时输出到控制台和文件
- 可配置的日志级别
- 统一的日志格式
"""
import os
import sys
import logging
from logging.handlers import RotatingFileHandler
from typing import Optional


# 默认日志格式
DEFAULT_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
DEFAULT_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

# 默认配置
DEFAULT_LOG_DIR = "logs"
DEFAULT_LOG_FILE = "app.log"
DEFAULT_MAX_BYTES = 10 * 1024 * 1024  # 10MB
DEFAULT_BACKUP_COUNT = 5


def setup_logging(
    log_file: Optional[str] = None,
    log_dir: str = DEFAULT_LOG_DIR,
    max_bytes: int = DEFAULT_MAX_BYTES,
    backup_count: int = DEFAULT_BACKUP_COUNT,
    log_level: int = logging.INFO,
    console_level: Optional[int] = None,
    log_format: str = DEFAULT_FORMAT,
    date_format: str = DEFAULT_DATE_FORMAT
) -> logging.Logger:
    """
    配置应用日志系统
    
    设置日志轮转、格式化、多输出目标等。
    
    Args:
        log_file: 日志文件名，默认 "app.log"
        log_dir: 日志目录，默认 "logs"
        max_bytes: 单个日志文件最大大小（字节），默认 10MB
        backup_count: 保留的备份文件数量，默认 5
        log_level: 文件日志级别，默认 INFO
        console_level: 控制台日志级别，默认与文件级别相同
        log_format: 日志格式字符串
        date_format: 日期格式字符串
    
    Returns:
        logging.Logger: 配置好的根日志记录器
    
    Example:
        >>> from backend.logging_config import setup_logging
        >>> logger = setup_logging(log_level=logging.DEBUG)
        >>> logger.info("应用启动")
    
    Note:
        - 日志文件会在 {log_dir}/{log_file} 路径创建
        - 当文件超过 max_bytes 时会自动轮转
        - 最多保留 backup_count 个备份文件
    """
    # 确保日志目录存在
    if log_dir:
        os.makedirs(log_dir, exist_ok=True)
    
    # 构建完整路径
    log_file = log_file or DEFAULT_LOG_FILE
    log_path = os.path.join(log_dir, log_file) if log_dir else log_file
    
    # 控制台级别默认与文件级别相同
    if console_level is None:
        console_level = log_level
    
    # 创建格式化器
    formatter = logging.Formatter(log_format, date_format)
    
    # 获取根日志记录器
    root_logger = logging.getLogger()
    root_logger.setLevel(min(log_level, console_level))
    
    # 清除现有处理器（避免重复添加）
    root_logger.handlers.clear()
    
    # 1. 控制台处理器
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(console_level)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)
    
    # 2. 文件处理器（带轮转）
    try:
        file_handler = RotatingFileHandler(
            log_path,
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding='utf-8'
        )
        file_handler.setLevel(log_level)
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)
        
        root_logger.info(f"📝 日志系统已初始化: {log_path} (最大 {max_bytes // (1024*1024)}MB, 保留 {backup_count} 个备份)")
    except Exception as e:
        root_logger.warning(f"⚠️ 无法创建日志文件 {log_path}: {e}，仅使用控制台输出")
    
    return root_logger


def get_logger(name: str) -> logging.Logger:
    """
    获取指定名称的日志记录器
    
    Args:
        name: 日志记录器名称，通常使用 __name__
    
    Returns:
        logging.Logger: 日志记录器实例
    
    Example:
        >>> from backend.logging_config import get_logger
        >>> logger = get_logger(__name__)
        >>> logger.info("模块已加载")
    """
    return logging.getLogger(name)


# 快捷配置函数
def setup_development_logging() -> logging.Logger:
    """
    配置开发环境日志
    
    - DEBUG 级别
    - 输出到控制台和文件
    - 较小的文件大小限制
    """
    return setup_logging(
        log_level=logging.DEBUG,
        max_bytes=5 * 1024 * 1024,  # 5MB
        backup_count=3
    )


def setup_production_logging() -> logging.Logger:
    """
    配置生产环境日志
    
    - INFO 级别
    - 输出到控制台和文件
    - 较大的文件大小限制
    """
    return setup_logging(
        log_level=logging.INFO,
        max_bytes=50 * 1024 * 1024,  # 50MB
        backup_count=10
    )
