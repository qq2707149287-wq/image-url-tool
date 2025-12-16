import requests
import json
import sys

# Configuration
BASE_URL = "http://localhost:8000"
USERNAME = "admin"
PASSWORD = "18793457"

def test_admin_flow():
    session = requests.Session()
    
    print(f"🔹 1.Logging in as {USERNAME}...")
    try:
        res = session.post(f"{BASE_URL}/auth/login", data={
            "username": USERNAME,
            "password": PASSWORD
        })
        
        if res.status_code != 200:
            print(f"❌ Login failed: {res.text}")
            return False
            
        data = res.json()
        token = data["access_token"]
        is_admin = data.get("is_admin")
        print(f"✅ Login successful. Token obtained.")
        print(f"   is_admin: {is_admin}")
        
        if not is_admin:
            print("❌ User is NOT an admin! Cannot proceed with admin tests.")
            # Optional: Try to promote user if running locally? 
            # But let's fail first.
            return False
            
        headers = {"Authorization": f"Bearer {token}"}
        
    except Exception as e:
        print(f"❌ Connection error: {e}")
        return False

    # 2. Test Get Stats
    print("\n🔹 2. Testing GET /admin/stats...")
    res = session.get(f"{BASE_URL}/admin/stats", headers=headers)
    if res.status_code == 200:
        print(f"✅ Stats: {json.dumps(res.json(), ensure_ascii=False)}")
    else:
        print(f"❌ Failed to get stats: {res.status_code} {res.text}")

    # 3. Test Get Reports
    print("\n🔹 3. Testing GET /admin/reports...")
    res = session.get(f"{BASE_URL}/admin/reports", headers=headers)
    if res.status_code == 200:
        reports = res.json()
        print(f"✅ Reports count: {len(reports.get('data', [])) if isinstance(reports, dict) else 'Unknown'}")
        if isinstance(reports, dict) and reports.get("data"):
             print(f"   First report sample: {reports['data'][0].get('reason')}")
    else:
        print(f"❌ Failed to get reports: {res.status_code} {res.text}")

    # 4. Test Get All Images
    print("\n🔹 4. Testing GET /admin/images...")
    res = session.get(f"{BASE_URL}/admin/images", headers=headers)
    if res.status_code == 200:
        images = res.json()
        print(f"✅ Images count (page 1): {len(images.get('data', [])) if isinstance(images, dict) else 'Unknown'}")
        if images.get('data'):
            first_img = images['data'][0]
            raw_url = first_img.get('url')
            print(f"   Raw URL: {raw_url}")
            
            # Simulate frontend logic
            if raw_url:
                target_url = raw_url.replace('/view/', '/mycloud/')
                full_target_url = f"{BASE_URL}{target_url}"
                print(f"   Target Thumbnail URL: {full_target_url}")
                
                # Try to fetch it
                img_res = session.get(full_target_url)
                print(f"   Thumbnail Fetch Status: {img_res.status_code}")
                print(f"   Content-Type: {img_res.headers.get('Content-Type')}")
                if img_res.status_code != 200:
                    print(f"   Thumbnail Error: {img_res.text[:200]}")
                else:
                    print(f"   Thumbnail Size: {len(img_res.content)} bytes")
    else:
        print(f"❌ Failed to get images: {res.status_code} {res.text}")

    return True

if __name__ == "__main__":
    success = test_admin_flow()
    if success:
        print("\n🎉 Test Completed Successfully!")
        sys.exit(0)
    else:
        print("\n⚠️ Test Failed!")
        sys.exit(1)
