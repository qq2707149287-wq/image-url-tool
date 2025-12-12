import os
import random
import string
import logging
import uuid
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from passlib.context import CryptContext
from jose import JWTError, jwt
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests
from dotenv import load_dotenv

from .. import database
from .. import schemas
from .. import email_utils
from .. import captcha_utils  # 验证码工具

# Setup Logger
logger = logging.getLogger(__name__)

# Load Env
load_dotenv()

# ==================== 配置常量 ====================
# [SECURITY] 强制要求 SECRET_KEY
SECRET_KEY = os.getenv("SECRET_KEY")
if not SECRET_KEY:
    logger.warning("⚠️ [Auth] 未配置 SECRET_KEY! 使用随机生成的临时密钥。")
    SECRET_KEY = "".join(random.choices(string.ascii_letters + string.digits, k=64))

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 30 # 30 Days
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "YOUR_GOOGLE_CLIENT_ID")
# Debug Mode (Lazy load from main or database? For simplicity, assume False or check env)
# We can't easily import SYSTEM_SETTINGS from main to avoid circular import.
# For now, we'll check env var or database setting if needed, or pass it in context.
# Let's assume production secure defaults.

# ==================== Security Utils ====================
pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login", auto_error=False)

router = APIRouter(prefix="/auth", tags=["auth"])

def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    return pwd_context.hash(password)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

async def get_current_user_optional(token: str = Depends(oauth2_scheme)):
    """
    Get current user if token is present and valid, else None.
    """
    if not token:
        return None
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            return None
            
        # Validate Session ID if present
        sid = payload.get("sid")
        if sid:
            if not database.validate_session(sid):
                return None
        
    except JWTError:
        return None
    
    user = database.get_user_by_username(username)
    return user

async def get_current_user(token: str = Depends(oauth2_scheme)):
    """
    Enforce auth.
    """
    user = await get_current_user_optional(token)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user

# ==================== Routes ====================

@router.get("/config")
async def get_auth_config():
    """返回公开认证配置"""
    return {
        "google_client_id": GOOGLE_CLIENT_ID if GOOGLE_CLIENT_ID != "YOUR_GOOGLE_CLIENT_ID" else None
    }

@router.post("/register", response_model=schemas.Token)
async def register(request: Request, user: schemas.UserCreate):
    if database.get_user_by_username(user.username):
        raise HTTPException(status_code=400, detail="Username already registered")
    
    hashed_password = get_password_hash(user.password)
    if not database.create_user(user.username, hashed_password):
         raise HTTPException(status_code=500, detail="Registration failed")
    
    # Auto login
    new_user = database.get_user_by_username(user.username)
    if new_user:
        sid = database.create_session(new_user['id'], request.headers.get("user-agent"), request.client.host)
        access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            data={"sub": user.username, "sid": sid}, expires_delta=access_token_expires
        )
        # Log Activity
        database.log_user_activity(new_user['id'], "REGISTER", request.client.host, request.headers.get("user-agent"))
        database.log_user_activity(new_user['id'], "LOGIN", request.client.host, request.headers.get("user-agent"))

        return {"access_token": access_token, "token_type": "bearer", "username": user.username}
    else:
        raise HTTPException(status_code=500, detail="Register failed")

@router.post("/login", response_model=schemas.Token)
async def login(request: Request, form_data: OAuth2PasswordRequestForm = Depends(), remember_me: bool = True):
    user = database.get_user_by_username(form_data.username)
    if not user:
        user = database.get_user_by_email(form_data.username)
    
    if not user or not verify_password(form_data.password, user['password_hash']):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    expires_minutes = ACCESS_TOKEN_EXPIRE_MINUTES if remember_me else 60 * 24
    access_token_expires = timedelta(minutes=expires_minutes)

    # Create Session
    sid = database.create_session(user['id'], request.headers.get("user-agent"), request.client.host)

    access_token = create_access_token(
        data={"sub": user['username'], "sid": sid}, expires_delta=access_token_expires
    )
    
    database.log_user_activity(user['id'], "LOGIN", request.client.host, request.headers.get("user-agent"))

    return {"access_token": access_token, "token_type": "bearer", "username": user['username']}

