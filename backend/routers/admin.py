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
    return database.get_abuse_reports(page, page_size, status)

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
