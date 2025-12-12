from pydantic import BaseModel
from typing import List


class DeleteRequest(BaseModel):
    ids: List[int]


class RenameRequest(BaseModel):
    id: int
    filename: str


class ValidateRequest(BaseModel):
    url: str


class UserCreate(BaseModel):
    username: str
    password: str


class UserLogin(BaseModel):
    username: str
    password: str


class Token(BaseModel):
    access_token: str
    token_type: str
    username: str
    is_admin: bool = False # 方便前端

class GoogleLoginRequest(BaseModel):
    token: str

class SendCodeRequest(BaseModel):
    email: str
    type: str # "register" or "reset"

class EmailRegisterRequest(BaseModel):
    username: str
    password: str
    email: str
    code: str
    captcha_id: str = ""      # 验证码ID
    captcha_code: str = ""    # 用户输入的验证码

class ResetPasswordRequest(BaseModel):
    email: str
    code: str
    new_password: str

class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str

class ChangeUsernameRequest(BaseModel):
    new_username: str

class UserLog(BaseModel):
    action: str
    ip_address: str | None = None
    user_agent: str | None = None
    created_at: str | None = None # SQLite returns string often, or convert using Pydantic serialization if datetime object
    # Pydantic v2 handles datetime, but SQLite driver might return str or datetime.
    # Safe to use str for now or datetime if we ensure it.


class VIPCodeRequest(BaseModel):
    code: str

