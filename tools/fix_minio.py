import boto3
import json
from botocore.client import Config

# --- MinIO 配置 (已根据你的截图填好) ---
MINIO_ENDPOINT = "http://s3.demo.test52dzhp.com"
MINIO_ACCESS_KEY = "kuByCmeTH1TbzbnW"
MINIO_SECRET_KEY = "TKhMmKHT0ZbbBlezfMfvaQyhTDEvQGv3"
MINIO_BUCKET_NAME = "images"

# --- 连接 MinIO ---
s3 = boto3.client('s3',
                  endpoint_url=MINIO_ENDPOINT,
                  aws_access_key_id=MINIO_ACCESS_KEY,
                  aws_secret_access_key=MINIO_SECRET_KEY,
                  config=Config(signature_version='s3v4'))

# --- 定义公开访问策略 ---
public_policy = {
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Principal": {"AWS": "*"},
            "Action": ["s3:GetObject"],
            "Resource": [f"arn:aws:s3:::{MINIO_BUCKET_NAME}/*"]
        }
    ]
}

try:
    # 1. 应用策略
    policy_json = json.dumps(public_policy)
    s3.put_bucket_policy(Bucket=MINIO_BUCKET_NAME, Policy=policy_json)
    print("✅ 成功！Bucket 'images' 已设置为公开访问 (Public)。")
    
    # 2. 验证一下
    print("正在验证权限...")
    try:
        policy = s3.get_bucket_policy(Bucket=MINIO_BUCKET_NAME)
        print("验证通过：策略已生效。")
    except Exception as e:
        print(f"验证警告：{e}")

except Exception as e:
    print(f"❌ 失败：{str(e)}")
    print("提示：请检查 Endpoint 地址是否能连通，或者账号密码是否正确。")
