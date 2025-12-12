# 使用官方轻量级 Python 镜像
FROM python:3.10-slim

# 设置工作目录
WORKDIR /app

# 1. 更换为清华源并安装 curl
# (python:3.10-slim 基于 Debian，默认源在国内很慢，换成清华源加速)
RUN sed -i 's/deb.debian.org/mirrors.tuna.tsinghua.edu.cn/g' /etc/apt/sources.list.d/debian.sources 2>/dev/null || sed -i 's/deb.debian.org/mirrors.tuna.tsinghua.edu.cn/g' /etc/apt/sources.list && \
  apt-get update && apt-get install -y curl libgl1 libglib2.0-0 && rm -rf /var/lib/apt/lists/*

# 2. [优化] 优先单独安装 PyTorch CPU 版 (利用 Docker 层缓存)
# 这一步非常重要！避免每次修改代码都重新下载 2GB 的 PyTorch
# 添加 --extra-index-url 以便能从清华源下载 torch 的依赖库 (如 typing-extensions)
RUN pip install --no-cache-dir "torch==2.9.1" --index-url https://download.pytorch.org/whl/cpu --extra-index-url https://pypi.tuna.tsinghua.edu.cn/simple

# 2.5. [优化] 分步安装大体积依赖 (降低构建时的内存峰值)
# 先安装 Transformers
RUN pip install --no-cache-dir "transformers==4.57.3" -i https://pypi.tuna.tsinghua.edu.cn/simple

# 再安装 NudeNet
RUN pip install --no-cache-dir "nudenet==3.4.2" -i https://pypi.tuna.tsinghua.edu.cn/simple

# 3. 复制 requirements.txt
COPY requirements.txt .

# 4. 安装剩余依赖 (使用清华源加速)
# 注意: torch 已经在上一步安装，这里会显示 "checking..." 然后跳过
RUN pip install --no-cache-dir -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

# 4. 复制剩余代码
COPY . .

# 5. 持久化配置
ENV DATA_DIR=/app/data
# [优化] 将 HOME 设置为 /app/data，这样 ~/.cache (HuggingFace) 和 ~/.NudeNet 都会存到持久化目录
ENV HOME=/app/data
ENV HF_HOME=/app/data/.cache/huggingface
ENV TORCH_HOME=/app/data/.cache/torch

# 声明 /app/data 为挂载点，提示 Docker/Coolify 这里需要持久化
VOLUME ["/app/data"]

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
