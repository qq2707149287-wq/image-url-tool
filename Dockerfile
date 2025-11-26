# 使用官方轻量级 Python 镜像
FROM python:3.10-slim

# 设置工作目录
WORKDIR /app

# 安装必要的依赖 (不再安装 libgl1 等，避免网络错误)
COPY requirements.txt .
# 使用清华源加速安装
RUN pip install --no-cache-dir -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

# 复制所有项目代码
COPY . .

# 暴露端口 8000
EXPOSE 8000

# 🔴 关键魔法代码：直接在镜像里告诉 Docker 怎么检查健康
# 只要这一行生效，Coolify 面板怎么配都不重要了
HEALTHCHECK --interval=5s --timeout=3s \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/')" || exit 1

# 启动命令
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
