# -*- coding: utf-8 -*-
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
    captcha_id: str = ""      # 可选：图形验证码ID
    captcha_code: str = ""    # 可选：用户输入的验证码

class UserLogin(BaseModel):
    username: str
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str
    username: str
    is_admin: bool = False # 方便前端
    is_vip: bool = False   # 方便前端判断 VIP 权限

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
    created_at: str | None = None 

class VIPCodeRequest(BaseModel):
    code: str

class GenerateVipCodesRequest(BaseModel):
    count: int = 10
    days: int = 30

class SignUrlRequest(BaseModel):
    object_name: str

class ResolveReport(BaseModel):
    notes: str = None

class AdminDeleteImage(BaseModel):
    hash: str
    reason: str = "Admin Deleted"

class BatchResolveReports(BaseModel):
    """批量处理举报的请求体"""
    ids: List[int]
    notes: str = None

class BatchDeleteImages(BaseModel):
    """批量删除图片的请求体"""
    hashes: List[str]

class AdminPromoteUser(BaseModel):
    is_admin: bool

class AdminResetPassword(BaseModel):
    new_password: str

class AdminBanUser(BaseModel):
    reason: str = "Violation of terms"

class BatchDeleteUsers(BaseModel):
    """批量删除用户的请求体"""
    user_ids: List[int]
