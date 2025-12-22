# -*- coding: utf-8 -*-
"""
文件验证服务模块

提供文件上传的安全验证功能，包括：
- 文件魔数（Magic Number）验证 - 检测真实文件类型
- 文件名安全检查 - 防止恶意字符注入
- 路径遍历攻击防护
- 文件大小限制检查
"""
import os
import re
import logging
from typing import Optional, Dict, Tuple
from dataclasses import dataclass

from fastapi import HTTPException

# 设置日志记录器
logger = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    """验证结果数据类"""
    is_valid: bool
    error_message: Optional[str] = None
    sanitized_filename: Optional[str] = None
    detected_mime_type: Optional[str] = None


class FileValidator:
    """
    文件上传安全验证器
    
    提供多层次的文件安全验证，确保上传文件的安全性。
    
    Attributes:
        MAGIC_NUMBERS: 文件魔数映射表，用于检测真实文件类型
        DANGEROUS_CHARS: 危险字符正则表达式
        MAX_FILENAME_LENGTH: 最大文件名长度
    
    Example:
        >>> validator = FileValidator()
        >>> result = validator.validate_all(
        ...     filename="test.jpg",
        ...     content=image_bytes,
        ...     max_size=10*1024*1024
        ... )
        >>> if not result.is_valid:
        ...     raise HTTPException(400, result.error_message)
    """
    
    # 文件魔数（Magic Numbers）用于检测真实文件类型
    # 格式: (魔数字节, 偏移量) -> MIME类型
    MAGIC_NUMBERS: Dict[bytes, str] = {
        b'\xff\xd8\xff': 'image/jpeg',           # JPEG
        b'\x89PNG\r\n\x1a\n': 'image/png',       # PNG
        b'GIF87a': 'image/gif',                   # GIF87a
        b'GIF89a': 'image/gif',                   # GIF89a
        b'RIFF': 'image/webp',                    # WebP (需额外检查)
        b'\x00\x00\x00': 'image/avif',           # AVIF/HEIC (需额外检查)
        b'BM': 'image/bmp',                       # BMP
    }
    
    # WebP 特殊魔数 (RIFF....WEBP)
    WEBP_SIGNATURE = b'WEBP'
    
    # AVIF/HEIC 特殊检测 (ftyp box)
    AVIF_BRANDS = [b'avif', b'avis', b'mif1']
    HEIC_BRANDS = [b'heic', b'heix', b'hevc', b'hevx', b'mif1']
    
    # 危险字符正则 (用于文件名清理)
    DANGEROUS_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
    
    # 路径遍历模式
    PATH_TRAVERSAL_PATTERNS = ['..', './', '.\\', '~']
    
    # 最大文件名长度
    MAX_FILENAME_LENGTH = 255
    
    def __init__(self, allowed_extensions: Optional[set] = None):
        """
        初始化验证器
        
        Args:
            allowed_extensions: 允许的文件扩展名集合，默认为常见图片格式
        """
        self.allowed_extensions = allowed_extensions or {
            '.jpg', '.jpeg', '.png', '.gif', '.webp',
            '.avif', '.heic', '.heif', '.bmp', '.svg', '.ico'
        }
    
    def validate_magic_number(self, content: bytes) -> Tuple[bool, Optional[str]]:
        """
        通过文件魔数验证文件真实类型
        
        检查文件头部的魔数字节，判断文件是否为真实的图片文件。
        防止恶意文件伪装成图片上传。
        
        Args:
            content: 文件二进制内容
        
        Returns:
            Tuple[bool, Optional[str]]: (是否有效, 检测到的MIME类型)
        
        Example:
            >>> is_valid, mime = validator.validate_magic_number(image_bytes)
            >>> print(f"有效: {is_valid}, 类型: {mime}")
        """
        if len(content) < 12:
            return False, None
        
        header = content[:12]
        
        # 检查基本魔数
        for magic, mime_type in self.MAGIC_NUMBERS.items():
            if header.startswith(magic):
                # WebP 需要额外检查
                if magic == b'RIFF' and len(content) >= 12:
                    if content[8:12] == self.WEBP_SIGNATURE:
                        return True, 'image/webp'
                    continue
                
                # AVIF/HEIC 需要检查 ftyp box
                if magic == b'\x00\x00\x00' and len(content) >= 12:
                    ftyp_brand = content[8:12]
                    if any(brand in ftyp_brand for brand in self.AVIF_BRANDS):
                        return True, 'image/avif'
                    if any(brand in ftyp_brand for brand in self.HEIC_BRANDS):
                        return True, 'image/heic'
                    continue
                
                return True, mime_type
        
        # SVG 特殊处理（文本格式）
        try:
            text_header = content[:1000].decode('utf-8', errors='ignore').lower()
            if '<svg' in text_header and 'xmlns' in text_header:
                return True, 'image/svg+xml'
        except Exception:
            pass
        
        # ICO 格式检查
        if content[:4] == b'\x00\x00\x01\x00':
            return True, 'image/x-icon'
        
        return False, None
    
    def sanitize_filename(self, filename: str) -> str:
        """
        清理并安全化文件名
        
        移除危险字符，防止注入攻击，限制文件名长度。
        
        Args:
            filename: 原始文件名
        
        Returns:
            str: 安全化后的文件名
        
        Example:
            >>> safe_name = validator.sanitize_filename("../../../etc/passwd.jpg")
            >>> print(safe_name)  # "etc_passwd.jpg"
        """
        if not filename:
            return "unnamed"
        
        # 移除路径部分，只保留文件名
        filename = os.path.basename(filename)
        
        # 移除路径遍历模式
        for pattern in self.PATH_TRAVERSAL_PATTERNS:
            filename = filename.replace(pattern, '')
        
        # 移除危险字符
        filename = self.DANGEROUS_CHARS.sub('_', filename)
        
        # 移除前导和尾随空格/点
        filename = filename.strip(' .')
        
        # 限制长度
        if len(filename) > self.MAX_FILENAME_LENGTH:
            name, ext = os.path.splitext(filename)
            max_name_len = self.MAX_FILENAME_LENGTH - len(ext)
            filename = name[:max_name_len] + ext
        
        return filename or "unnamed"
    
    def validate_path_traversal(self, path: str) -> None:
        """
        检查路径遍历攻击
        
        检测并阻止任何可能导致路径遍历的模式。
        
        Args:
            path: 要检查的路径
        
        Raises:
            HTTPException (400): 检测到路径遍历攻击
        """
        if not path:
            return
        
        # 检查常见遍历模式
        dangerous_patterns = [
            '..',           # 上级目录
            './',           # 当前目录
            '.\\',          # Windows 当前目录
            '~',            # 用户目录
            '%2e%2e',       # URL 编码的 ..
            '%252e%252e',   # 双重 URL 编码
        ]
        
        path_lower = path.lower()
        for pattern in dangerous_patterns:
            if pattern.lower() in path_lower:
                logger.warning(f"🚨 检测到路径遍历攻击: {path}")
                raise HTTPException(status_code=400, detail="非法路径")
        
        # 检查绝对路径
        if path.startswith('/') or path.startswith('\\'):
            logger.warning(f"🚨 检测到绝对路径: {path}")
            raise HTTPException(status_code=400, detail="非法路径")
        
        # Windows 驱动器路径检查
        if len(path) >= 2 and path[1] == ':':
            logger.warning(f"🚨 检测到Windows驱动器路径: {path}")
            raise HTTPException(status_code=400, detail="非法路径")
    
    def validate_extension(self, filename: str) -> Tuple[bool, str]:
        """
        验证文件扩展名
        
        Args:
            filename: 文件名
        
        Returns:
            Tuple[bool, str]: (是否有效, 扩展名)
        """
        ext = os.path.splitext(filename)[1].lower()
        is_valid = ext in self.allowed_extensions
        return is_valid, ext
    
    def validate_file_size(
        self, 
        content: bytes, 
        max_size: int,
        is_vip: bool = False
    ) -> None:
        """
        验证文件大小
        
        Args:
            content: 文件内容
            max_size: 最大允许大小（字节）
            is_vip: 是否为VIP用户
        
        Raises:
            HTTPException (400): 文件超过大小限制
        """
        file_size = len(content)
        if file_size > max_size:
            size_mb = max_size // (1024 * 1024)
            upgrade_hint = "" if is_vip else " 请升级 VIP 解锁更大文件限制。"
            logger.warning(f"⚠️ 文件过大: {file_size} bytes > {max_size} bytes")
            raise HTTPException(
                status_code=400,
                detail=f"文件过大，当前限制 {size_mb}MB。{upgrade_hint}"
            )
    
    def validate_all(
        self,
        filename: str,
        content: bytes,
        max_size: int,
        is_vip: bool = False,
        check_magic: bool = True
    ) -> ValidationResult:
        """
        执行完整的文件验证
        
        综合执行所有验证步骤：大小、扩展名、魔数、文件名安全化。
        
        Args:
            filename: 原始文件名
            content: 文件二进制内容
            max_size: 最大文件大小
            is_vip: 是否为VIP用户
            check_magic: 是否检查文件魔数
        
        Returns:
            ValidationResult: 验证结果对象
        
        Example:
            >>> result = validator.validate_all("test.jpg", content, 10*1024*1024)
            >>> if result.is_valid:
            ...     safe_filename = result.sanitized_filename
        """
        try:
            # 1. 检查文件大小
            self.validate_file_size(content, max_size, is_vip)
            
            # 2. 安全化文件名
            safe_filename = self.sanitize_filename(filename)
            
            # 3. 检查扩展名
            ext_valid, ext = self.validate_extension(safe_filename)
            if not ext_valid:
                allowed = ', '.join(sorted(self.allowed_extensions))
                return ValidationResult(
                    is_valid=False,
                    error_message=f"不支持的文件类型: {ext}，允许的类型: {allowed}"
                )
            
            # 4. 检查文件魔数（可选但推荐）
            detected_mime = None
            if check_magic:
                magic_valid, detected_mime = self.validate_magic_number(content)
                if not magic_valid:
                    logger.warning(f"⚠️ 文件魔数验证失败: {filename}")
                    # 对于某些格式（如 SVG、ICO），魔数检测可能不准确
                    # 这里只记录警告，不直接拒绝
                    if ext not in {'.svg', '.ico'}:
                        return ValidationResult(
                            is_valid=False,
                            error_message="文件内容与扩展名不匹配，请确保上传真实的图片文件"
                        )
            
            logger.debug(f"✅ 文件验证通过: {safe_filename} (MIME: {detected_mime})")
            
            return ValidationResult(
                is_valid=True,
                sanitized_filename=safe_filename,
                detected_mime_type=detected_mime
            )
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"❌ 文件验证异常: {e}")
            return ValidationResult(
                is_valid=False,
                error_message=f"文件验证失败: {str(e)}"
            )


# 创建默认验证器实例
default_validator = FileValidator()
