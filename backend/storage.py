# -*- coding: utf-8 -*-
import os
import mimetypes
import logging
from typing import Any, Optional

import boto3
from botocore.client import Config
from botocore.exceptions import ClientError, EndpointConnectionError, NoCredentialsError

logger = logging.getLogger(__name__)

# 全局 S3 客户端实例
_s3_client: Optional[Any] = None
MINIO_BUCKET_NAME = "images"  # 默认值，会从环境变量更新

# [兼容] 暴露 minio_client 别名，供 main.py 健康检查使用
# 注意: 这是懒加载的，需要先调用 get_s3_client() 初始化
minio_client = None  # 将在 get_s3_client() 中更新


def get_s3_client() -> Optional[Any]:
    """获取 S3 客户端实例（延迟初始化）"""
    global _s3_client, MINIO_BUCKET_NAME, minio_client
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
        
        # [FIX] 确保存储桶存在
        ensure_bucket_exists(_s3_client, MINIO_BUCKET_NAME)
        
        # [兼容] 同步更新全局别名
        minio_client = _s3_client
    return _s3_client

def ensure_bucket_exists(s3_client, bucket_name):
    """确保 MinIO 存储桶存在，如果不存在则创建"""
    try:
        s3_client.head_bucket(Bucket=bucket_name)
    except ClientError as e:
        # 桶不存在（404）或无权限（403）
        error_code = e.response.get('Error', {}).get('Code', '')
        if error_code in ('404', 'NoSuchBucket'):
            _create_bucket_with_policy(s3_client, bucket_name)
        else:
            logger.error(f"❌ 检查存储桶失败 (权限不足?): {e}")
    except EndpointConnectionError as e:
        logger.error(f"❌ 无法连接到存储服务: {e}")
    except Exception as e:
        # 兜底处理未知异常
        logger.error(f"❌ 检查存储桶时发生未知错误: {e}")

def _create_bucket_with_policy(s3_client, bucket_name):
    """创建存储桶并设置公开读策略（内部函数）"""
    try:
        logger.info(f"正在创建存储桶: {bucket_name}")
        s3_client.create_bucket(Bucket=bucket_name)
        logger.info(f"✅ 存储桶已创建: {bucket_name}")
        
        # 设置 Bucket 策略为 public (只读)
        import json
        policy = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Principal": {"AWS": "*"},
                    "Action": ["s3:GetObject"],
                    "Resource": [f"arn:aws:s3:::{bucket_name}/*"]
                }
            ]
        }
        s3_client.put_bucket_policy(Bucket=bucket_name, Policy=json.dumps(policy))
        logger.info(f"🔓 存储桶策略已设置为公开读取")
        
    except ClientError as e:
        logger.error(f"❌ 创建存储桶失败 (API错误): {e}")
    except EndpointConnectionError as e:
        logger.error(f"❌ 创建存储桶失败 (网络错误): {e}")

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
    except ClientError as e:
        error_code = e.response.get('Error', {}).get('Code', '')
        logger.error(f"❌ [MyCloud] S3 API 错误 ({error_code}): {e}")
        return {
            "success": False,
            "service": "MyCloud",
            "error": f"S3 API 错误: {error_code}"
        }
    except EndpointConnectionError as e:
        logger.error(f"❌ [MyCloud] 网络连接失败: {e}")
        return {
            "success": False,
            "service": "MyCloud",
            "error": "存储服务连接失败"
        }
    except RuntimeError as e:
        logger.error(f"❌ [MyCloud] 初始化错误: {e}")
        return {
            "success": False,
            "service": "MyCloud",
            "error": str(e)
        }
    except Exception as e:
        logger.error(f"❌ [MyCloud] 未知错误: {e}")
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
    except ClientError as e:
        error_code = e.response.get('Error', {}).get('Code', '')
        if error_code == 'NoSuchKey':
            logger.warning(f"❌ 对象不存在: {object_name}")
        else:
            logger.warning(f"❌ 读取对象失败 (S3 错误 {error_code}): {e}")
        raise
    except EndpointConnectionError as e:
        logger.error(f"❌ 读取对象失败 (网络错误): {e}")
        raise
    except Exception as e:
        logger.warning(f"❌ 读取 MyCloud 对象失败: {e}")
        raise


def delete_from_minio(object_name: str) -> bool:
    """
    从 MinIO 删除对象
    
    Args:
        object_name: 对象键名 (Key)
        
    Returns:
        bool: 删除是否成功
    """
    s3 = get_s3_client()
    if not s3:
        logger.error("❌ [MyCloud] MinIO 客户端未初始化")
        return False

    try:
        s3.delete_object(Bucket=MINIO_BUCKET_NAME, Key=object_name)
        return True
    except ClientError as e:
        error_code = e.response.get('Error', {}).get('Code', '')
        logger.error(f"❌ [MyCloud] 删除失败 (S3 错误 {error_code}): {e}")
        return False
    except EndpointConnectionError as e:
        logger.error(f"❌ [MyCloud] 删除失败 (网络错误): {e}")
        return False
    except Exception as e:
        logger.error(f"❌ [MyCloud] 删除失败 (未知错误): {e}")
        return False
