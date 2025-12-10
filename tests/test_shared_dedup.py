import requests
import uuid
import time
import sys

# Use distinct port for testing
PORT = 8001
BASE_URL = f"http://localhost:{PORT}"

def test_shared_dedup():
    print("Testing Shared Mode Deduplication...")

    # 1. Create two users
    username1 = f"user1_{uuid.uuid4().hex[:8]}"
    username2 = f"user2_{uuid.uuid4().hex[:8]}"
    pwd = "password"

    token1 = register_user(username1, pwd)
    token2 = register_user(username2, pwd)

    if not token1 or not token2:
        sys.exit(1)

    # 2. Upload Image X as User 1 (Shared)
    # Use a unique fake image content to ensure hash is unique for this test run
    unique_content = f"fake_image_{uuid.uuid4()}".encode()
    files = {'file': ('test.jpg', unique_content, 'image/jpeg')}
    
    print(f"User 1 uploading Hash X (Shared)...")
    res1 = requests.post(
        f"{BASE_URL}/upload",
        files=files,
        data={'shared_mode': 'true', 'token': token1}
    )
    if res1.status_code != 200:
        print(f"User 1 upload failed: {res1.text}")
        sys.exit(1)
    
    hash1 = res1.json()['hash']
    print(f"Uploaded Hash: {hash1}")

    # 3. Upload SAME Image X as User 2 (Shared)
    print(f"User 2 uploading SAME Hash X (Shared)...")
    # Need to rewind file or re-create
    files2 = {'file': ('test.jpg', unique_content, 'image/jpeg')}
    res2 = requests.post(
        f"{BASE_URL}/upload",
        files=files2,
        data={'shared_mode': 'true', 'token': token2}
    )
    if res2.status_code != 200:
        print(f"User 2 upload failed: {res2.text}")
        sys.exit(1)

    # 4. Check shared history count for this hash
    # We need to query history. Since both are users, we can just check via User 1 or User 2.
    # We want to see how many items with this hash exist in shared mode.
    # Note: Search by keyword logic might not work for hash, but we can list all shared and filter.
    print("Checking history...")
    headers = {"Authorization": f"Bearer {token1}"}
    hist_res = requests.get(f"{BASE_URL}/history?view_mode=shared&page_size=100", headers=headers)
    
    if hist_res.status_code != 200:
        print(f"History fetch failed: {hist_res.text}")
        sys.exit(1)
    
    items = hist_res.json()['data']
    # Filter by our hash
    matches = [item for item in items if item['hash'] == hash1]
    
    print(f"Found {len(matches)} matches for hash {hash1} in shared history.")
    
    if len(matches) == 1:
        print("✅ Correct: Only 1 record found!")
    elif len(matches) > 1:
        print(f"❌ Incorrect: Found {len(matches)} duplicates!")
        sys.exit(1)
    else:
        print("❌ Error: Image not found in history!")
        sys.exit(1)

def register_user(username, password):
    res = requests.post(f"{BASE_URL}/auth/register", json={"username": username, "password": password})
    if res.status_code == 200:
        return res.json()['access_token']
    print(f"Register failed for {username}: {res.text}")
    return None

if __name__ == "__main__":
    try:
        test_shared_dedup()
    except Exception as e:
        print(f"Exception: {e}")
        sys.exit(1)
