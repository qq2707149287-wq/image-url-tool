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
import mimetypes # 引入这个库来准确判断文件类型

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
    print(f"✅ 服务器启动成功！")
    print(f"📍 访问地址: http://{local_ip}:{port}")
    print("="*60 + "\n")
    
    yield
    
    print("\n👋 服务器已停止\n")

app = FastAPI(title="图片URL获取工具", lifespan=lifespan)

# === 3. MinIO 配置 ===
MINIO_ENDPOINT = "http://s3.demo.test52dzhp.com"
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
        return {"width": 0, "height": 0, "size": len(content)}

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
    print(f"   [MyCloud] 正在上传 {name[:40]}...")
    try:
        s3 = create_minio_client()
        ext = os.path.splitext(name)[1] or ".jpg"
        key = f"{fhash}{ext}"
        
        # 尽可能准确地设置类型，防止浏览器误判
        content_type, _ = mimetypes.guess_type(name)
        if not content_type:
            content_type = "application/octet-stream"

        s3.put_object(
            Bucket=MINIO_BUCKET_NAME,
            Key=key,
            Body=data,
            ContentType=content_type
        )

        # 返回相对路径
        url = f"/mycloud/{key}"

        print("   ✅ [MyCloud] 成功")
        return {
            "success": True,
            "service": "MyCloud",
            "url": url,
            "key": key
        }
    except Exception as e:
        print(f"   ❌ [MyCloud] 错误: {e}")
        return {
            "success": False,
            "service": "MyCloud",
            "error": str(e)
        }

# === 6. 上传接口 ===
@app.post("/upload")
async def upload_endpoint(
    file: UploadFile = File(...),
    services: str = Form("myminio")
):
    try:
        content = await file.read()
        fhash = calculate_md5(content)
        info = get_image_info(content)

        res = upload_to_minio(content, file.filename, fhash)

        if not res["success"]:
            return JSONResponse({
                "success": False,
                "error": res.get("error"),
                "failed_list": [{"service": "MyCloud", "error": res.get("error")}]
            })
        
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
        return JSONResponse(status_code=500, content={"success": False, "error": str(e)})

# === 7. 图片代理接口 (修改重点) ===
@app.get("/mycloud/{object_name:path}")
def get_mycloud_image(object_name: str):
    try:
        s3 = create_minio_client()
        
        # 1. 获取文件流
        obj = s3.get_object(Bucket=MINIO_BUCKET_NAME, Key=object_name)
        body = obj["Body"]
        
        # 2. 强制判断文件类型
        # 优先根据文件名后缀判断类型 (例如 .jpg -> image/jpeg)
        # 这样即使 MinIO 里存的是乱七八糟的类型，我们也能纠正过来
        content_type, _ = mimetypes.guess_type(object_name)
        
        # 如果实在判断不出来，才用 MinIO 返回的，或者默认值
        if not content_type:
            content_type = obj.get("ContentType", "application/octet-stream")

        # 3. 关键头信息：告诉浏览器 "Inline" (在页面内显示)
        headers = {
            "Content-Disposition": "inline",  # <--- 就是这句话禁止了自动下载
            "Cache-Control": "public, max-age=315360000" # 让浏览器多缓存一会，加载更快
        }

        return StreamingResponse(body, media_type=content_type, headers=headers)

    except Exception as e:
        print(f"   ❌ 读取失败: {e}")
        raise HTTPException(status_code=404, detail="Image not found")

# === 8. 其他接口 ===
@app.post("/validate")
async def val(d: dict):
    return {"success": True, "url": d.get("url")}

# 挂载前端
app.mount("/static", StaticFiles(directory="frontend"), name="static")

@app.get("/")
def idx():
    return FileResponse(os.path.join("frontend", "index.html"))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="warning", access_log=False)
