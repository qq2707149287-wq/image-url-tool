import os
import logging
import uuid
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
import bcrypt
from jose import JWTError, jwt
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests

from .. import database
from .. import schemas
from .. import email_utils
from .. import captcha_utils  # 验证码工具
from ..config import (
    SECRET_KEY, 
    JWT_ALGORITHM as ALGORITHM, 
    ACCESS_TOKEN_EXPIRE_MINUTES,
    GOOGLE_CLIENT_ID,
    BCRYPT_ROUNDS
)

# 设置日志记录器
logger = logging.getLogger(__name__)

# ==================== 安全工具函数 ====================
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login", auto_error=False)

router = APIRouter(prefix="/auth", tags=["auth"])

def verify_password(plain_password, hashed_password):
    try:
        # bcrypt 需要 bytes 类型参数
        if isinstance(hashed_password, str):
            hashed_password = hashed_password.encode('utf-8')
        if isinstance(plain_password, str):
            plain_password = plain_password.encode('utf-8')
            
        return bcrypt.checkpw(plain_password, hashed_password)
    except Exception as e:
        logger.error(f"❌ [Auth] 密码验证出错: {e}")
        return False

def get_password_hash(password):
    if isinstance(password, str):
        password = password.encode('utf-8')
    salt = bcrypt.gensalt(rounds=BCRYPT_ROUNDS)
    return bcrypt.hashpw(password, salt).decode('utf-8')

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
    获取当前用户（如果 token 有效），否则返回 None。
    """
    if not token:
        return None
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            return None
            
        # 如果存在 Session ID，验证其有效性
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
    强制认证：如果用户未登录则抛出 401 异常。
    """
    user = await get_current_user_optional(token)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user

# ==================== 路由接口 ====================

@router.get("/config")
async def get_auth_config():
    """返回公开认证配置"""
    return {
        "google_client_id": GOOGLE_CLIENT_ID if GOOGLE_CLIENT_ID else None
    }

@router.post("/register", response_model=schemas.Token)
async def register(request: Request, user: schemas.UserCreate):
    """
    用户注册接口
    
    功能:
    - 验证图形验证码 (captcha)
    - 验证用户名唯一性
    - 创建新用户
    - 自动登录并返回 Access Token
    """
    # 图形验证码验证（即使是简单注册也要防机器人喵~）
    from ..global_state import SYSTEM_SETTINGS
    
    bypass = False
    if SYSTEM_SETTINGS.get("debug_mode") and user.captcha_code == "abcd":
        bypass = True
        logger.info(f"🔧 [Debug] Skipping Captcha for user: {user.username}")
        
    if not bypass:
        if user.captcha_id and user.captcha_code:
            if not captcha_utils.verify_captcha(user.captcha_id, user.captcha_code):
                raise HTTPException(status_code=400, detail="图形验证码错误或已过期")
    
    if database.get_user_by_username(user.username):
        raise HTTPException(status_code=400, detail="用户名已被注册")
    
    hashed_password = get_password_hash(user.password)
    if not database.create_user(user.username, hashed_password):
         raise HTTPException(status_code=500, detail="注册失败")
    
    # 自动登录
    new_user = database.get_user_by_username(user.username)
    if new_user:
        sid = database.create_session(new_user['id'], request.headers.get("user-agent"), request.client.host)
        access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            data={"sub": user.username, "sid": sid}, expires_delta=access_token_expires
        )
        # 记录用户活动
        database.log_user_activity(new_user['id'], "REGISTER", request.client.host, request.headers.get("user-agent"))
        database.log_user_activity(new_user['id'], "LOGIN", request.client.host, request.headers.get("user-agent"))

        return {
            "access_token": access_token, 
            "token_type": "bearer", 
            "username": user.username,
            # 新注册用户默认为非VIP，非管理员
            "is_admin": False,
            "is_vip": False 
        }
    else:
        raise HTTPException(status_code=500, detail="Register failed")

