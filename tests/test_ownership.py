import requests
import uuid
import sys

# Use distinct port for testing
PORT = 8001
BASE_URL = f"http://localhost:{PORT}"

def test_ownership_transfer():
    print("Testing Ownership Logic...")

    # 1. Register User A
    username = f"user_{uuid.uuid4().hex[:8]}"
    pwd = "password"
    token = register_user(username, pwd)
    if not token:
        sys.exit(1)

    # 2. Case A: Upload UNIQUE image as User A -> Should own it
    unique_content = f"unique_{uuid.uuid4()}".encode()
    files = {'file': ('test.jpg', unique_content, 'image/jpeg')}
    
    print(f"User {username} uploading NEW image...")
    res1 = requests.post(
        f"{BASE_URL}/upload",
        files=files,
        data={'shared_mode': 'true', 'token': token}
    )
    if res1.status_code != 200:
        print(f"Upload failed: {res1.text}")
        sys.exit(1)
    
    hash1 = res1.json()['hash']
    
    # Check ownership (is_mine should be true)
    headers = {"Authorization": f"Bearer {token}"}
    hist_res = requests.get(f"{BASE_URL}/history?view_mode=shared", headers=headers)
    items = hist_res.json()['data']
    my_item = next((i for i in items if i['hash'] == hash1), None)
    
    if not my_item or not my_item['is_mine']:
        print("❌ Case A Failed: New image NOT owned by uploader.")
        # Debug info
        if my_item:
             print(f"Item found but is_mine={my_item['is_mine']}, user_id={my_item.get('user_id')}")
        sys.exit(1)
    print("✅ Case A Passed: New image owned by uploader.")

    # 3. Case B: Anonymous upload first, then User A uploads SAME image -> User A should CLAIM it?
    # Current behavior: User A probably doesn't own it.
    # User Request implies: They want to control it.
    
    anon_content = f"anon_{uuid.uuid4()}".encode()
    
    # Upload as Anonymous (No token)
    # Note: Anonymous can only upload to shared mode now.
    print("Uploading as Anonymous...")
    files_anon = {'file': ('anon.jpg', anon_content, 'image/jpeg')}
    res_anon = requests.post(
        f"{BASE_URL}/upload",
        files=files_anon,
        data={'shared_mode': 'true'} # Anonymous forced shared
    )
    if res_anon.status_code != 200:
        print(f"Anon upload failed: {res_anon.text}")
        sys.exit(1)
    
    hash2 = res_anon.json()['hash']
    
    # Now User A uploads SAME content
    print(f"User {username} uploading SAME anonymous image...")
    files_reup = {'file': ('reup.jpg', anon_content, 'image/jpeg')}
    res_reup = requests.post(
        f"{BASE_URL}/upload",
        files=files_reup,
        data={'shared_mode': 'true', 'token': token}
    )
    
    # Check if User A owns it now
    hist_res2 = requests.get(f"{BASE_URL}/history?view_mode=shared&page_size=100", headers=headers)
    items2 = hist_res2.json()['data']
    reup_item = next((i for i in items2 if i['hash'] == hash2), None)
    
    if not reup_item:
        print("❌ Case B Error: Item disappeared?")
        sys.exit(1)
        
    print(f"Re-uploaded Item Ownership: is_mine={reup_item['is_mine']}, user_id={reup_item.get('user_id')}")
    
    if reup_item['is_mine']:
        print("✅ Case B Passed: User CLAIMED the anonymous image.")
    else:
        print("⚠️ Case B Result: User did NOT claim the image (Expected with current code).")
        # This confirms why user is angry.

def register_user(username, password):
    res = requests.post(f"{BASE_URL}/auth/register", json={"username": username, "password": password})
    if res.status_code == 200:
        return res.json()['access_token']
    print(f"Register failed: {res.text}")
    return None

if __name__ == "__main__":
    try:
        test_ownership_transfer()
    except Exception as e:
        print(f"Exception: {e}")
        sys.exit(1)
