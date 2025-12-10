import requests
import sqlite3
import uuid
import sys
import os

PORT = 8001
BASE_URL = f"http://localhost:{PORT}"
DB_PATH = "d:/codes/real-projects/image-url-tool/history.db"

def test_admin_deletion():
    print("🚀 Testing Admin Deletion Power...")

    # 1. Register Victim User (User A)
    victim_name = f"victim_{uuid.uuid4().hex[:8]}"
    victim_token = register_user(victim_name, "password")
    if not victim_token: sys.exit(1)
    
    # 2. Victim Uploads Private Image
    print(f"👤 Victim {victim_name} uploading private image...")
    files = {'file': ('victim.jpg', b'private_content', 'image/jpeg')}
    res = requests.post(f"{BASE_URL}/upload", files=files, data={'shared_mode': 'false', 'token': victim_token})
    print(f"   Upload Status: {res.status_code}")
    if res.status_code != 200:
        print(f"   Upload Failed: {res.text}")
        sys.exit(1)
    
    resp_json = res.json()
    print(f"   Upload Response: {resp_json}")
    victim_img_hash = resp_json.get('hash')
    
    # Get ID of this image
    headers_victim = {"Authorization": f"Bearer {victim_token}"}
    hist_res = requests.get(f"{BASE_URL}/history?view_mode=private", headers=headers_victim)
    print(f"   History Status: {hist_res.status_code}")
    hist = hist_res.json()
    # print(f"   History Response: {hist}")
    
    if not hist.get('data'):
         print("   No history data found!")
         sys.exit(1)
         
    img_id = next((i['id'] for i in hist['data'] if i['hash'] == victim_img_hash), None)
    print(f"   Image ID: {img_id}")
    if not img_id:
        print("   Could not find uploaded image in history!")
        sys.exit(1)

    # 3. Register Admin User
    admin_name = f"admin_{uuid.uuid4().hex[:8]}"
    admin_token = register_user(admin_name, "password") # Initially normal user
    
    # 4. PROMOTE TO ADMIN via SQL
    print(f"👮 Promoting {admin_name} to ADMIN via SQL...")
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE users SET is_admin = 1 WHERE username = ?", (admin_name,))
    conn.commit()
    conn.close()
    
    # 5. Admin tries to delete Victim's image
    print("🔥 Admin attempting to delete Victim's image...")
    headers_admin = {"Authorization": f"Bearer {admin_token}"}
    del_res = requests.post(
        f"{BASE_URL}/history/delete",
        json={"ids": [img_id]},
        headers=headers_admin
    )
    
    print(f"   Response: {del_res.json()}")
    
    if del_res.json().get("success") and del_res.json().get("count") == 1:
        print("✅ Success! Admin deleted another user's private image.")
    else:
        print("❌ Failed! Admin could not delete image.")
        print(del_res.text)
        sys.exit(1)

def register_user(username, password):
    res = requests.post(f"{BASE_URL}/auth/register", json={"username": username, "password": password})
    if res.status_code == 200:
        return res.json()['access_token']
    print(f"Register failed: {res.text}")
    return None

if __name__ == "__main__":
    try:
        test_admin_deletion()
    except Exception as e:
        print(f"Exception: {e}")
        sys.exit(1)
