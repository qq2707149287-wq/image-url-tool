import requests

base_url = "http://localhost:8000"

# Login
res = requests.post(f"{base_url}/auth/login", data={'username': 'admin', 'password': '18793457'})
token = res.json()['access_token']

# Get stats
res = requests.get(f"{base_url}/admin/stats", headers={'Authorization': f'Bearer {token}'})
print(f"Status: {res.status_code}")
print(f"Response: {res.json()}")
