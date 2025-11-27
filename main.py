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
import mimetypes  # 核心修复库

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
        
        # [优化] 上传时尽量猜对类型，但这一步不是决定性的
        content_type, _ = mimetypes.guess_type(name)
        if not content_type:
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
            # 保留 failed_list 结构，防止前端解析报错
            return JSONResponse({
                "success": False,
                "error": res.get("error", "上传失败"),
                "failed_list": [{"service": "MyCloud", "error": res.get("error")}]
            })
        
        print("✨ 任务完成")
        # 保留完整的 JSON 结构
        return JSONResponse({
            "success": True,
            "filename": file.filename,
            "hash": fhash,
            "url": res["url"],
            "service": res["service"],
            "all_results": [res], # 保留 all_results，前端历史记录依赖它
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

# === 7. 图片代理接口 (这是本次唯一修改核心逻辑的地方) ===
@app.get("/mycloud/{object_name:path}")
def get_mycloud_image(object_name: str):
    """
    代理 MinIO 图片请求，解决证书错误和自动下载问题
    """
    try:
        s3 = create_minio_client()
        obj = s3.get_object(Bucket=MINIO_BUCKET_NAME, Key=object_name)
        body = obj["Body"]
        
        # --- 核心修复开始 ---
        # 1. 强制猜测类型，不管 MinIO 里存的是乱码还是 application/octet-stream
        content_type, _ = mimetypes.guess_type(object_name)
        
        # 2. 如果没猜出来（比如没后缀），尝试用 MinIO 的数据，或者默认给 jpeg
        if not content_type:
            content_type = obj.get("ContentType", "image/jpeg")
            
        # 3. 强制设置响应头，禁止下载，强制预览
        headers = {
            "Content-Disposition": "inline",  # 只要把这个设为 inline，浏览器就会尝试渲染
            "Content-Type": content_type,     # 明确告诉浏览器这是图片
            "Cache-Control": "public, max-age=31536000" # 加上缓存，让加载更快
        }
        # --- 核心修复结束 ---

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