@router.post("/login", response_model=schemas.Token)
async def login(request: Request, form_data: OAuth2PasswordRequestForm = Depends(), remember_me: bool = True):
    """
    用户登录接口 (OAuth2 兼容)
    
    Args:
        form_data: 包含 username 和 password
        remember_me: 是否记住登录 (默认 30 天，否则 24 小时)
        
    Returns:
        JSON: 包含 access_token 和用户信息
    """
    try:
        logger.info(f"👉 [Auth] 尝试登录: {form_data.username}")
        user = database.get_user_by_username(form_data.username)
        if not user:
            user = database.get_user_by_email(form_data.username)
        
        # 详细的密码验证日志
        verification_result = False
        if user:
            try:
                verification_result = verify_password(form_data.password, user['password_hash'])
            except Exception as ve:
                logger.error(f"❌ [Auth] verify_password 内部报错: {ve}")
                verification_result = False
        
        if not user or not verification_result:
            logger.warning(f"❌ [Auth] 登录失败: 用户名或密码错误 (User found: {bool(user)})")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect username or password",
                headers={"WWW-Authenticate": "Bearer"},
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ [Auth] 登录接口发生未知异常: {e}")
        import traceback
        logger.error(traceback.format_exc())
        # 返回 400 而不是 500，避免前端 SyntaxError，同时给出错误提示
        raise HTTPException(
            status_code=400,
            detail=f"Login Error: {str(e)}"
        )
    
    expires_minutes = ACCESS_TOKEN_EXPIRE_MINUTES if remember_me else 60 * 24
    access_token_expires = timedelta(minutes=expires_minutes)

    # 创建会话
    sid = database.create_session(user['id'], request.headers.get("user-agent"), request.client.host)

    access_token = create_access_token(
        data={"sub": user['username'], "sid": sid}, expires_delta=access_token_expires
    )
    
    database.log_user_activity(user['id'], "LOGIN", request.client.host, request.headers.get("user-agent"))

    return {
        "access_token": access_token, 
        "token_type": "bearer", 
        "username": user['username'],
        "is_admin": bool(user.get("is_admin")),
        "is_vip": bool(user.get("is_vip"))
    }

@router.post("/google", response_model=schemas.Token)
async def google_login(req_obj: Request, request: schemas.GoogleLoginRequest):
    """
    Google 登录接口 (Popup 模式)
    
    接收前端 Google Sign-In 返回的 id_token，验证并登录/注册用户。
    如果用户不存在，将自动创建新账号。
    """
    token = request.token
    try:
        id_info = id_token.verify_oauth2_token(
            token, 
            google_requests.Request(), 
            GOOGLE_CLIENT_ID if GOOGLE_CLIENT_ID else None,
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
    """
    Google 登录回调接口 (Redirect 模式)
    
    当配置 ux_mode: 'redirect' 时，Google 会 POST credential 到此接口。
    验证成功后返回一个自动跳转的 HTML 页面，将 Token 写入 localStorage。
    """
    # 注意: g_csrf_token 是 Google 自动发送的，我们需要接收它但不需要验证（验证由 credential 本身完成）
    try:
        id_info = id_token.verify_oauth2_token(
            credential, 
            google_requests.Request(), 
            GOOGLE_CLIENT_ID if GOOGLE_CLIENT_ID else None,
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
    """
    发送邮箱验证码 API
    
    支持两种类型:
    - register: 注册验证码 (检查邮箱是否已注册)
    - reset: 重置密码验证码 (检查邮箱是否存在)
    """
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
    """
    邮箱注册接口
    
    包含双重验证:
    1. 图形验证码 (Captcha)
    2. 邮箱验证码 (Email Code)
    """
    # 图形验证码验证
    from ..global_state import SYSTEM_SETTINGS
    
    bypass = False
    if SYSTEM_SETTINGS.get("debug_mode") and request.captcha_code == "abcd":
        bypass = True
        logger.info(f"🔧 [Debug] Skipping Captcha for email register: {request.username}")
        
    if not bypass:
        if request.captcha_id and request.captcha_code:
            if not captcha_utils.verify_captcha(request.captcha_id, request.captcha_code):
                raise HTTPException(status_code=400, detail="图形验证码错误或已过期")
    
    # 邮件验证码验证
    valid_code = database.get_valid_verification_code(request.email, "register")
    if not valid_code or valid_code != request.code:
         raise HTTPException(status_code=400, detail="邮件验证码无效或已过期")
        
    if database.get_user_by_username(request.username):
        raise HTTPException(status_code=400, detail="用户名已被注册")

    hashed_password = get_password_hash(request.password)
    
    success = database.create_email_user(request.username, request.email, hashed_password)
    if not success:
         raise HTTPException(status_code=400, detail="注册失败，可能是邮箱已被使用")
    
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
    """
    重置密码接口
    
    验证邮箱验证码并设置新密码
    """
    valid_code = database.get_valid_verification_code(request.email, "reset")
    if not valid_code or valid_code != request.code:
        raise HTTPException(status_code=400, detail="Invalid verification code")
        
    password_hash = get_password_hash(request.new_password)
    if not database.update_user_password(request.email, password_hash):
        raise HTTPException(status_code=500, detail="Failed to reset password")
    
    database.delete_verification_code(request.email, "reset")
        
    return {"success": True, "message": "Password reset successfully"}

# [VIP] 直链签名接口
from .. import security

@router.post("/sign-url")
async def sign_url(
    req: schemas.SignUrlRequest, 
    user=Depends(get_current_user)
):
    """
    VIP 专属：生成带签名的直链
    """
    if not user.get("is_vip"):
        raise HTTPException(status_code=403, detail="此功能仅限 VIP 用户使用")

    # 默认有效期 1 年 (VIP 特权)
    expires = int((datetime.utcnow() + timedelta(days=365)).timestamp())
    sig = security.generate_url_signature(req.object_name, expires)
    
    signed_url = f"/mycloud/{req.object_name}?token={sig}&expires={expires}"
    
    return {"signed_url": signed_url}
