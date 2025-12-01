# 使用官方轻量级 Python 镜像
FROM python:3.10-slim

# 设置工作目录
WORKDIR /app

# ----------------- 🚀 关键优化点 🚀 -----------------
# 1. 先只复制 requirements.txt 这一个文件过去
COPY requirements.txt .

# 2. 立刻安装依赖
# 只要 requirements.txt 的内容没变，
# 下次部署时，Docker 就会直接跳过这一步（使用缓存），速度几乎是 0 秒！
RUN pip install --no-cache-dir -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
# ----------------------------------------------------

# 3. 依赖装完后，再复制剩下的所有代码
# 这样即使你改了 main.py，Docker 也只会重新跑这一步，极快！
COPY . .

# 暴露端口
EXPOSE 8000

# 健康检查 (保留你之前的配置)
HEALTHCHECK --interval=5s --timeout=3s \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/')" || exit 1

# 启动命令
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
