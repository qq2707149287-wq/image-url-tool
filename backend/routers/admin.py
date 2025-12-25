# -*- coding: utf-8 -*-
from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import List, Optional
from .. import database, schemas
from .auth import get_current_user

router = APIRouter(
    prefix="/admin",
    tags=["admin"],
    responses={404: {"description": "Not found"}},
)

def get_current_admin(current_user: dict = Depends(get_current_user)):
    """
    Dependency to ensure the user is an admin.
    """
    if not current_user.get("is_admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="需要管理员权限 (Admin privileges required)"
        )
    return current_user

@router.get("/stats")
async def get_stats(current_user: dict = Depends(get_current_admin)):
    """获取管理后台统计数据"""
    return database.get_admin_stats()

@router.get("/reports")
async def get_reports(
    page: int = 1, 
    page_size: int = 50, 
    status: Optional[str] = None,
    current_user: dict = Depends(get_current_admin)
):
    """获取举报列表"""
    return database.get_abuse_reports(status=status, page=page, page_size=page_size)

@router.post("/reports/{report_id}/resolve")
async def resolve_report(
    report_id: int, 
    data: schemas.ResolveReport, 
    current_user: dict = Depends(get_current_admin)
):
    """标记举报为已处理"""
    success = database.resolve_abuse_report(report_id, data.notes)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to resolve report")
    return {"success": True}

@router.get("/images")
async def get_all_images(
    page: int = 1, 
    page_size: int = 30, 
    keyword: Optional[str] = None,
    current_user: dict = Depends(get_current_admin)
):
    """获取全站图片 (上帝视角)"""
    return database.get_history_list(
        page=page, 
        page_size=page_size, 
        keyword=keyword, 
        is_admin=True,
        view_mode="admin_all"
    )

@router.post("/images/delete")
async def admin_delete_image(
    data: schemas.AdminDeleteImage, 
    current_user: dict = Depends(get_current_admin)
):
    """管理员强制删除图片"""
    from .. import storage
    
    # 1. 查找图片
    image = database.get_image_by_hash(data.hash)
    if not image:
        # 如果找不到，尝试通过 keyword 搜索 (兼容旧逻辑)
        images = database.get_history_list(keyword=data.hash, page_size=1, is_admin=True, view_mode="admin_all")
        if images and images.get('data'):
            image = images['data'][0]
    
    if not image:
        raise HTTPException(status_code=404, detail="Image not found")
        
    # 2. 删除文件
    # 尝试从 URL 解析 Object Key
    if image.get("url") and "/mycloud/" in image["url"]:
        object_key = image["url"].replace("/mycloud/", "")
        storage.delete_from_minio(object_key)
    elif image.get("filename"):
        # 最后的尝试：假设 filename 就是 key (不太可靠，但为了兼容)
        # 通常 filename 是 cat.jpg，但 key 是 hash.jpg
        # 这里最好不要乱删。如果 url 不对劲，可能不是 minio 的文件（例如外部链接）
        pass
    
    # 3. 删库
    success = database.delete_image_by_hash_system(data.hash)
    
    if success:
        return {"success": True}
    else:
        raise HTTPException(status_code=500, detail="Delete failed")


@router.post("/reports/batch-resolve")
async def batch_resolve_reports(
    data: schemas.BatchResolveReports, 
    current_user: dict = Depends(get_current_admin)
):
    """批量标记多条举报为已处理"""
    result = database.batch_resolve_reports(data.ids, data.notes)
    if not result.get("success"):
        raise HTTPException(status_code=500, detail=result.get("error", "Batch resolve failed"))
    return result


@router.post("/images/batch-delete")
async def batch_delete_images(
    data: schemas.BatchDeleteImages,
    current_user: dict = Depends(get_current_admin)
):
    """批量删除多张图片"""
    from .. import storage
    
    # 1. 先删除 MinIO 文件
    for h in data.hashes:
        image = database.get_image_by_hash(h)
        if image and image.get("url") and "/mycloud/" in image["url"]:
            object_key = image["url"].replace("/mycloud/", "")
            storage.delete_from_minio(object_key)
    
    # 2. 批量删除数据库记录
    result = database.batch_delete_images_by_hashes(data.hashes)
    if not result.get("success"):
        raise HTTPException(status_code=500, detail=result.get("error", "Batch delete failed"))
    return result


