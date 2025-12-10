import os
import sys
from fastapi.testclient import TestClient

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.main import app
from backend import database

client = TestClient(app)

def test_api_clear():
    print("--- Starting API Clear Test ---")
    
    # Initialize DB
    database.init_db()
    
    # Mock data
    device_id = "api_test_device"
    
    # We need to simulate the cookie
    cookies = {"device_id": device_id}
    
    # Clean up first
    database.clear_all_history(device_id, view_mode="private")
    database.clear_all_history(device_id, view_mode="shared")
    
    # 1. Create Private and Shared images
    print("1. Creating images...")
    img_p = {
        "url": "http://p.com", "filename": "p.png", "hash": "hash_p", 
        "service": "local", "width": 100, "height": 100, "size": 100, "content_type": "image/png"
    }
    img_s = {
        "url": "http://s.com", "filename": "s.png", "hash": "hash_s", 
        "service": "local", "width": 100, "height": 100, "size": 100, "content_type": "image/png"
    }
    
    database.save_to_db(img_p, device_id=device_id, is_shared=False)
    database.save_to_db(img_s, device_id=device_id, is_shared=True)
    
    # Verify creation
    res_p = client.get("/history?view_mode=private", cookies=cookies).json()
    res_s = client.get("/history?view_mode=shared", cookies=cookies).json()
    print(f"   -> Private count: {len(res_p['data'])}")
    print(f"   -> Shared count: {len(res_s['data'])}")
    
    if len(res_p['data']) != 1 or len(res_s['data']) != 1:
        print("❌ Setup failed.")
        return

    # 2. Clear Private via API
    print("\n2. Clearing PRIVATE via API...")
    resp = client.post("/history/clear?view_mode=private", cookies=cookies)
    print(f"   -> Response: {resp.json()}")
    
    # Verify
    res_p = client.get("/history?view_mode=private", cookies=cookies).json()
    res_s = client.get("/history?view_mode=shared", cookies=cookies).json()
    print(f"   -> Private count: {len(res_p['data'])}")
    print(f"   -> Shared count: {len(res_s['data'])}")
    
    if len(res_p['data']) == 0 and len(res_s['data']) == 1:
        print("✅ PASSED: API Clear Private worked.")
    else:
        print("❌ FAILED: API Clear Private failed.")

    # 3. Clear Shared via API
    print("\n3. Clearing SHARED via API...")
    resp = client.post("/history/clear?view_mode=shared", cookies=cookies)
    print(f"   -> Response: {resp.json()}")
    
    # Verify
    res_s = client.get("/history?view_mode=shared", cookies=cookies).json()
    print(f"   -> Shared count: {len(res_s['data'])}")
    
    if len(res_s['data']) == 0:
        print("✅ PASSED: API Clear Shared worked.")
    else:
        print("❌ FAILED: API Clear Shared failed.")

if __name__ == "__main__":
    test_api_clear()
