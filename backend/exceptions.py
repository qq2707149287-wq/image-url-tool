# -*- coding: utf-8 -*-
"""
自定义异常模块

提供统一的异常处理机制，用于：
- 标准化错误响应格式
- 区分不同类型的业务错误
- 提供友好的中文错误消息
- 避免向客户端暴露敏感信息
"""
from typing import Optional, Any, Dict


class ImageToolException(Exception):
    """
    图床工具基础异常类
    
    所有自定义业务异常的基类，提供统一的错误响应格式。
    
    Attributes:
        message: 用户友好的错误消息（中文）
        code: 错误代码，用于客户端识别错误类型
        status_code: HTTP 状态码
        details: 额外的错误详情（仅用于日志，不返回给客户端）
    
    Example:
        >>> raise ImageToolException("操作失败", code="OPERATION_FAILED", status_code=400)
    """
    
    def __init__(
        self,
        message: str,
        code: str = "UNKNOWN_ERROR",
        status_code: int = 400,
        details: Optional[Any] = None
    ):
        """
        初始化异常
        
        Args:
            message: 用户友好的错误消息
            code: 错误代码
            status_code: HTTP 状态码
            details: 内部错误详情（不暴露给客户端）
        """
        super().__init__(message)
        self.message = message
        self.code = code
        self.status_code = status_code
        self.details = details
    
    def to_response(self) -> Dict[str, Any]:
        """
        转换为标准响应格式
        
        Returns:
            Dict[str, Any]: 适合返回给客户端的错误响应
        """
        return {
            "success": False,
            "error": {
                "code": self.code,
                "message": self.message
            }
        }
    
    def __str__(self) -> str:
        return f"[{self.code}] {self.message}"


class FileValidationError(ImageToolException):
    """
    文件验证失败异常
    
    当上传的文件不符合要求时抛出，例如：
    - 文件类型不支持
    - 文件大小超限
    - 文件内容无效
    """
    
    def __init__(
        self,
        message: str = "文件验证失败",
        details: Optional[Any] = None
    ):
        super().__init__(
            message=message,
            code="FILE_VALIDATION_ERROR",
            status_code=400,
            details=details
        )


class FileSizeError(FileValidationError):
    """
    文件大小超限异常
    """
    
    def __init__(
        self,
        max_size_mb: int,
        is_vip: bool = False
    ):
        upgrade_hint = "" if is_vip else " 请升级 VIP 解锁更大文件限制。"
        super().__init__(
            message=f"文件过大，当前限制 {max_size_mb}MB。{upgrade_hint}"
        )


class FileTypeError(FileValidationError):
    """
    文件类型不支持异常
    """
    
    def __init__(
        self,
        extension: str,
        allowed: str
    ):
        super().__init__(
            message=f"不支持的文件类型: {extension}，允许的类型: {allowed}"
        )


class RateLimitError(ImageToolException):
    """
    请求频率超限异常
    
    当用户请求频率超过限制时抛出。
    """
    
    def __init__(
        self,
        message: str = "请求过于频繁，请稍后再试",
        retry_after: Optional[int] = None
    ):
        super().__init__(
            message=message,
            code="RATE_LIMIT_EXCEEDED",
            status_code=429,
            details={"retry_after": retry_after} if retry_after else None
        )


class UploadLimitError(RateLimitError):
    """
    上传限额已达异常
    """
    
    def __init__(
        self,
        user_type: str,
        limit: int,
        is_logged_in: bool = False,
        is_vip: bool = False
    ):
        message = f"{user_type}每日限额 {limit} 张，您已达标。"
        
        if not is_logged_in:
            message += " 请登录以获取更多额度 (5张/日)。"
        elif not is_vip:
            message += " 请激活 VIP 解锁无限上传！"
        
        super().__init__(message=message)
        self.code = "UPLOAD_LIMIT_EXCEEDED"


class AuditRejectError(ImageToolException):
    """
    内容审核拒绝异常
    
    当上传的内容未通过安全审核时抛出。
    """
    
    def __init__(
        self,
        reason: str = "内容未通过安全审核"
    ):
        super().__init__(
            message=f"上传失败：{reason}",
            code="CONTENT_REJECTED",
            status_code=400
        )


class AuthenticationError(ImageToolException):
    """
    认证失败异常
    
    当用户认证失败时抛出，例如：
    - Token 无效或过期
    - 用户名或密码错误
    """
    
    def __init__(
        self,
        message: str = "认证失败，请重新登录"
    ):
        super().__init__(
            message=message,
            code="AUTHENTICATION_FAILED",
            status_code=401
        )


class AuthorizationError(ImageToolException):
    """
    授权失败异常
    
    当用户没有权限执行操作时抛出。
    """
    
    def __init__(
        self,
        message: str = "没有权限执行此操作"
    ):
        super().__init__(
            message=message,
            code="AUTHORIZATION_FAILED",
            status_code=403
        )


class ResourceNotFoundError(ImageToolException):
    """
    资源未找到异常
    """
    
    def __init__(
        self,
        resource_type: str = "资源",
        resource_id: Optional[str] = None
    ):
        message = f"{resource_type}不存在"
        if resource_id:
            message = f"{resource_type} '{resource_id}' 不存在"
        
        super().__init__(
            message=message,
            code="RESOURCE_NOT_FOUND",
            status_code=404
        )


class StorageError(ImageToolException):
    """
    存储服务异常
    
    当存储操作失败时抛出。
    注意：不向客户端暴露具体存储错误详情。
    """
    
    def __init__(
        self,
        message: str = "存储服务暂时不可用，请稍后重试",
        details: Optional[Any] = None
    ):
        super().__init__(
            message=message,
            code="STORAGE_ERROR",
            status_code=503,
            details=details
        )


class DatabaseError(ImageToolException):
    """
    数据库异常
    
    当数据库操作失败时抛出。
    注意：不向客户端暴露具体数据库错误详情。
    """
    
    def __init__(
        self,
        message: str = "服务暂时不可用，请稍后重试",
        details: Optional[Any] = None
    ):
        super().__init__(
            message=message,
            code="DATABASE_ERROR",
            status_code=503,
            details=details
        )
