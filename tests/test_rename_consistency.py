import requests
import uuid
import sys
import time

PORT = 8001
BASE_URL = f"http://localhost:{PORT}" 

def test_rename():
    print(f"正在测试重命名一致性 (目标: {BASE_URL})...")
    
    # Wait for server to be up
    for i in range(10):
        try:
            r = requests.get(f"{BASE_URL}/health")
            if r.status_code == 200:
                print("✅ 服务器已启动。")
                break
        except:
            time.sleep(1)
            print("⏳ 等待服务器响应...")
    else:
        print("❌ 服务器启动失败。")
        sys.exit(1)

    # Register/Login
    username = f"user_{uuid.uuid4().hex[:8]}"
    pwd = "password"
    token = register_user(username, pwd)
    if not token:
        print("❌ 注册/登录失败")
        sys.exit(1)

    headers = {"Authorization": f"Bearer {token}"}

    # Upload Image 1
    content1 = f"img1_{uuid.uuid4()}".encode()
    files1 = {'file': ('org1.jpg', content1, 'image/jpeg')}
    # Ensure token is passed properly
    res1 = requests.post(f"{BASE_URL}/upload", files=files1, data={'token': token, 'shared_mode': 'false'})
    
    if res1.status_code != 200:
         print(f"❌ 上传图片1失败: {res1.text}")
         sys.exit(1)

    id1 = res1.json().get('id')
    
    if not id1:
        print(f"❌ 上传图片1未返回ID! 响应: {res1.json()}")
        sys.exit(1)

    print(f"📸 图片1上传成功: ID={id1}")

    # Upload Image 2 (Different content)
    content2 = f"img2_{uuid.uuid4()}".encode()
    files2 = {'file': ('org2.jpg', content2, 'image/jpeg')}
    res2 = requests.post(f"{BASE_URL}/upload", files=files2, data={'token': token, 'shared_mode': 'false'})
    id2 = res2.json().get('id')

    if not id2:
         print("❌ 上传图片2未返回ID!")
         sys.exit(1)

    print(f"📸 图片2上传成功: ID={id2}")

    # Rename Img 1 using ID
    new_name = "renamed_by_id.jpg"
    rename_res = requests.post(
        f"{BASE_URL}/history/rename",
        json={"id": id1, "filename": new_name},
        headers=headers
    )
    
    if rename_res.status_code != 200:
         print(f"❌ 重命名API请求失败 {rename_res.status_code}: {rename_res.text}")
         sys.exit(1)
         
    if not rename_res.json().get('success'):
         print(f"❌ 重命名逻辑失败: {rename_res.json()}")
         sys.exit(1)

    # Verify Img 1 is renamed
    # Get history and check
    hist_res = requests.get(f"{BASE_URL}/history?page_size=100&view_mode=private", headers=headers)
    items = hist_res.json()['data']
    
    print(f"📊 历史记录中找到 {len(items)} 项。")
    
    item1 = next((i for i in items if i['id'] == id1), None)
    item2 = next((i for i in items if i['id'] == id2), None)
    
    if not item1:
        print("❌ 历史记录中未找到图片1")
        sys.exit(1)

    if item1['filename'] != new_name:
         print(f"❌ 图片1文件名不匹配: {item1['filename']} != {new_name}")
         sys.exit(1)
         
    if item2:
        if item2['filename'] == new_name:
             print(f"❌ 图片2被错误地重命名了！")
             sys.exit(1)
    
    print("✅ 重命名一致性测试通过！")

def register_user(username, password):
    try:
        res = requests.post(f"{BASE_URL}/auth/register", json={"username": username, "password": password})
        if res.status_code == 200:
            return res.json()['access_token']
        # If already exists, login
        login_res = requests.post(f"{BASE_URL}/auth/login", data={"username": username, "password": password})
        if login_res.status_code == 200:
             return login_res.json()['access_token']
    except Exception as e:
        print(f"Auth Error: {e}")
    return None

if __name__ == "__main__":
    test_rename()
