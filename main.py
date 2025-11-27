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

# === 1. 获取本机IP地址 ===
def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except:
        return "127.0.0.1"

# === 2. 生命周期事件处理器 ===
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
    print("   3. 选择图床服务并获取链接（当前仅 MyCloud）")
    print("")
    print("⚠️  按 Ctrl+C 可停止服务器")
    print("="*60 + "\n")
    
    yield
    
    print("\n👋 服务器已停止\n")

app = FastAPI(title="图片URL获取工具", lifespan=lifespan)

# === 3. MinIO 配置（这里是后端内部访问地址，跟前端无关） ===
MINIO_ENDPOINT = "http://s3.demo.test52dzhp.com"   # 这还是给 boto3 用的
MINIO_ACCESS_KEY = "kuByCmeTH1TbzbnW"
MINIO_SECRET_KEY = "TKhMmKHT0ZbbBlezfMfvaQyhTDEvQGv3"
MINIO_BUCKET_NAME = "images"

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
    """
    封装一下，后面上传和读取都用它，方便以后要改配置
    """
    return boto3.client(
        "s3",
        endpoint_url=MINIO_ENDPOINT,
        aws_access_key_id=MINIO_ACCESS_KEY,
        aws_secret_access_key=MINIO_SECRET_KEY,
        config=Config(signature_version="s3v4")
    )

# === 5. 唯一的上传函数：MyCloud (MinIO) ===
def upload_to_minio(data: bytes, name: str, fhash: str):
    print(f"   [MyCloud] 正在上传 {name[:40]}...")
    try:
        s3 = create_minio_client()
        ext = os.path.splitext(name)[1] or ".jpg"
        key = f"{fhash}{ext}"
        
        ctype = "application/octet-stream"
        lower_ext = ext.lower()
        if lower_ext in [".jpg", ".jpeg"]:
            ctype = "image/jpeg"
        elif lower_ext == ".png":
            ctype = "image/png"
        elif lower_ext == ".gif":
            ctype = "image/gif"
        elif lower_ext == ".webp":
            ctype = "image/webp"
        elif lower_ext == ".bmp":
            ctype = "image/bmp"

        s3.put_object(
            Bucket=MINIO_BUCKET_NAME,
            Key=key,
            Body=data,
            ContentType=ctype
        )

        # 关键改动：不再返回 MinIO 域名，而是当前站点下的相对路径
        url = f"/mycloud/{key}"

        print("   ✅ [MyCloud] 成功")
        return {
            "success": True,
            "service": "MyCloud",
            "url": url,
            "key": key,
            "content_type": ctype
        }
    except Exception as e:
        print(f"   ❌ [MyCloud] 错误: {e}")
        return {
            "success": False,
            "service": "MyCloud",
            "error": str(e)
        }

SERVICE_MAP = {
    "myminio": upload_to_minio
}

# === 6. 上传接口 ===
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

        # 目前只支持 myminio，其它忽略
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
            "url": res["url"],           # 形如 /mycloud/xxxx.jpg
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

# === 7. 图片代理接口：让前端只访问 /mycloud/...，不直接碰 MinIO 域名 ===
@app.get("/mycloud/{object_name:path}")
def get_mycloud_image(object_name: str):
    """
    通过当前服务把 MinIO 里的图片读出来返回给浏览器：
    - 浏览器看到的是当前站点的证书，不会再报 ERR_CERT_AUTHORITY_INVALID
    - Content-Type 取自 MinIO 里保存的类型，浏览器会直接预览图片
    """
    try:
        s3 = create_minio_client()
        obj = s3.get_object(Bucket=MINIO_BUCKET_NAME, Key=object_name)
        body = obj["Body"]
        content_type = obj.get("ContentType", "application/octet-stream")
        return StreamingResponse(body, media_type=content_type)
    except Exception as e:
        print(f"   ❌ 读取 MyCloud 对象失败: {e}")
        raise HTTPException(status_code=404, detail="Image not found")

# === 8. 简单验证接口（现在前端只是用来走流程） ===
@app.post("/validate")
async def val(d: dict):
    url = d.get("url")
    print(f"验证 URL 请求: {url}")
    # 目前简单返回成功，如果以后要严格检查可以再改
    return {"success": True, "url": url}

# === 9. 静态文件与首页 ===
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
