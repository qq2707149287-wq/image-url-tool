import os
import mimetypes
import logging
from typing import Any, Optional

import boto3
from botocore.client import Config

logger = logging.getLogger(__name__)

# 全局 S3 客户端实例
_s3_client: Optional[Any] = None
MINIO_BUCKET_NAME = "images"  # 默认值，会从环境变量更新


def get_s3_client() -> Optional[Any]:
    """获取 S3 客户端实例（延迟初始化）"""
    global _s3_client, MINIO_BUCKET_NAME
    if _s3_client is None:
        # 延迟读取环境变量，确保 load_dotenv() 已执行
        minio_endpoint = os.getenv("MINIO_ENDPOINT")
        minio_access_key = os.getenv("MINIO_ACCESS_KEY")
        minio_secret_key = os.getenv("MINIO_SECRET_KEY")
        MINIO_BUCKET_NAME = os.getenv("MINIO_BUCKET_NAME", "images")

        if not all([minio_endpoint, minio_access_key, minio_secret_key]):
            logger.warning("⚠️  MinIO 配置缺失！请检查 .env 文件或环境变量。")
            return None

        _s3_client = boto3.client(
            "s3",
            endpoint_url=minio_endpoint,
            aws_access_key_id=minio_access_key,
            aws_secret_access_key=minio_secret_key,
            config=Config(signature_version="s3v4")
        )
    return _s3_client

def upload_to_minio(data: bytes, name: str, fhash: str) -> dict[str, Any]:
    """
    上传文件到 MinIO 存储

    Args:
        data: 文件内容
        name: 原始文件名
        fhash: 文件哈希值

    Returns:
        包含上传结果的字典
    """
    logger.info(f"[MyCloud] 正在上传 {name[:40]}...")
    try:
        s3 = get_s3_client()
        if not s3:
            raise RuntimeError("MinIO 客户端未初始化")

        ext = os.path.splitext(name)[1] or ".jpg"
        key = f"{fhash}{ext}"

        # 确定 MIME 类型
        content_type, _ = mimetypes.guess_type(name)
        if not content_type:
            # AVIF 的额外处理
            if name.lower().endswith('.avif'):
                content_type = 'image/avif'
            else:
                content_type = "application/octet-stream"

        s3.put_object(
            Bucket=MINIO_BUCKET_NAME,
            Key=key,
            Body=data,
            ContentType=content_type
        )

        url = f"/mycloud/{key}"  # 使用相对路径代理

        logger.info("✅ [MyCloud] 成功")
        return {
            "success": True,
            "service": "MyCloud",
            "url": url,
            "key": key,
            "content_type": content_type
        }
    except Exception as e:
        logger.error(f"❌ [MyCloud] 错误: {e}")
        return {
            "success": False,
            "service": "MyCloud",
            "error": str(e)
        }


def get_minio_object(object_name: str) -> dict[str, Any]:
    """
    从 MinIO 获取对象

    Args:
        object_name: 对象键名

    Returns:
        S3 对象响应

    Raises:
        Exception: 获取对象失败时抛出
    """
    s3 = get_s3_client()
    if not s3:
        raise RuntimeError("MinIO 客户端未初始化")

    try:
        obj = s3.get_object(Bucket=MINIO_BUCKET_NAME, Key=object_name)
        return obj
    except Exception as e:
        logger.warning(f"❌ 读取 MyCloud 对象失败: {e}")
        raise
