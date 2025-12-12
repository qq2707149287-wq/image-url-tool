import logging
import uuid
import random
import string
from typing import List, Optional
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, Response, Form
from fastapi.responses import JSONResponse

from .. import database
from .. import schemas
from .. import email_utils
from ..routers.auth import get_current_user, get_current_user_optional, verify_password, get_password_hash, create_access_token

# Setup Logger
logger = logging.getLogger(__name__)

router = APIRouter()

# ==================== User Info & Management ====================

@router.get("/auth/me")
async def read_users_me(current_user: dict = Depends(get_current_user)):
    return {
        "id": current_user["id"],
        "username": current_user["username"],
        "is_admin": current_user.get("is_admin", 0),
        "avatar": current_user.get("avatar"),
        "created_at": current_user["created_at"],
        "is_vip": bool(current_user.get("is_vip")),
        "vip_expiry": current_user.get("vip_expiry")
    }

@router.post("/auth/change-password")
async def change_password(
    request: schemas.ChangePasswordRequest,
    current_user: dict = Depends(get_current_user)
):
    """已登录状态下修改密码"""
    if not verify_password(request.old_password, current_user['password_hash']):
        raise HTTPException(status_code=400, detail="旧密码不正确")
    
    password_hash = get_password_hash(request.new_password)
    # 需要通过 email 或 username 更新
    if current_user.get('email'):
        success = database.update_user_password(current_user['email'], password_hash)
    else:
        success = database.update_user_password_by_id(current_user['id'], password_hash)
    
    if not success:
        raise HTTPException(status_code=500, detail="修改密码失败")
    
    return {"success": True, "message": "密码修改成功"}

@router.post("/auth/change-username")
async def change_username(
    request: schemas.ChangeUsernameRequest,
    current_user: dict = Depends(get_current_user)
):
    """修改用户名"""
    new_username = request.new_username.strip()
    
    if len(new_username) < 2 or len(new_username) > 20:
        raise HTTPException(status_code=400, detail="用户名长度需在2-20个字符之间")
    
    if database.get_user_by_username(new_username):
        raise HTTPException(status_code=400, detail="用户名已被占用")
    
    success = database.update_username(current_user['id'], new_username)
    if not success:
        raise HTTPException(status_code=500, detail="修改用户名失败")
    
    # 返回新的 Token
    from ..routers.auth import ACCESS_TOKEN_EXPIRE_MINUTES # Import constant? Or duplicated.
    # It's better to duplicate or move constants to config.
    # For now, duplicate logic or import.
    # ACCESS_TOKEN_EXPIRE_MINUTES is in auth.py but is it public? Yes.
    
    access_token_expires = timedelta(minutes=60 * 24 * 30) # Hardcoded fallback or import
    access_token = create_access_token(
        data={"sub": new_username}, 
        expires_delta=access_token_expires
    )
    
    return {
        "success": True,
        "access_token": access_token,
        "username": new_username
    }

@router.delete("/auth/delete-account")
async def delete_account(current_user: dict = Depends(get_current_user)):
    """注销账号 - 删除用户及其所有数据"""
    user_id = current_user['id']
    database.delete_user_history(user_id)
    success = database.delete_user(user_id)
    if not success:
        raise HTTPException(status_code=500, detail="账号注销失败")
    return {"success": True, "message": "账号已注销"}

@router.get("/auth/user-stats")
async def get_user_stats(current_user: dict = Depends(get_current_user)):
    """获取用户统计信息"""
    return database.get_user_stats(current_user['id'])

@router.get("/auth/logs", response_model=List[schemas.UserLog])
async def get_logs(current_user: dict = Depends(get_current_user)):
    """获取登录日志"""
    return database.get_user_logs(current_user['id'])

# ==================== Sessions ====================

@router.get("/auth/sessions")
async def get_active_sessions(current_user: dict = Depends(get_current_user)):
    """获取当前所有活跃会话"""
    return database.get_active_sessions(current_user['id'])

@router.delete("/auth/sessions/{session_id}")
async def revoke_session(session_id: str, current_user: dict = Depends(get_current_user)):
    """注销指定会话 (踢下线)"""
    sessions = database.get_active_sessions(current_user['id'])
    if not any(s['session_id'] == session_id for s in sessions):
        raise HTTPException(status_code=404, detail="Session not found")
        
    success = database.revoke_session(session_id, current_user['id'])
    if not success:
        raise HTTPException(status_code=500, detail="Failed to revoke session")
        
    return {"success": True}

