
from fastapi.testclient import TestClient
from backend.main import app
from backend import schemas
from backend import database
import pytest
import os

client = TestClient(app)

# Mock email sending to avoid real spam or needing credentials in test env if .env not loaded
# But we want to test real logic if possible. 
# main.py loads .env. If present, it works.

def test_send_code_register():
    # 1. Send Code
    response = client.post("/auth/send-code", json={"email": "test_register@example.com", "type": "register"})
    # If SMTP fails (e.g. invalid creds in .env or network), this might fail. 
    # But code logic is 200 on success.
    # We can mock email_utils.send_verification_code
    
    # Check if database has code
    code = database.get_valid_verification_code("test_register@example.com", "register")
    assert code is not None
    assert len(code) == 6

def test_register_email_flow():
    email = "test_user_new@example.com"
    username = "test_user_new"
    password = "password123"
    
    # 1. Send Code
    database.save_verification_code(email, "123456", "register", datetime.now() + timedelta(minutes=10))
    
    # 2. Register
    response = client.post("/auth/register-email", json={
        "username": username,
        "password": password,
        "email": email,
        "code": "123456"
    })
    if response.status_code != 200:
        print(response.json())
    assert response.status_code == 200
    assert response.json()["success"] == True
    
    # 3. Login
    response = client.post("/auth/login", data={"username": username, "password": password})
    assert response.status_code == 200
    assert "access_token" in response.json()

from datetime import datetime, timedelta