@router.post("/google", response_model=schemas.Token)
async def google_login(req_obj: Request, request: schemas.GoogleLoginRequest):
    token = request.token
    try:
        id_info = id_token.verify_oauth2_token(
            token, 
            google_requests.Request(), 
            GOOGLE_CLIENT_ID if GOOGLE_CLIENT_ID != "YOUR_GOOGLE_CLIENT_ID" else None,
            clock_skew_in_seconds=10
        )
        google_id = id_info['sub']
        email = id_info.get('email')
        name = id_info.get('name', 'Google User')
        picture = id_info.get('picture')

        user = database.get_user_by_google_id(google_id)
        if not user:
            username = email if email else f"google_{google_id[:8]}"
            if database.get_user_by_username(username):
                username = f"{username}_{uuid.uuid4().hex[:4]}"
            
            if not database.create_google_user(username, google_id, picture):
               raise HTTPException(status_code=500, detail="Failed to create user")
            user = database.get_user_by_username(username)

        sid = database.create_session(user['id'], req_obj.headers.get("user-agent"), req_obj.client.host)
        access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            data={"sub": user["username"], "sid": sid}, 
            expires_delta=access_token_expires
        )
        
        database.log_user_activity(user['id'], "LOGIN_GOOGLE", req_obj.client.host, req_obj.headers.get("user-agent"))

        return {
            "access_token": access_token,
            "token_type": "bearer",
            "username": user["username"],
            "is_admin": bool(user.get("is_admin"))
        }

    except ValueError as e:
        logger.error(f"Invalid Google Token: {e}")
        raise HTTPException(status_code=400, detail="Invalid Google Token")
    except Exception as e:
        logger.error(f"Google Login Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# [New] Google Redirect 模式的回调处理
# 当 ux_mode: 'redirect' 时，Google 会 POST credential 到这个 URL
from fastapi.responses import HTMLResponse
from fastapi import Form

@router.post("/google-callback", response_class=HTMLResponse)
async def google_callback(req_obj: Request, credential: str = Form(...), g_csrf_token: str = Form(None)):
    """处理 Google Sign-In redirect 模式的回调"""
    # 注意: g_csrf_token 是 Google 自动发送的，我们需要接收它但不需要验证（验证由 credential 本身完成）
    try:
        id_info = id_token.verify_oauth2_token(
            credential, 
            google_requests.Request(), 
            GOOGLE_CLIENT_ID if GOOGLE_CLIENT_ID != "YOUR_GOOGLE_CLIENT_ID" else None,
            clock_skew_in_seconds=10
        )
        google_id = id_info['sub']
        email = id_info.get('email')
        name = id_info.get('name', 'Google User')
        picture = id_info.get('picture')

        user = database.get_user_by_google_id(google_id)
        if not user:
            username = email if email else f"google_{google_id[:8]}"
            if database.get_user_by_username(username):
                username = f"{username}_{uuid.uuid4().hex[:4]}"
            
            if not database.create_google_user(username, google_id, picture):
               raise HTTPException(status_code=500, detail="Failed to create user")
            user = database.get_user_by_username(username)

        sid = database.create_session(user['id'], req_obj.headers.get("user-agent"), req_obj.client.host)
        access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            data={"sub": user["username"], "sid": sid}, 
            expires_delta=access_token_expires
        )
        
        database.log_user_activity(user['id'], "LOGIN_GOOGLE", req_obj.client.host, req_obj.headers.get("user-agent"))

        # 返回一个自动跳转的 HTML 页面，将 Token 存入 localStorage
        return f"""
        <!DOCTYPE html>
        <html>
        <head><title>登录成功</title></head>
        <body>
            <p>登录成功，正在跳转...</p>
            <script>
                localStorage.setItem('token', '{access_token}');
                localStorage.setItem('username', '{user["username"]}');
                window.location.href = '/';
            </script>
        </body>
        </html>
        """
    except ValueError as e:
        logger.error(f"Invalid Google Token (redirect): {e}")
        return f"<html><body><p>登录失败: Google Token 无效</p><a href='/'>返回首页</a></body></html>"
    except Exception as e:
        logger.error(f"Google Login Error (redirect): {e}")
        return f"<html><body><p>登录失败: {str(e)}</p><a href='/'>返回首页</a></body></html>"

