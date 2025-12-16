import requests

base_url = "http://localhost:8000"
username = "admin"
password = "18793457"

# 1. Login
print("1. Logging in...")
session = requests.Session()
login_res = session.post(f"{base_url}/auth/login", data={'username': username, 'password': password})
if login_res.status_code != 200:
    print(f"Login Failed: {login_res.text}")
    exit(1)
token = login_res.json()['access_token']
headers = {'Authorization': f"Bearer {token}"}
print("Login successful.")

# 2. Upload
print("\n2. Uploading image...")
tiny_png = b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\rIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82'

files = {'file': ('test_cat.png', tiny_png, 'image/png')}
try:
    # Use session or headers? Endpoint allows Bearer token or cookie.
    # Upload check: upload_endpoint(..., current_user=Depends(...))
    res = requests.post(
        f"{base_url}/upload", 
        files=files, 
        data={'shared_mode': 'true'},
        headers=headers 
    )
    print(f"Upload Status: {res.status_code}")
    if res.status_code == 200:
        data = res.json()
        print(f"Upload Result: {data}")
        file_url = data['url']
        full_url = f"{base_url}{file_url}"
        
        # 3. Fetch
        print(f"\n3. Fetching {full_url}...")
        # Fetch without headers (public access)
        res_get = requests.get(full_url)
        print(f"Fetch Status: {res_get.status_code}")
        print(f"Content-Length: {len(res_get.content)}")
    else:
        print(f"Upload Failed: {res.text}")

except Exception as e:
    print(f"Error: {e}")
