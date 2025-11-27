import socket
from fastapi import FastAPI, File, UploadFile, Form
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
import requests
from PIL import Image
from io import BytesIO
import os
import hashlib
import boto3
from botocore.client import Config
import traceback
import time

# === 1. 获取本机IP地址 (保留你的逻辑) ===
def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except:
        return "127.0.0.1"

# === 2. 生命周期事件处理器 (完全恢复你的原版文案) ===
@asynccontextmanager
async def lifespan(app: FastAPI):
    """服务器生命周期管理 - 启动和关闭事件"""
    
    # 获取 IP 用于打印
    local_ip = get_local_ip()
    port = 8000

    # 启动时执行 - 这里就是你要求的原封不动的文案
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
    
    yield  # 服务器运行期间
    
    # 关闭时执行
    print("\n👋 服务器已停止\n")

app = FastAPI(title="图片URL获取工具", lifespan=lifespan)

# === 3. 配置区域 ===
IMGBB_API_KEY = "7505d9912bf2caabcaf818aac92e562a"

# MinIO 配置
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

# === 5. 各图床上传函数 ===

def upload_to_imgbb(data, name):
    print(f"   [ImgBB] 正在上传 {name[:15]}...")
    try:
        files = {"image": (name, data)}
        # verify=False 仅用于测试环境解决 SSL 问题
        resp = requests.post(
            "https://api.imgbb.com/1/upload",
            data={"key": IMGBB_API_KEY},
            files=files,
            timeout=45,
            verify=False
        )
        
        if resp.status_code != 200:
            print(f"   ❌ [ImgBB] 失败: HTTP {resp.status_code} - {resp.text[:200]}")
            return {
                "success": False,
                "service": "ImgBB",
                "error": f"HTTP {resp.status_code}"
            }
        
        res = resp.json()
        if res.get("success"):
            print("   ✅ [ImgBB] 成功")
            return {
                "success": True,
                "service": "ImgBB",
                "url": res["data"]["url"]
            }
        else:
            err = res.get("error", {}).get("message", "API Error")
            print(f"   ❌ [ImgBB] API拒绝: {err}")
            return {
                "success": False,
                "service": "ImgBB",
                "error": err
            }
    except Exception as e:
        print(f"   ❌ [ImgBB] 异常: {e}")
        return {
            "success": False,
            "service": "ImgBB",
            "error": "网络错误或超时"
        }

def upload_to_minio(data, name, fhash):
    print(f"   [MyCloud] 正在上传 {name[:15]}...")
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
        
        # 简单的类型判断
        ctype = "application/octet-stream"
        if ext.lower() in [".jpg", ".jpeg"]:
            ctype = "image/jpeg"
        elif ext.lower() == ".png":
            ctype = "image/png"
        elif ext.lower() == ".gif":
            ctype = "image/gif"
        elif ext.lower() == ".webp":
            ctype = "image/webp"

        s3.put_object(Bucket=MINIO_BUCKET_NAME, Key=key, Body=data, ContentType=ctype)
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

def upload_to_catbox(data, name):
    """
    Catbox 官方说明：
      POST https://catbox.moe/user/api.php
      form-data:
        reqtype = "fileupload"
        fileToUpload = (file)
    返回：成功时为纯文本 URL
    """
    print(f"   [Catbox] 正在上传 {name[:15]}...")
    try:
        files = {
            "fileToUpload": (name, data)
        }
        payload = {
            "reqtype": "fileupload"
            # 可以加 userhash 做账号归属，这里留空表示匿名
        }
        resp = requests.post(
            "https://catbox.moe/user/api.php",
            data=payload,
            files=files,
            timeout=60
        )
        if resp.status_code != 200:
            print(f"   ❌ [Catbox] 失败: HTTP {resp.status_code} - {resp.text[:200]}")
            return {
                "success": False,
                "service": "Catbox",
                "error": f"HTTP {resp.status_code}"
            }
        url = resp.text.strip()
        if not (url.startswith("http://") or url.startswith("https://")):
            print(f"   ❌ [Catbox] 返回内容异常: {url[:200]}")
            return {
                "success": False,
                "service": "Catbox",
                "error": "返回内容不是 URL"
            }
        print("   ✅ [Catbox] 成功")
        return {
            "success": True,
            "service": "Catbox",
            "url": url
        }
    except Exception as e:
        print(f"   ❌ [Catbox] 异常: {e}")
        return {
            "success": False,
            "service": "Catbox",
            "error": "网络错误或超时"
        }

# === 6. 服务映射表 ===
SERVICE_MAP = {
    "myminio": upload_to_minio,
    "imgbb": upload_to_imgbb,
    "catbox": upload_to_catbox
}