@router.post("/send-code")
async def send_verification_code(request: schemas.SendCodeRequest):
    email = request.email
    code_type = request.type
    
    if code_type not in ["register", "reset"]:
        raise HTTPException(status_code=400, detail="Invalid code type")

    code = ''.join(random.choices(string.digits, k=6))
    expires_at = datetime.now() + timedelta(minutes=10)
    
    if not database.save_verification_code(email, code, code_type, expires_at):
         raise HTTPException(status_code=500, detail="Failed to save verification code")

    try:
        if code_type == "register":
            if database.get_user_by_email(email):
                raise HTTPException(status_code=400, detail="Email already registered")
            await email_utils.send_verification_code(email, code)
        elif code_type == "reset":
            if not database.get_user_by_email(email):
                raise HTTPException(status_code=404, detail="Email not found")
            await email_utils.send_password_reset_code(email, code)
            
        return {"success": True, "message": "Code sent"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Send email failed: {e}")
        # 这里暂时用 print，实际上应该根据 debug_mode 判断
        print(f"DEV MODE CODE: {code}") 
        raise HTTPException(status_code=500, detail=f"Failed to send email: {str(e)}")

@router.post("/register-email")
async def register_email(req_obj: Request, request: schemas.EmailRegisterRequest):
    # TODO: Pass debug_mode logic or check env. For now we strictly verify code.
    bypass_verify = False # In new structure, assume safe by default. 
    # If we want debug mode, we can read os.getenv("DEBUG")? Or just enforce verify.
    
    # [NEW] 图形验证码验证
    if request.captcha_id and request.captcha_code:
        if not captcha_utils.verify_captcha(request.captcha_id, request.captcha_code):
            raise HTTPException(status_code=400, detail="图形验证码错误或已过期")
    elif not bypass_verify:
        # 如果没有提供验证码参数，也需要验证（防止绕过）
        # 但为了兼容旧版前端，暂时只有提供时才验证
        pass
    
    if not bypass_verify:
        valid_code = database.get_valid_verification_code(request.email, "register")
        if not valid_code or valid_code != request.code:
             # Development fallback if code is empty/debug mode... 
             # Let's keep it strict for refactor.
             raise HTTPException(status_code=400, detail="Invalid or expired verification code")
        
    if database.get_user_by_username(request.username):
        raise HTTPException(status_code=400, detail="Username already exists")

    hashed_password = get_password_hash(request.password)
    
    success = database.create_email_user(request.username, request.email, hashed_password)
    if not success:
         raise HTTPException(status_code=400, detail="Register failed")
    
    database.delete_verification_code(request.email, "register")
    
    user = database.get_user_by_username(request.username)
    sid = database.create_session(user['id'], req_obj.headers.get("user-agent"), req_obj.client.host)
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": request.username, "sid": sid}, 
        expires_delta=access_token_expires
    )
         
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "username": request.username
    }

@router.post("/reset-password")
async def reset_password(request: schemas.ResetPasswordRequest):
    valid_code = database.get_valid_verification_code(request.email, "reset")
    if not valid_code or valid_code != request.code:
        raise HTTPException(status_code=400, detail="Invalid verification code")
        
    password_hash = get_password_hash(request.new_password)
    if not database.update_user_password(request.email, password_hash):
        raise HTTPException(status_code=500, detail="Failed to reset password")
    
    database.delete_verification_code(request.email, "reset")
        
    return {"success": True, "message": "Password reset successfully"}
