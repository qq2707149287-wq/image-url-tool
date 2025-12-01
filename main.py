import socket
from fastapi import FastAPI, File, UploadFile, Form, HTTPException
from fastapi.responses import JSONResponse, FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
from PIL import Image
from io import BytesIO
import os
import hashlib
import boto3
from botocore.client import Config
import traceback
import mimetypes 
import sqlite3
from typing import List
from pydantic import BaseModel
import logging
from dotenv import load_dotenv

# === 0. 配置与初始化 ===
# 加载环境变量
load_dotenv()

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 手动教 Python 认识 AVIF
mimetypes.add_type("image/avif", ".avif")
mimetypes.add_type("image/heic", ".heic")
mimetypes.add_type("image/webp", ".webp")

# 数据库配置
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "history.db")

# MinIO 配置 (从环境变量读取)
MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT")
MINIO_ACCESS_KEY = os.getenv("MINIO_ACCESS_KEY")
MINIO_SECRET_KEY = os.getenv("MINIO_SECRET_KEY")
MINIO_BUCKET_NAME = os.getenv("MINIO_BUCKET_NAME", "images")

if not all([MINIO_ENDPOINT, MINIO_ACCESS_KEY, MINIO_SECRET_KEY]):
    logger.warning("⚠️  MinIO 配置缺失！请检查 .env 文件或环境变量。")

