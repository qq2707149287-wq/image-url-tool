import requests
import json

url = "http://localhost:8000/upload"
file_path = r"C:\Users\qq270\.gemini\antigravity\brain\efa5fb12-d278-41e6-b25f-0d65a0777fb1\uploaded_image_1765356951018.jpg"

# 1. Login
auth_url = "http://localhost:8000/auth/login"
login_data = {
    "username": "aa",
    "password": "11"
}

print(f"Logging in as {login_data['username']}...")
try:
    auth_response = requests.post(auth_url, data=login_data) # Form data for OAuth2
    if auth_response.status_code != 200:
        print(f"Login failed: {auth_response.status_code} {auth_response.text}")
        exit(1)
    
    token = auth_response.json()["access_token"]
    print("Login success! Token acquired.")
    
    # 2. Upload with Token
    headers = {"Authorization": f"Bearer {token}"}
    
    with open(file_path, "rb") as f:
        files = {"file": ("mosaic.jpg", f, "image/jpeg")}
        data = {"is_shared": "true"} 
        print(f"Uploading {file_path} (Shared Mode)...")
        response = requests.post(url, files=files, data=data, headers=headers, timeout=10)
        
        print(f"Status Code: {response.status_code}")
        try:
            data = response.json()
            print("Response JSON:")
            print(json.dumps(data, indent=2, ensure_ascii=False))
            
            if "audit_logs" in data and "clip" in data["audit_logs"]:
                clip_scores = data["audit_logs"]["clip"]
                target_label = "拼贴艺术或马赛克风格"
                if target_label in clip_scores:
                    score = clip_scores[target_label]
                    print(f"\n[VERIFICATION] '{target_label}' Score: {score:.4f}")
                    if score > 0.5:
                        print("✅ SUCCESS: High score for Mosaic Art!")
                    else:
                        print("⚠️ WARNING: Score is low. Check model.")
                else:
                    print(f"❌ '{target_label}' NOT FOUND in audit logs.")
            else:
                print("No audit details found.")
                
        except json.JSONDecodeError:
            print("Response text:", response.text)

except Exception as e:
    print(f"Error: {e}")