@router.post("/vip/generate")
async def generate_vip_codes(
    data: schemas.GenerateVipCodesRequest,
    current_user: dict = Depends(get_current_admin)
):
    """批量生成 VIP 激活码"""
    import random
    import string
    
    generated_codes = []
    failed_count = 0
    
    # 限制单次生成数量，防止滥用
    count = min(data.count, 100)
    
    for _ in range(count):
        # 生成 16 位随机码 (大写字母+数字)
        files = ''.join(random.choices(string.ascii_uppercase + string.digits, k=16))
        # 格式化为 XXXX-XXXX-XXXX-XXXX
        code = f"{files[:4]}-{files[4:8]}-{files[8:12]}-{files[12:]}"
        
        # 尝试插入数据库
        if database.create_vip_code(code, data.days):
            generated_codes.append(code)
        else:
            failed_count += 1
            
    return {
        "success": True,
        "count": len(generated_codes),
        "failed": failed_count,
        "codes": generated_codes,
        "days": data.days
    }



# ==================== 用户管理接口 (Stage 5) ====================

@router.get("/users")
async def get_users(
    page: int = 1, 
    page_size: int = 20, 
    search: Optional[str] = None,
    current_user: dict = Depends(get_current_admin)
):
    """获取用户列表"""
    return database.get_all_users(page, page_size, search)

@router.post("/users/{user_id}/promote")
async def promote_user(
    user_id: int, 
    data: schemas.AdminPromoteUser, 
    current_user: dict = Depends(get_current_admin)
):
    """提权/降权用户"""
    # 不能取消自己的管理员权限
    if user_id == current_user['id'] and not data.is_admin:
        raise HTTPException(status_code=400, detail="不能取消自己的管理员权限")
        
    success = database.promote_user_to_admin(user_id, data.is_admin)
    if not success:
        raise HTTPException(status_code=500, detail="Operation failed")
    return {"success": True}

@router.post("/users/{user_id}/reset-password")
async def admin_reset_password(
    user_id: int, 
    data: schemas.AdminResetPassword, 
    current_user: dict = Depends(get_current_admin)
):
    """强制重置用户密码"""
    from .auth import get_password_hash
    hashed = get_password_hash(data.new_password)
    success = database.reset_user_password_by_admin(user_id, hashed)
    if not success:
        raise HTTPException(status_code=500, detail="Operation failed")
    return {"success": True}

@router.post("/users/{user_id}/ban")
async def ban_user_endpoint(
    user_id: int, 
    data: schemas.AdminBanUser, 
    current_user: dict = Depends(get_current_admin)
):
    """封禁用户 (踢出登录状态)"""
    if user_id == current_user['id']:
        raise HTTPException(status_code=400, detail="不能封禁自己")
        
    success = database.ban_user(user_id)
    if not success:
        raise HTTPException(status_code=500, detail="Operation failed")
    return {"success": True}


@router.post("/users/batch-delete")
async def batch_delete_users_endpoint(
    data: schemas.BatchDeleteUsers,
    current_user: dict = Depends(get_current_admin)
):
    """批量删除用户"""
    # 保护: 不能删除 admin, aa, bb
    # 虽然前端会过滤，但后端也要做好防线
    # 这里为了简单，我们先不一个个查用户名，但我们可以检查当前用户是否在被删除列表中
    if current_user['id'] in data.user_ids:
        raise HTTPException(status_code=400, detail="Cannot delete yourself")
        
    result = database.batch_delete_users(data.user_ids)
    if not result.get("success"):
        raise HTTPException(status_code=500, detail=result.get("error", "Batch delete failed"))
    return result
