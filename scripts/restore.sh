#!/bin/bash
# ==============================================================================
# 🐾 图床数据恢复脚本
# 功能：从备份恢复数据库 + MinIO 图片
# 用法：chmod +x restore.sh && ./restore.sh /path/to/backup/folder
# ==============================================================================

set -e

# 检查参数
if [ -z "$1" ]; then
    echo "❌ 用法: ./restore.sh /path/to/backup/folder"
    echo "   例如: ./restore.sh /root/imagehost-backups/20251223_030000"
    exit 1
fi

BACKUP_PATH="$1"

# 验证备份目录
if [ ! -d "${BACKUP_PATH}" ]; then
    echo "❌ 错误: 备份目录不存在: ${BACKUP_PATH}"
    exit 1
fi

if [ ! -f "${BACKUP_PATH}/history.db" ]; then
    echo "❌ 错误: 备份目录中没有找到 history.db"
    exit 1
fi

echo "🐾 =========================================="
echo "🐾 图床数据恢复开始"
echo "🐾 从备份: ${BACKUP_PATH}"
echo "🐾 =========================================="

# -------------------- 配置区域 --------------------
CONTAINER_KEYWORD="e0w48c0swgscwooo404wowc8"
MINIO_ENDPOINT="http://s3.demo.test52dzhp.com"
MINIO_ACCESS_KEY="VkXXzUYMVduEG9K0"
MINIO_SECRET_KEY="qn4QL0WwxFLDeWZMuQPrdTh4rawGTUAu"
MINIO_BUCKET="images"

# -------------------- 第一步：恢复数据库 --------------------
echo ""
echo "📦 [1/2] 正在恢复数据库..."

CONTAINER_ID=$(docker ps --filter "name=${CONTAINER_KEYWORD}" --format "{{.ID}}" | head -n 1)

if [ -z "${CONTAINER_ID}" ]; then
    echo "❌ 错误：找不到图床容器！请先确保应用已部署并运行。"
    exit 1
fi

# 停止应用写入 (可选，跳过以避免服务中断)
# docker exec "${CONTAINER_ID}" pkill -STOP uvicorn || true

# 复制数据库到容器
docker cp "${BACKUP_PATH}/history.db" "${CONTAINER_ID}:/app/data/history.db"

# 恢复写入
# docker exec "${CONTAINER_ID}" pkill -CONT uvicorn || true

echo "✅ 数据库恢复成功！"

# -------------------- 第二步：恢复 MinIO 图片 --------------------
echo ""
echo "📷 [2/2] 正在恢复 MinIO 图片..."

if [ -d "${BACKUP_PATH}/images" ]; then
    # 配置 MinIO 连接
    mc alias set restore_minio "${MINIO_ENDPOINT}" "${MINIO_ACCESS_KEY}" "${MINIO_SECRET_KEY}" --api S3v4 > /dev/null 2>&1

    # 同步图片到 MinIO
    mc mirror "${BACKUP_PATH}/images/" restore_minio/"${MINIO_BUCKET}" --overwrite --quiet

    echo "✅ 图片恢复成功！"
else
    echo "⚠️ 备份中没有 images 目录，跳过图片恢复。"
fi

# -------------------- 完成 --------------------
echo ""
echo "🎉 =========================================="
echo "🎉 恢复完成！"
echo "🎉 =========================================="
echo ""
echo "💡 提示: 建议重启容器使数据库更改完全生效:"
echo "   docker restart ${CONTAINER_ID}"
echo ""
