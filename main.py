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

# === 0. 核心修复：手动教 Python 认识 AVIF ===
# 因为很多 Linux 容器默认不认识这个新格式，必须手动注册
mimetypes.add_type("image/avif", ".avif")
mimetypes.add_type("image/heic", ".heic")
mimetypes.add_type("image/webp", ".webp")

# === 1. 获取本机IP地址 (保留原功能) ===
def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except:
        return "127.0.0.1"

# === 2. 生命周期事件处理器 (保留原有的详细提示) ===
@asynccontextmanager
async def lifespan(app: FastAPI):
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

# === 3. MinIO 配置 ===
MINIO_ENDPOINT = "http://s3.demo.test52dzhp.com"
MINIO_ACCESS_KEY = "kuByCmeTH1TbzbnW"
MINIO_SECRET_KEY = "TKhMmKHT0ZbbBlezfMfvaQyhTDEvQGv3"
MINIO_BUCKET_NAME = "images"

# === 4. 工具函数 (保留) ===
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

# === 5. 上传逻辑 (保留详细日志) ===
def upload_to_minio(data: bytes, name: str, fhash: str):
    print(f"   [MyCloud] 正在上传 {name[:40]}...")
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

        print("   ✅ [MyCloud] 成功")
        return {
            "success": True,
            "service": "MyCloud",
            "url": url,
            "key": key,
            "content_type": content_type
        }
    except Exception as e:
        print(f"   ❌ [MyCloud] 错误: {e}")
        return {
            "success": False,
            "service": "MyCloud",
            "error": str(e)
        }

# === 6. 上传接口 (保留完整的返回结构) ===
@app.post("/upload")
async def upload_endpoint(
    file: UploadFile = File(...),
    services: str = Form("myminio")
):
    print(f"\n📥 收到上传任务: {file.filename}")
    try:
        content = await file.read()
        fhash = calculate_md5(content)
        info = get_image_info(content)

        # 核心上传
        res = upload_to_minio(content, file.filename, fhash)

        if not res["success"]:
            print("❌ 上传失败")
            return JSONResponse({
                "success": False,
                "error": res.get("error", "上传失败"),
                "failed_list": [{"service": "MyCloud", "error": res.get("error")}]
            })
        
        print("✨ 任务完成")
        return JSONResponse({
            "success": True,
            "filename": file.filename,
            "hash": fhash,
            "url": res["url"],
            "service": res["service"],
            "all_results": [res], 
            "failed_list": [],
            "width": info["width"],
            "height": info["height"],
            "size": info["size"]
        })

    except Exception as e:
        traceback.print_exc()
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e)}
        )

# === 7. 图片代理接口 (针对 AVIF 做了增强) ===
@app.get("/mycloud/{object_name:path}")
def get_mycloud_image(object_name: str):
    """
    代理 MinIO 图片请求，解决证书错误和自动下载问题
    """
    try:
        s3 = create_minio_client()
        obj = s3.get_object(Bucket=MINIO_BUCKET_NAME, Key=object_name)
        body = obj["Body"]
        
        # 1. 尝试猜测类型 (因为开头手动 add_type 了，现在应该能认出 avif)
        content_type, _ = mimetypes.guess_type(object_name)
        
        # 2. 双重保险：如果系统还是笨笨的，我们人工指定
        if not content_type:
            lower_name = object_name.lower()
            if lower_name.endswith(".avif"):
                content_type = "image/avif"
            elif lower_name.endswith(".webp"):
                content_type = "image/webp"
            else:
                content_type = obj.get("ContentType", "image/jpeg")
            
        # 3. 强制设置响应头，禁止下载，强制预览
        headers = {
            "Content-Disposition": "inline",
            "Content-Type": content_type,
            "Cache-Control": "public, max-age=31536000"
        }

        return StreamingResponse(body, media_type=content_type, headers=headers)
    except Exception as e:
        print(f"   ❌ 读取 MyCloud 对象失败: {e}")
        raise HTTPException(status_code=404, detail="Image not found")

# === 8. 验证接口 (保留) ===
@app.post("/validate")
async def val(d: dict):
    url = d.get("url")
    print(f"验证 URL 请求: {url}")
    return {"success": True, "url": url}

# === 9. 静态文件与首页 (保留) ===
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
        log_level="warning",
        access_log=False
    )
