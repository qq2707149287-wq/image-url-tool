# 使用官方轻量级 Python 镜像
FROM python:3.10-slim

# 设置工作目录
WORKDIR /app

# --- 修改重点：此处删除了 apt-get 相关的命令 ---
# 绝大多数情况下 Pillow 不需要它们也能运行，删掉可以避免构建失败

# 1. 复制依赖文件并安装
COPY requirements.txt .

# 2. 安装 Python 依赖
# 依然保留清华源，防止 pip 安装也超时
RUN pip install --no-cache-dir -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

# 3. 复制所有项目代码
COPY . .

# 4. 暴露端口
EXPOSE 8000

# 5. 启动命令
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
