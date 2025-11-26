# 使用官方轻量级 Python 镜像
FROM python:3.10-slim

# 设置工作目录
WORKDIR /app

# 1. 安装系统依赖 (Pillow 处理图片需要 libgl1)
# 这一步非常重要，否则上传图片时会报错 "ImportError: libGL.so.1"
RUN apt-get update && apt-get install -y \
    libgl1-mesa-glx \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# 2. 复制依赖文件并安装
COPY requirements.txt .
# 使用清华源加速安装（如果你的服务器在国内），如果在国外可去掉 -i 参数
RUN pip install --no-cache-dir -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

# 3. 复制所有项目代码
COPY . .

# 4. 暴露端口
EXPOSE 8000

# 5. 启动命令
# 使用 0.0.0.0 让外部可以访问
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
