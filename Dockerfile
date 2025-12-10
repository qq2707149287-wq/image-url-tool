# 使用官方轻量级 Python 镜像
FROM python:3.10-slim

# 设置工作目录
WORKDIR /app

# 1. 安装 curl (用于健康检查)
# 这一步必须在 COPY 之前，利用 Docker 缓存
RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*

# 2. 先只复制 requirements.txt
COPY requirements.txt .

# 3. 安装依赖 (使用清华源加速)
RUN pip install --no-cache-dir -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

# 4. 复制剩余代码
COPY . .

# 暴露端口
EXPOSE 8000

# 5. 优化后的健康检查
# - start-period: 给它 10秒 启动时间，不要一上来就报错
# - interval: 每 30秒 查一次，减轻压力
# - CMD: 使用 curl -f 检查 /health 接口
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
  CMD curl -f http://localhost:8000/health || exit 1

# 启动命令
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