# ==================== VIP ====================

@router.post("/auth/vip/activate")
async def activate_vip(
    req: schemas.VIPCodeRequest,
    current_user: dict = Depends(get_current_user)
):
    """激活 VIP"""
    code = req.code.strip()
    if not code:
        raise HTTPException(status_code=400, detail="激活码不能为空")
        
    res = database.activate_vip(current_user['id'], code)
    if not res["success"]:
        raise HTTPException(status_code=400, detail=res.get("error"))
        
    return {
        "success": True, 
        "message": "VIP 激活成功", 
        "expiry": res["expiry"]
    }

@router.post("/admin/vip/generate")
async def generate_vip_code_endpoint(
    days: int = Form(...),
    count: int = Form(1),
    current_user: dict = Depends(get_current_user)
):
    """(管理员) 生成 VIP 激活码"""
    if not current_user.get("is_admin"):
        raise HTTPException(status_code=403, detail="需要管理员权限")
        
    codes = []
    for _ in range(count):
        raw_code = uuid.uuid4().hex[:16].upper()
        formatted_code = f"{raw_code[:4]}-{raw_code[4:8]}-{raw_code[8:12]}-{raw_code[12:]}"
        if database.create_vip_code(formatted_code, days):
            codes.append(formatted_code)
            
    return {"success": True, "codes": codes}

# ==================== History ====================

@router.get("/history")
def get_history(
    request: Request,
    response: Response,
    page: int = 1,
    page_size: int = 20,
    keyword: str = "",
    view_mode: str = "private",
    only_mine: bool = False,
    current_user: Optional[dict] = Depends(get_current_user_optional)
) -> dict:
    """获取历史记录列表"""
    user_id = current_user['id'] if current_user else None
    is_admin = current_user.get('is_admin', False) if current_user else False

    final_view_mode = view_mode
    if not user_id:
        final_view_mode = "shared"
    
    return database.get_history_list(page, page_size, keyword, device_id=None, user_id=user_id, is_admin=is_admin, view_mode=final_view_mode, only_mine=only_mine)

@router.post("/history/delete")
def delete_history(
    request: Request, 
    response: Response, 
    req: schemas.DeleteRequest,
    current_user: Optional[dict] = Depends(get_current_user_optional)
) -> dict:
    """批量删除历史记录"""
    user_id = current_user['id'] if current_user else None
    is_admin = current_user.get('is_admin', False) if current_user else False

    if not user_id:
        return {"success": False, "error": "Login required explicitly for deletion"}
        
    return database.delete_history_items(req.ids, device_id=None, user_id=user_id, is_admin=is_admin)

@router.post("/history/clear")
def clear_history(
    request: Request, 
    response: Response,
    view_mode: str = "private",
    current_user: Optional[dict] = Depends(get_current_user_optional)
) -> dict:
    """清空历史记录"""
    user_id = current_user['id'] if current_user else None
    is_admin = current_user.get('is_admin', False) if current_user else False
    
    if not user_id:
         return {"success": False, "error": "Login required"}
         
    return database.clear_all_history(device_id=None, view_mode=view_mode, user_id=user_id, is_admin=is_admin)

@router.post("/history/rename")
def rename_history(
    request: Request, 
    response: Response, 
    body: schemas.RenameRequest,
    current_user: Optional[dict] = Depends(get_current_user_optional)
) -> JSONResponse:
    """重命名历史记录"""
    user_id = current_user['id'] if current_user else None
    is_admin = current_user.get('is_admin', False) if current_user else False

    if not user_id:
        return JSONResponse({"success": False, "error": "Login required"})

    try:
        res = database.rename_history_item(body.id, body.filename, device_id=None, user_id=user_id, is_admin=is_admin)

        if res["success"]:
            logger.info(f"✅ 重命名成功: ID={body.id} -> {body.filename}")
            return JSONResponse({"success": True})
        else:
            logger.warning(f"❌ 重命名失败: {res.get('error')} (ID: {body.id})")
            return JSONResponse({"success": False, "error": res.get("error")})
    except Exception as e:
        logger.error(f"❌ 重命名失败: {e}", exc_info=True)
        return JSONResponse({"success": False, "error": "服务器内部错误"})