# === 7. 上传接口 ===
@app.post("/upload")
async def upload_endpoint(
    file: UploadFile = File(...),
    services: str = Form("myminio")
):
    print(f"\n📥 收到上传任务: {file.filename}")
    print(f"   ▶ 请求图床: {services}")
    try:
        content = await file.read()
        fhash = calculate_md5(content)
        info = get_image_info(content)

        # 解析前端传来的服务列表，只保留后端支持的
        todo_raw = [s.strip() for s in services.split(",") if s.strip()]
        todo = []
        for s in todo_raw:
            if s in SERVICE_MAP and s not in todo:
                todo.append(s)

        if not todo:
            todo = ["myminio"]  # 默认只走自建

        success_list = []
        failed_list = []

        for k in todo:
            func = SERVICE_MAP[k]
            print(f"→ 尝试图床: {k}")
            if k == "myminio":
                res = func(content, file.filename, fhash)
            else:
                res = func(content, file.filename)

            if res.get("success"):
                success_list.append(res)
            else:
                failed_list.append({
                    "service": k,
                    "error": res.get("error", "未知错误")
                })

        if not success_list:
            print("❌ 所有图床均失败")
            return JSONResponse({
                "success": False,
                "error": "所有图床均上传失败",
                "failed_list": failed_list
            })
        
        print("✨ 任务完成")
        main_res = success_list[0]
        return JSONResponse({
            "success": True,
            "filename": file.filename,
            "hash": fhash,
            "url": main_res["url"],
            "service": main_res["service"],
            "all_results": success_list,
            "failed_list": failed_list,
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

# === 8. 简单验证接口（你原来就是个占位） ===
@app.post("/validate")
async def val(d: dict):
    url = d.get("url")
    print(f"验证 URL 请求: {url}")
    # 这里现在直接返回 success=True，如果要做真实 HEAD 请求，可以再说
    return {"success": True, "url": url}

# === 9. 静态文件与首页 ===
app.mount("/static", StaticFiles(directory="frontend"), name="static")

@app.get("/")
def idx():
    return FileResponse(os.path.join("frontend", "index.html"))

if __name__ == "__main__":
    import uvicorn
    # 使用简洁的日志输出，因为我们已经有了漂亮的横幅
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_level="warning",
        access_log=False
    )
import socket
from fastapi import FastAPI, File, UploadFile, Form
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
import requests
from PIL import Image
from io import BytesIO
import os
import hashlib
import boto3
from botocore.client import Config
import traceback
import time

# === 1. 获取本机IP地址 (保留你的逻辑) ===
def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except:
        return "127.0.0.1"

# === 2. 生命周期事件处理器 (完全恢复你的原版文案) ===
@asynccontextmanager
async def lifespan(app: FastAPI):
    """服务器生命周期管理 - 启动和关闭事件"""
    
    # 获取 IP 用于打印
    local_ip = get_local_ip()
    port = 8000

    # 启动时执行 - 这里就是你要求的原封不动的文案
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
    
    yield  # 服务器运行期间
    
    # 关闭时执行
    print("\n👋 服务器已停止\n")

app = FastAPI(title="图片URL获取工具", lifespan=lifespan)

# === 3. 配置区域 ===
IMGBB_API_KEY = "7505d9912bf2caabcaf818aac92e562a"

# MinIO 配置
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

# === 5. 各图床上传函数 ===

def upload_to_imgbb(data, name):
    print(f"   [ImgBB] 正在上传 {name[:15]}...")
    try:
        files = {"image": (name, data)}
        # verify=False 仅用于测试环境解决 SSL 问题
        resp = requests.post(
            "https://api.imgbb.com/1/upload",
            data={"key": IMGBB_API_KEY},
            files=files,
            timeout=45,
            verify=False
        )
        
        if resp.status_code != 200:
            print(f"   ❌ [ImgBB] 失败: HTTP {resp.status_code} - {resp.text[:200]}")
            return {
                "success": False,
                "service": "ImgBB",
                "error": f"HTTP {resp.status_code}"
            }
        
        res = resp.json()
        if res.get("success"):
            print("   ✅ [ImgBB] 成功")
            return {
                "success": True,
                "service": "ImgBB",
                "url": res["data"]["url"]
            }
        else:
            err = res.get("error", {}).get("message", "API Error")
            print(f"   ❌ [ImgBB] API拒绝: {err}")
            return {
                "success": False,
                "service": "ImgBB",
                "error": err
            }
    except Exception as e:
        print(f"   ❌ [ImgBB] 异常: {e}")
        return {
            "success": False,
            "service": "ImgBB",
            "error": "网络错误或超时"
        }

def upload_to_minio(data, name, fhash):
    print(f"   [MyCloud] 正在上传 {name[:15]}...")
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
        
        # 简单的类型判断
        ctype = "application/octet-stream"
        if ext.lower() in [".jpg", ".jpeg"]:
            ctype = "image/jpeg"
        elif ext.lower() == ".png":
            ctype = "image/png"
        elif ext.lower() == ".gif":
            ctype = "image/gif"
        elif ext.lower() == ".webp":
            ctype = "image/webp"

        s3.put_object(Bucket=MINIO_BUCKET_NAME, Key=key, Body=data, ContentType=ctype)
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

def upload_to_catbox(data, name):
    """
    Catbox 官方说明：
      POST https://catbox.moe/user/api.php
      form-data:
        reqtype = "fileupload"
        fileToUpload = (file)
    返回：成功时为纯文本 URL
    """
    print(f"   [Catbox] 正在上传 {name[:15]}...")
    try:
        files = {
            "fileToUpload": (name, data)
        }
        payload = {
            "reqtype": "fileupload"
            # 可以加 userhash 做账号归属，这里留空表示匿名
        }
        resp = requests.post(
            "https://catbox.moe/user/api.php",
            data=payload,
            files=files,
            timeout=60
        )
        if resp.status_code != 200:
            print(f"   ❌ [Catbox] 失败: HTTP {resp.status_code} - {resp.text[:200]}")
            return {
                "success": False,
                "service": "Catbox",
                "error": f"HTTP {resp.status_code}"
            }
        url = resp.text.strip()
        if not (url.startswith("http://") or url.startswith("https://")):
            print(f"   ❌ [Catbox] 返回内容异常: {url[:200]}")
            return {
                "success": False,
                "service": "Catbox",
                "error": "返回内容不是 URL"
            }
        print("   ✅ [Catbox] 成功")
        return {
            "success": True,
            "service": "Catbox",
            "url": url
        }
    except Exception as e:
        print(f"   ❌ [Catbox] 异常: {e}")
        return {
            "success": False,
            "service": "Catbox",
            "error": "网络错误或超时"
        }

# === 6. 服务映射表 ===
SERVICE_MAP = {
    "myminio": upload_to_minio,
    "imgbb": upload_to_imgbb,
    "catbox": upload_to_catbox
}

# === 7. 上传接口 ===
@app.post("/upload")
async def upload_endpoint(
    file: UploadFile = File(...),
    services: str = Form("myminio")
):
    print(f"\n📥 收到上传任务: {file.filename}")
    print(f"   ▶ 请求图床: {services}")
    try:
        content = await file.read()
        fhash = calculate_md5(content)
        info = get_image_info(content)

        # 解析前端传来的服务列表，只保留后端支持的
        todo_raw = [s.strip() for s in services.split(",") if s.strip()]
        todo = []
        for s in todo_raw:
            if s in SERVICE_MAP and s not in todo:
                todo.append(s)

        if not todo:
            todo = ["myminio"]  # 默认只走自建

        success_list = []
        failed_list = []

        for k in todo:
            func = SERVICE_MAP[k]
            print(f"→ 尝试图床: {k}")
            if k == "myminio":
                res = func(content, file.filename, fhash)
            else:
                res = func(content, file.filename)

            if res.get("success"):
                success_list.append(res)
            else:
                failed_list.append({
                    "service": k,
                    "error": res.get("error", "未知错误")
                })

        if not success_list:
            print("❌ 所有图床均失败")
            return JSONResponse({
                "success": False,
                "error": "所有图床均上传失败",
                "failed_list": failed_list
            })
        
        print("✨ 任务完成")
        main_res = success_list[0]
        return JSONResponse({
            "success": True,
            "filename": file.filename,
            "hash": fhash,
            "url": main_res["url"],
            "service": main_res["service"],
            "all_results": success_list,
            "failed_list": failed_list,
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

# === 8. 简单验证接口（你原来就是个占位） ===
@app.post("/validate")
async def val(d: dict):
    url = d.get("url")
    print(f"验证 URL 请求: {url}")
    # 这里现在直接返回 success=True，如果要做真实 HEAD 请求，可以再说
    return {"success": True, "url": url}

# === 9. 静态文件与首页 ===
app.mount("/static", StaticFiles(directory="frontend"), name="static")

@app.get("/")
def idx():
    return FileResponse(os.path.join("frontend", "index.html"))

if __name__ == "__main__":
    import uvicorn
    # 使用简洁的日志输出，因为我们已经有了漂亮的横幅
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_level="warning",
        access_log=False
    )





