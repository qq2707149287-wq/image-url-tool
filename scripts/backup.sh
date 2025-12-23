#!/bin/bash
# ==============================================================================
# 🐾 图床数据备份脚本
# 功能：自动备份数据库 + MinIO 图片到本地目录
# 用法：chmod +x backup.sh && ./backup.sh
# ==============================================================================

# ==================== 配置区域 (请根据实际情况修改) ====================

# 备份保存目录 (会自动创建)
BACKUP_DIR="/root/imagehost-backups"

# 图床容器名称关键词 (Coolify 会自动生成带 UUID 的容器名)
CONTAINER_KEYWORD="e0w48c0swgscwooo404wowc8"

# MinIO 配置 (与 Coolify 环境变量保持一致)
MINIO_ENDPOINT="http://s3.demo.test52dzhp.com"
MINIO_ACCESS_KEY="VlXXZuYMVduEG9K0"
MINIO_SECRET_KEY="qn4QL0WwxFLDeWZMuQPrdTh4rawGTUAu"
MINIO_BUCKET="images"

# 保留最近多少天的备份 (自动清理旧备份)
KEEP_DAYS=7

# ==============================================================================

set -e

# 生成时间戳
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
TODAY_DIR="${BACKUP_DIR}/${TIMESTAMP}"

echo "🐾 =========================================="
echo "🐾 图床数据备份开始"
echo "🐾 时间: $(date)"
echo "🐾 备份目录: ${TODAY_DIR}"
echo "🐾 =========================================="

# 创建备份目录
mkdir -p "${TODAY_DIR}"

# -------------------- 第一步：备份数据库 --------------------
echo ""
echo "📦 [1/3] 正在备份数据库..."

# 找到正在运行的图床容器
CONTAINER_ID=$(docker ps --filter "name=${CONTAINER_KEYWORD}" --format "{{.ID}}" | head -n 1)

if [ -z "${CONTAINER_ID}" ]; then
    echo "❌ 错误：找不到图床容器！请检查容器是否在运行。"
    exit 1
fi

echo "   找到容器: ${CONTAINER_ID}"

# 从容器中复制数据库
docker cp "${CONTAINER_ID}:/app/data/database.db" "${TODAY_DIR}/database.db"

if [ -f "${TODAY_DIR}/database.db" ]; then
    DB_SIZE=$(du -h "${TODAY_DIR}/database.db" | cut -f1)
    echo "✅ 数据库备份成功！大小: ${DB_SIZE}"
else
    echo "❌ 数据库备份失败！"
    exit 1
fi

# -------------------- 第二步：备份 MinIO 图片 --------------------
echo ""
echo "📷 [2/3] 正在备份 MinIO 图片..."

# 检查 mc 客户端是否存在
if ! command -v mc &> /dev/null; then
    echo "   正在安装 MinIO 客户端..."
    wget -q https://dl.min.io/client/mc/release/linux-amd64/mc -O /usr/local/bin/mc
    chmod +x /usr/local/bin/mc
fi

# 配置 MinIO 连接
mc alias set backup_minio "${MINIO_ENDPOINT}" "${MINIO_ACCESS_KEY}" "${MINIO_SECRET_KEY}" --api S3v4 > /dev/null 2>&1

# 同步图片到本地
mkdir -p "${TODAY_DIR}/images"
mc mirror backup_minio/"${MINIO_BUCKET}" "${TODAY_DIR}/images/" --quiet

IMAGE_COUNT=$(find "${TODAY_DIR}/images" -type f | wc -l)
IMAGES_SIZE=$(du -sh "${TODAY_DIR}/images" | cut -f1)
echo "✅ 图片备份成功！共 ${IMAGE_COUNT} 个文件，总大小: ${IMAGES_SIZE}"

# -------------------- 第三步：清理旧备份 --------------------
echo ""
echo "🧹 [3/3] 清理 ${KEEP_DAYS} 天前的旧备份..."

OLD_BACKUPS=$(find "${BACKUP_DIR}" -maxdepth 1 -type d -mtime +${KEEP_DAYS} | grep -v "^${BACKUP_DIR}$" || true)

if [ -n "${OLD_BACKUPS}" ]; then
    echo "${OLD_BACKUPS}" | while read dir; do
        echo "   删除: ${dir}"
        rm -rf "${dir}"
    done
    echo "✅ 旧备份清理完成！"
else
    echo "   没有需要清理的旧备份。"
fi

# -------------------- 完成 --------------------
echo ""
echo "🎉 =========================================="
echo "🎉 备份完成！"
echo "🎉 备份位置: ${TODAY_DIR}"
echo "🎉 =========================================="
echo ""
echo "📋 备份内容:"
ls -lh "${TODAY_DIR}"
echo ""
