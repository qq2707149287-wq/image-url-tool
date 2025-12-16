# 使用官方轻量级 Python 镜像
FROM python:3.10-slim

# 设置工作目录
WORKDIR /app

# ==================== 构建时内存优化 ====================
# 这些环境变量可以显著降低 pip 安装时的内存使用
ENV PIP_NO_CACHE_DIR=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
# 禁用 torch 的 CUDA 内存分配器 (我们只用 CPU)
ENV PYTORCH_NO_CUDA_MEMORY_CACHING=1

# 1. 更换为清华源并安装依赖
RUN sed -i 's/deb.debian.org/mirrors.tuna.tsinghua.edu.cn/g' /etc/apt/sources.list.d/debian.sources 2>/dev/null || sed -i 's/deb.debian.org/mirrors.tuna.tsinghua.edu.cn/g' /etc/apt/sources.list && \
  apt-get update && apt-get install -y --no-install-recommends curl libgl1 libglib2.0-0 && rm -rf /var/lib/apt/lists/*

# 2. [关键优化] 分步安装大型依赖，每步完成后清理，降低内存峰值
# 2.1 安装 PyTorch CPU 版 (最大的包，~800MB)
RUN pip install --no-cache-dir "torch==2.9.1" --index-url https://download.pytorch.org/whl/cpu --extra-index-url https://pypi.tuna.tsinghua.edu.cn/simple && \
  rm -rf /root/.cache /tmp/*

# 2.2 安装 Transformers
RUN pip install --no-cache-dir "transformers==4.57.3" -i https://pypi.tuna.tsinghua.edu.cn/simple && \
  rm -rf /root/.cache /tmp/*

# 2.3 安装 NudeNet
RUN pip install --no-cache-dir "nudenet==3.4.2" -i https://pypi.tuna.tsinghua.edu.cn/simple && \
  rm -rf /root/.cache /tmp/*

# 3. 复制 requirements.txt 并安装剩余小依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple && \
  rm -rf /root/.cache /tmp/*

# 4. 复制代码
COPY . .

# 5. 运行时配置
ENV DATA_DIR=/app/data
ENV HOME=/app/data
ENV HF_HOME=/app/data/.cache/huggingface
ENV TORCH_HOME=/app/data/.cache/torch

# 声明持久化目录
VOLUME ["/app/data"]

# 暴露端口
EXPOSE 8000

# 6. 健康检查 (宽松配置，适合低配服务器)
# - start-period: 180秒，给 AI 模型充足加载时间
# - interval: 60秒，减少检查频率
HEALTHCHECK --interval=60s --timeout=15s --start-period=180s --retries=5 \
  CMD curl -f http://localhost:8000/health || exit 1

# ⚠️ 部署提示:
# - 最低内存: 2GB RAM
# - 推荐: Coolify 中设置 Memory Limit >= 2048MB
# - 如构建仍失败，可尝试在服务器添加 swap: sudo fallocate -l 2G /swapfile && sudo mkswap /swapfile && sudo swapon /swapfile

# 启动命令 (单 worker，节省内存)
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
