import sys
import os
# Add project root to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from fastapi.testclient import TestClient
from backend.main import app
import uuid
from backend import database
from datetime import datetime, timedelta

client = TestClient(app)

def test_vip_lifecycle():
    # Ensure DB is initialized
    database.init_db()

    # 1. Setup Admin User (to generate codes)
    admin_suffix = uuid.uuid4().hex[:6]
    admin_username = f"admin_{admin_suffix}"
    admin_password = "AdminPassword123!"
    
    # Register admin (manually update DB to set is_admin=1)
    client.post("/auth/register", json={"username": admin_username, "password": admin_password})
    
    # Force set as admin
    with database.get_db_connection() as conn:
        c = conn.cursor()
        c.execute("UPDATE users SET is_admin = 1 WHERE username = ?", (admin_username,))
        conn.commit()
    
    # Login as Admin
    admin_login = client.post("/auth/login", data={"username": admin_username, "password": admin_password})
    admin_token = admin_login.json()["access_token"]
    
    # 2. Setup Normal User
    user_suffix = uuid.uuid4().hex[:6]
    username = f"user_{user_suffix}"
    password = "UserPassword123!"
    
    client.post("/auth/register", json={"username": username, "password": password})
    login_res = client.post("/auth/login", data={"username": username, "password": password})
    user_token = login_res.json()["access_token"]
    
    # 3. Verify User is NOT VIP initially
    me_res = client.get("/auth/me", headers={"Authorization": f"Bearer {user_token}"})
    user_data = me_res.json()
    assert user_data["is_vip"] == False
    assert user_data["vip_expiry"] is None
    
    # 4. Generate VIP Code (As Admin)
    gen_res = client.post("/admin/vip/generate", 
                          data={"days": 30, "count": 1},
                          headers={"Authorization": f"Bearer {admin_token}"})
    assert gen_res.status_code == 200
    vip_code = gen_res.json()["codes"][0]
    print(f"Generated VIP Code: {vip_code}")
    
    # 5. Activate VIP (As User)
    act_res = client.post("/auth/vip/activate",
                          json={"code": vip_code},
                          headers={"Authorization": f"Bearer {user_token}"})
    if act_res.status_code != 200:
        print(act_res.json())
    assert act_res.status_code == 200
    expiry_str = act_res.json()["expiry"]
    print(f"VIP Activated! Expiry: {expiry_str}")
    
    # 6. Verify User IS VIP now
    me_res_after = client.get("/auth/me", headers={"Authorization": f"Bearer {user_token}"})
    user_data_after = me_res_after.json()
    assert user_data_after["is_vip"] == True
    assert user_data_after["vip_expiry"] == expiry_str
    
    # 7. Try to reuse code (Should Fail)
    act_res_fail = client.post("/auth/vip/activate",
                          json={"code": vip_code},
                          headers={"Authorization": f"Bearer {user_token}"})
    assert act_res_fail.status_code == 400
    assert "已被使用" in act_res_fail.json()["detail"]
    
    # 8. Extend VIP (Stacking)
    # Generate another 10 days code
    gen_res2 = client.post("/admin/vip/generate", 
                          data={"days": 10, "count": 1},
                          headers={"Authorization": f"Bearer {admin_token}"})
    vip_code2 = gen_res2.json()["codes"][0]
    
    # Activate
    act_res2 = client.post("/auth/vip/activate",
                          json={"code": vip_code2},
                          headers={"Authorization": f"Bearer {user_token}"})
    assert act_res2.status_code == 200
    
    # Check new expiry (Should be around 30+10 = 40 days from now)
    # Just check if it's later than first expiry
    new_expiry_str = act_res2.json()["expiry"]
    first_date = datetime.strptime(expiry_str, "%Y-%m-%d %H:%M:%S")
    second_date = datetime.strptime(new_expiry_str, "%Y-%m-%d %H:%M:%S")
    
    assert second_date > first_date
    print(f"VIP Extended! New Expiry: {new_expiry_str}")
    
    print("✅ VIP System Test Passed")

if __name__ == "__main__":
    test_vip_lifecycle()