def init_db():
    """初始化 SQLite 数据库"""
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS history
                     (id INTEGER PRIMARY KEY AUTOINCREMENT,
                      url TEXT NOT NULL,
                      filename TEXT,
                      hash TEXT,
                      service TEXT,
                      width INTEGER,
                      height INTEGER,
                      size INTEGER,
                      content_type TEXT,
                      created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
        
        # [优化] 添加索引以加速搜索
        c.execute("CREATE INDEX IF NOT EXISTS idx_filename ON history (filename)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_url ON history (url)")
        
        conn.commit()
        conn.close()
        logger.info(f"✅ 数据库已就绪: {DB_PATH}")
    except Exception as e:
        logger.error(f"❌ 数据库初始化失败: {e}")

def save_to_db(data: dict):
    """保存记录到数据库"""
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        # 检查是否已存在 (根据 hash)
        c.execute("SELECT id FROM history WHERE hash = ?", (data.get("hash"),))
        if c.fetchone():
            # 更新现有记录
            c.execute('''UPDATE history SET 
                         url=?, filename=?, service=?, width=?, height=?, size=?, content_type=?, created_at=CURRENT_TIMESTAMP
                         WHERE hash=?''',
                      (data.get("url"), data.get("filename"), data.get("service"),
                       data.get("width"), data.get("height"), data.get("size"), data.get("content_type"),
                       data.get("hash")))
        else:
            # 插入新记录
            c.execute('''INSERT INTO history (url, filename, hash, service, width, height, size, content_type)
                         VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
                      (data.get("url"), data.get("filename"), data.get("hash"), data.get("service"),
                       data.get("width"), data.get("height"), data.get("size"), data.get("content_type")))
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"❌ 保存到数据库失败: {e}")

# === 2. 获取本机IP地址 ===
def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except:
        return "127.0.0.1"

# === 3. 生命周期事件处理器 ===
@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()  # 初始化数据库
    local_ip = get_local_ip()
    port = 8000

    print("\n" + "="*60)
    print(f"✅ 服务器启动成功！ (Host IP: {local_ip})")
    print("="*60)
    print("📍 访问地址:")
    print(f"   • http://localhost:{port}")
    print(f"   • http://{local_ip}:{port}")
    print("")
    print("💡 使用说明:")
    print("   1. 在浏览器中打开上述任一地址")
    print("   2. 上传图片或输入图片URL")
    print("   3. 自动上传至 MyCloud 并生成预览链接")
    print("")
    print("⚠️  按 Ctrl+C 可停止服务器")
    print("="*60 + "\n")
    
    yield
    
    print("\n👋 服务器已停止\n")

app = FastAPI(title="图片URL获取工具", lifespan=lifespan)

# === 4. 工具函数 ===
def calculate_md5(content: bytes) -> str:
    return hashlib.md5(content).hexdigest()

def get_image_info(content: bytes):
    try:
        img = Image.open(BytesIO(content))
        return {"width": img.width, "height": img.height, "size": len(content)}
    except:
        return {"width": 0, "height": len(content), "size": len(content)}

def create_minio_client():
    return boto3.client(
        "s3",
        endpoint_url=MINIO_ENDPOINT,
        aws_access_key_id=MINIO_ACCESS_KEY,
        aws_secret_access_key=MINIO_SECRET_KEY,
        config=Config(signature_version="s3v4")
    )

# === 5. 上传逻辑 ===
def upload_to_minio(data: bytes, name: str, fhash: str):
    logger.info(f"[MyCloud] 正在上传 {name[:40]}...")
    try:
        s3 = create_minio_client()
        ext = os.path.splitext(name)[1] or ".jpg"
        key = f"{fhash}{ext}"
        
        # [优化] 上传时尽量猜对类型
        content_type, _ = mimetypes.guess_type(name)
        if not content_type:
            # 针对 AVIF 的额外补丁
            if name.lower().endswith('.avif'):
                content_type = 'image/avif'
            else:
                content_type = "application/octet-stream"

        s3.put_object(
            Bucket=MINIO_BUCKET_NAME,
            Key=key,
            Body=data,
            ContentType=content_type
        )

        url = f"/mycloud/{key}" # 使用相对路径代理

        logger.info("✅ [MyCloud] 成功")
        return {
            "success": True,
            "service": "MyCloud",
            "url": url,
            "key": key,
            "content_type": content_type
        }
    except Exception as e:
        logger.error(f"❌ [MyCloud] 错误: {e}")
        return {
            "success": False,
            "service": "MyCloud",
            "error": str(e)
        }

# === 6. 上传接口 ===
# [优化] 改为同步函数 (def)，让 FastAPI 在线程池中运行它，避免阻塞主线程
@app.post("/upload")
def upload_endpoint(file: UploadFile = File(...)):
    logger.info(f"📥 收到上传任务: {file.filename}")
    try:
        # 注意: file.read() 在同步函数中也是阻塞的，但这里是在线程池中，所以没问题
        # 如果文件非常大，建议用 spool_max_size 或异步读取后转同步处理
        content = file.file.read() 
        fhash = calculate_md5(content)
        info = get_image_info(content)

        # 核心上传
        res = upload_to_minio(content, file.filename, fhash)

        if not res["success"]:
            logger.error("❌ 上传失败")
            return JSONResponse({
                "success": False,
                "error": res.get("error", "上传失败"),
                "failed_list": [{"service": "MyCloud", "error": res.get("error")}]
            })
        
        logger.info("✨ 任务完成")
        
        # 如果文件名是默认的image.png，使用hash作为文件名
        display_filename = file.filename if file.filename != 'image.png' else fhash
        
        result_data = {
            "success": True,
            "filename": display_filename,
            "hash": fhash,
            "url": res["url"],
            "service": res["service"],
            "all_results": [res], 
            "failed_list": [],
            "width": info["width"],
            "height": info["height"],
            "size": info["size"],
            "content_type": res["content_type"]
        }
        
        # 保存到数据库
        save_to_db(result_data)
        
        return JSONResponse(result_data)

    except Exception as e:
        logger.error(f"上传异常: {e}")
        traceback.print_exc()
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e)}
        )

# === 7. 图片代理接口 ===
# MIME类型映射表
MIME_TYPE_MAP = {
    ".avif": "image/avif",
    ".webp": "image/webp",
    ".heic": "image/heic",
    ".heif": "image/heif",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".gif": "image/gif",
    ".bmp": "image/bmp",
    ".svg": "image/svg+xml",
    ".ico": "image/x-icon",
}

@app.get("/mycloud/{object_name:path}")
def get_mycloud_image(object_name: str):
    """
    代理 MinIO 图片请求
    """
    try:
        s3 = create_minio_client()
        obj = s3.get_object(Bucket=MINIO_BUCKET_NAME, Key=object_name)
        body = obj["Body"]

        # 1. 获取文件扩展名并确定MIME类型
        lower_name = object_name.lower()
        ext = os.path.splitext(lower_name)[1]

        # 2. 优先使用我们的映射表
        content_type = MIME_TYPE_MAP.get(ext)

        # 3. 尝试mimetypes
        if not content_type:
            content_type, _ = mimetypes.guess_type(object_name)

        # 4. 兜底
        if not content_type:
            content_type = obj.get("ContentType", "application/octet-stream")

        headers = {
            "Content-Disposition": "inline",
            "Content-Type": content_type,
            "Cache-Control": "public, max-age=31536000",
            "X-Content-Type-Options": "nosniff",
        }

        return StreamingResponse(body, media_type=content_type, headers=headers)
    except Exception as e:
        logger.warning(f"❌ 读取 MyCloud 对象失败: {e}")
        raise HTTPException(status_code=404, detail="Image not found")

# === 8. 验证接口 ===
@app.post("/validate")
async def val(d: dict):
    url = d.get("url")
    logger.info(f"验证 URL 请求: {url}")
    return {"success": True, "url": url}

# === 9. 历史记录接口 ===
@app.get("/history")
def get_history(page: int = 1, page_size: int = 20, keyword: str = ""):
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        
        offset = (page - 1) * page_size
        query = "SELECT * FROM history"
        params = []
        
        if keyword:
            query += " WHERE filename LIKE ? OR url LIKE ?"
            params.extend([f"%{keyword}%", f"%{keyword}%"])
            
        query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
        params.extend([page_size, offset])
        
        c.execute(query, params)
        rows = c.fetchall()
        
        # 获取总数
        count_query = "SELECT COUNT(*) FROM history"
        count_params = []
        if keyword:
            count_query += " WHERE filename LIKE ? OR url LIKE ?"
            count_params.extend([f"%{keyword}%", f"%{keyword}%"])
            
        c.execute(count_query, count_params)
        total = c.fetchone()[0]
        
        conn.close()
        
        data = [dict(row) for row in rows]
        return {"success": True, "data": data, "total": total, "page": page, "page_size": page_size}
    except Exception as e:
        logger.error(f"获取历史记录失败: {e}")
        return {"success": False, "error": str(e)}

class DeleteRequest(BaseModel):
    ids: List[int]

@app.post("/history/delete")
def delete_history(req: DeleteRequest):
    try:
        if not req.ids:
            return {"success": True, "count": 0}
            
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        placeholders = ','.join('?' * len(req.ids))
        c.execute(f"DELETE FROM history WHERE id IN ({placeholders})", req.ids)
        count = c.rowcount
        conn.commit()
        conn.close()
        return {"success": True, "count": count}
    except Exception as e:
        return {"success": False, "error": str(e)}

@app.post("/history/clear")
def clear_history():
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("DELETE FROM history")
        conn.commit()
        conn.close()
        return {"success": True}
    except Exception as e:
        return {"success": False, "error": str(e)}

# [优化] 改为同步函数
@app.post("/history/rename")
def rename_history(body: dict):
    """重命名历史记录"""
    try:
        url = body.get("url")
        filename = body.get("filename")
        
        if not url or not filename:
            return JSONResponse({"success": False, "error": "缺少必要参数"})
        
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        
        # 尝试直接匹配URL
        c.execute("UPDATE history SET filename = ? WHERE url = ?", (filename, url))
        affected = c.rowcount
        
        # 如果没有匹配到，尝试提取路径部分进行匹配
        if affected == 0 and url.startswith("http"):
            # 从完整URL中提取路径部分 (如 /mycloud/xxx.png)
            from urllib.parse import urlparse
            parsed = urlparse(url)
            path = parsed.path
            c.execute("UPDATE history SET filename = ? WHERE url = ?", (filename, path))
            affected = c.rowcount
        
        conn.commit()
        conn.close()
        
        if affected > 0:
            logger.info(f"✅ 重命名成功: {url} -> {filename}")
            return JSONResponse({"success": True})
        else:
            logger.warning(f"❌ 重命名失败: 未找到匹配的记录 (URL: {url})")
            return JSONResponse({"success": False, "error": "未找到匹配的记录"})
    except Exception as e:
        logger.error(f"❌ 重命名失败: {e}")
        traceback.print_exc()
        return JSONResponse({"success": False, "error": str(e)})

# === 10. 静态文件与首页 ===
app.mount("/static", StaticFiles(directory="frontend"), name="static")

@app.get("/")
def idx():
    return FileResponse(os.path.join("frontend", "index.html"))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_level="info",
        access_log=False
    )
