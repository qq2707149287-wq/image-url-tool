import sys
import os
# Add project root to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from fastapi.testclient import TestClient
from backend.main import app
from backend import database
import uuid

import logging

# Configure logging to show INFO level
logging.basicConfig(level=logging.INFO, stream=sys.stdout, format='%(asctime)s - %(levelname)s - %(message)s')

client = TestClient(app)

def test_rate_limits():
    database.init_db()
    
    # Clean history for this test to ensure clean counts
    with database.get_db_connection() as conn:
        conn.execute("DELETE FROM history")
        conn.commit()

    # 1. Anonymous User (Limit: 2)
    print("\n--- Testing Anonymous Limit (2) ---")
    headers = {"X-Device-ID": "test_device_anon"}
    
    # Upload 1
    res1 = client.post("/upload", 
                       files={"file": ("test1.jpg", b"fake_content_1", "image/jpeg")},
                       data={"shared_mode": "true"}, # Anon must use shared
                       headers=headers)
    assert res1.status_code == 200
    print("Upload 1: OK")
    
    # Upload 2
    res2 = client.post("/upload", 
                       files={"file": ("test2.jpg", b"fake_content_2", "image/jpeg")},
                       data={"shared_mode": "true"},
                       headers=headers)
    assert res2.status_code == 200
    print("Upload 2: OK")
    
    # Upload 3 (Should Fail)
    res3 = client.post("/upload", 
                       files={"file": ("test3.jpg", b"fake_content_3", "image/jpeg")},
                       data={"shared_mode": "true"},
                       headers=headers)
    if res3.status_code == 429:
        print("Upload 3: BLOCKED (Expected)")
    else:
        print(f"Upload 3: Failed to Block (Status: {res3.status_code})")
        print(res3.json())
    assert res3.status_code == 429
    
    # 2. Free User (Limit: 5)
    print("\n--- Testing Free User Limit (5) ---")
    user_suffix = uuid.uuid4().hex[:6]
    username = f"free_user_{user_suffix}"
    client.post("/auth/register", json={"username": username, "password": "pwd"})
    login_res = client.post("/auth/login", data={"username": username, "password": "pwd"})
    token = login_res.json()["access_token"]
    user_headers = {"Authorization": f"Bearer {token}"}
    
    # Upload 5 times
    for i in range(5):
        res = client.post("/upload", 
                       files={"file": (f"free_{i}.jpg", f"content_{i}".encode(), "image/jpeg")},
                       data={"shared_mode": "false"},
                       headers=user_headers)
        assert res.status_code == 200
        print(f"Free Upload {i+1}: OK")
        
    # Upload 6 (Should Fail)
    res6 = client.post("/upload", 
                   files={"file": ("free_6.jpg", b"content_6", "image/jpeg")},
                   data={"shared_mode": "false"},
                   headers=user_headers)
    assert res6.status_code == 429
    print("Free Upload 6: BLOCKED (Expected)")
    
    # 3. VIP User (Unlimited)
    print("\n--- Testing VIP User (Unlimited) ---")
    # Register Admin to generate code
    admin_suffix = uuid.uuid4().hex[:6]
    admin_name = f"admin_{admin_suffix}"
    client.post("/auth/register", json={"username": admin_name, "password": "pwd"})
    with database.get_db_connection() as conn:
        conn.execute("UPDATE users SET is_admin=1 WHERE username=?", (admin_name,))
        conn.commit()
    admin_token = client.post("/auth/login", data={"username": admin_name, "password": "pwd"}).json()["access_token"]
    
    # Generate Code
    gen = client.post("/admin/vip/generate", data={"days": 1, "count": 1}, headers={"Authorization": f"Bearer {admin_token}"})
    if gen.status_code != 200:
        print("Gen failed:", gen.json())
    code = gen.json()["codes"][0]
    
    # Activate for Free User
    client.post("/auth/vip/activate", json={"code": code}, headers=user_headers)
    
    # Upload 6th time again (Should Succeed now)
    res_vip = client.post("/upload", 
                   files={"file": ("vip_test.jpg", b"vip_content", "image/jpeg")},
                   data={"shared_mode": "false"},
                   headers=user_headers)
    assert res_vip.status_code == 200
    print("VIP Upload (6th): OK (Unblocked)")

    print("\n✅ All Rate Limit Tests Passed!")

if __name__ == "__main__":
    test_rate_limits()
