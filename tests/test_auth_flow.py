import requests
import uuid
import time
import sys
import os

# Use distinct port for testing
PORT = 8001
BASE_URL = f"http://localhost:{PORT}"

def test_auth_flow():
    # 0. Check health
    try:
        requests.get(f"{BASE_URL}/health")
    except Exception:
        print(f"Server not up at {BASE_URL}")
        sys.exit(1)

    # 1. Register
    username = f"user_{uuid.uuid4().hex[:8]}"
    password = "testpassword"
    print(f"Testing with user: {username}")
    
    reg_res = requests.post(f"{BASE_URL}/auth/register", json={"username": username, "password": password})
    if reg_res.status_code != 200:
        print(f"Register failed: {reg_res.text}")
        sys.exit(1)
    
    token_data = reg_res.json()
    token = token_data["access_token"]
    print(f"Registration successful, got token: {token[:10]}...")

    # 2. Login (verify token works)
    login_res = requests.post(f"{BASE_URL}/auth/login", data={"username": username, "password": password})
    if login_res.status_code != 200:
        print(f"Login failed: {login_res.text}")
        sys.exit(1)
    print("Login successful")

    # 3. Get Me
    headers = {"Authorization": f"Bearer {token}"}
    me_res = requests.get(f"{BASE_URL}/auth/me", headers=headers)
    if me_res.status_code != 200:
        print(f"Get Me failed: {me_res.text}")
        sys.exit(1)
    print(f"Me data: {me_res.json()}")

    # 4. Mock Upload (if possible, or just skip if we don't have minio)
    # We can check history instead. It should be empty but accessible.
    hist_res = requests.get(f"{BASE_URL}/history", headers=headers)
    if hist_res.status_code == 200:
        data = hist_res.json()
        print(f"History check successful. Count: {len(data.get('data', []))}")
    else:
        print(f"History failed: {hist_res.text}")
        sys.exit(1)

    print("✅ All auth tests passed!")

if __name__ == "__main__":
    # Simple retry to wait for server
    for i in range(10):
        try:
            test_auth_flow()
            break
        except Exception as e:
            if i == 9: raise e
            time.sleep(1)
