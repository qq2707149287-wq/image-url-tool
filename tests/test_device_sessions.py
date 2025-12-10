import sys
import os
# Add project root to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from fastapi.testclient import TestClient
from backend.main import app
import uuid
from backend import database

client = TestClient(app)

def test_session_lifecycle():
    # Ensure DB is initialized (it might be already, but harmless)
    database.init_db()

    # 1. Setup User
    unique_suffix = uuid.uuid4().hex[:6]
    username = f"test_sess_{unique_suffix}"
    password = "TestPassword123!"
    
    print(f"\nUser: {username}")

    # Register (creates session automatically)
    reg_res = client.post("/auth/register", json={"username": username, "password": password})
    if reg_res.status_code != 200:
        print(reg_res.json())
    assert reg_res.status_code == 200
    token1 = reg_res.json()["access_token"]
    print("Token 1 acquired (Registration)")
    
    # Verify Token 1 works
    me_res = client.get("/auth/me", headers={"Authorization": f"Bearer {token1}"})
    assert me_res.status_code == 200
    user_id = me_res.json()["id"]
    
    # 2. Get Active Sessions (Should be 1)
    sessions_res = client.get("/auth/sessions", headers={"Authorization": f"Bearer {token1}"})
    assert sessions_res.status_code == 200
    sessions = sessions_res.json()
    assert len(sessions) == 1
    session1_id = sessions[0]["session_id"]
    print(f"Session 1: {session1_id}")
    
    # 3. Login again (Simulate Device 2)
    # Login creates new session
    # Note: Login endpoint expects form data
    login_res = client.post("/auth/login", data={"username": username, "password": password})
    assert login_res.status_code == 200
    token2 = login_res.json()["access_token"]
    print("Token 2 acquired (Login)")
    
    # Verify Token 2 works
    me_res2 = client.get("/auth/me", headers={"Authorization": f"Bearer {token2}"})
    assert me_res2.status_code == 200
    
    # 4. Get Active Sessions (Should be 2)
    sessions_res = client.get("/auth/sessions", headers={"Authorization": f"Bearer {token2}"})
    assert len(sessions_res.json()) == 2
    print("Active Sessions count: 2")
    
    # 5. Token 2 revokes Token 1
    revoke_res = client.delete(f"/auth/sessions/{session1_id}", headers={"Authorization": f"Bearer {token2}"})
    assert revoke_res.status_code == 200
    print("Session 1 revoked")
    
    # 6. Verify Token 1 is invalid (401 or similar)
    # Note: get_current_user raises 401 if session invalid
    bad_res = client.get("/auth/me", headers={"Authorization": f"Bearer {token1}"})
    print(f"Token 1 access code: {bad_res.status_code}")
    assert bad_res.status_code == 401 or bad_res.status_code == 403
    
    # 7. Verify Token 2 is still valid
    good_res = client.get("/auth/me", headers={"Authorization": f"Bearer {token2}"})
    assert good_res.status_code == 200
    print("Token 2 still valid")
    
    print("✅ Test Passed: Session Management Flow")

if __name__ == "__main__":
    test_session_lifecycle()
