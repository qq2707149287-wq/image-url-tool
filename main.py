import socket
from fastapi import FastAPI, File, UploadFile, Form
from fastapi.responses import JSONResponse, FileResponse
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
    print("   3. 选择图床服务并获取链接")
    print("")
    print("⚠️  按 Ctrl+C 可停止服务器")
    print("="*60 + "\n")
    
    yield
    
    print("\n👋 服务器已停止\n")

app = FastAPI(title="图片URL获取工具", lifespan=lifespan)

# === 3. 配置区域 ===
MINIO_ENDPOINT = "http://s3.demo.test52dzhp.com"
MINIO_ACCESS_KEY = "kuByCmeTH1TbzbnW"
MINIO_SECRET_KEY = "TKhMmKHT0ZbbBlezfMfvaQyhTDEvQGv3"
MINIO_BUCKET_NAME = "images"

# === 4. 工具函数 ===
def calculate_md5(content):
    return hashlib.md5(content).hexdigest()

def get_image_info(content):
    try:
        img = Image.open(BytesIO(content))
        return {"width": img.width, "height": img.height, "size": len(content)}
    except:
        return {"width": 0, "height": 0, "size": len(content)}

# === 5. 唯一的上传函数：MyCloud ===
def upload_to_minio(data, name, fhash):
    print(f"   [MyCloud] 正在上传 {name[:40]}...")
    try:
        s3 = boto3.client(
            's3', 
            endpoint_url=MINIO_ENDPOINT,
            aws_access_key_id=MINIO_ACCESS_KEY,
            aws_secret_access_key=MINIO_SECRET_KEY,
            config=Config(signature_version='s3v4')
        )
        ext = os.path.splitext(name)[1] or ".jpg"
        key = f"{fhash}{ext}"
        
        ctype = "application/octet-stream"
        if ext.lower() in [".jpg", ".jpeg"]: 
            ctype = "image/jpeg"
        elif ext.lower() == ".png": 
            ctype = "image/png"
        elif ext.lower() == ".gif": 
            ctype = "image/gif"
        elif ext.lower() == ".webp": 
            ctype = "image/webp"

        s3.put_object(
            Bucket=MINIO_BUCKET_NAME, 
            Key=key, 
            Body=data, 
            ContentType=ctype
        )
        url = f"{MINIO_ENDPOINT}/{MINIO_BUCKET_NAME}/{key}"
        print("   ✅ [MyCloud] 成功")
        return {
            "success": True, 
            "service": "MyCloud", 
            "url": url
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

        # 只走 MyCloud
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
            content={
                "success": False, 
                "error": str(e)
            }
        )

@app.post("/validate")
async def val(d: dict): 
    return {"success": True}

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
