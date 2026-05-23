from typing import Any, List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_current_user
from app.crud.user import user as user_crud
from app.crud.style import style as style_crud
from app.crud.article import article as article_crud
from app.db.session import get_db
from app.models.user import User, UserProfile
from app.schemas.user import (
    UserUpdate,
    UserResponse,
    UserProfileUpdate,
    UserProfileResponse
)
from app.schemas.style import (
    StyleProfileCreate,
    StyleProfileUpdate,
    StyleProfileResponse
)
from app.schemas.article import (
    ArticleForAnalysisCreate,
    ArticleForAnalysisResponse
)

router = APIRouter()


@router.get("/profile", response_model=dict)
async def get_user_profile(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Any:
    """获取用户资料"""
    # 获取用户资料
    profile = await user_crud.get_profile(db, user_id=current_user.id)
    
    user_data = UserResponse.from_orm(current_user).dict()
    if profile:
        user_data["profile"] = UserProfileResponse.from_orm(profile).dict()
    
    return {
        "code": 200,
        "message": "获取用户资料成功",
        "data": user_data
    }


@router.put("/profile", response_model=dict)
async def update_user_profile(
    profile_in: UserProfileUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Any:
    """更新用户资料"""
    # 更新用户基本信息
    if profile_in.full_name is not None or profile_in.avatar_url is not None:
        user_update_data = {}
        if profile_in.full_name is not None:
            user_update_data["full_name"] = profile_in.full_name
        if profile_in.avatar_url is not None:
            user_update_data["avatar_url"] = profile_in.avatar_url
        user_update = UserUpdate(**user_update_data)
        await user_crud.update(db, db_obj=current_user, obj_in=user_update)
    
    # 更新用户资料
    profile = await user_crud.update_profile(
        db,
        user_id=current_user.id,
        profile_in=profile_in
    )
    
    # 获取更新后的用户信息
    updated_user = await user_crud.get(db, id=current_user.id)
    user_data = UserResponse.from_orm(updated_user).dict()
    if profile:
        user_data["profile"] = UserProfileResponse.from_orm(profile).dict()
    
    return {
        "code": 200,
        "message": "用户资料更新成功",
        "data": user_data
    }


@router.post("/style-profiles", response_model=dict)
async def create_style_profile(
    style_in: StyleProfileCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Any:
    """创建风格档案"""
    # 检查风格名称是否已存在
    existing_style = await style_crud.get_by_name(
        db,
        name=style_in.name,
        user_id=current_user.id
    )
    
    if existing_style:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="风格名称已存在"
        )
    
    # 创建风格档案
    style_profile = await style_crud.create(
        db,
        obj_in=style_in,
        user_id=current_user.id
    )
    
    return {
        "code": 200,
        "message": "风格档案创建成功",
        "data": StyleProfileResponse.from_orm(style_profile).dict()
    }


@router.get("/style-profiles", response_model=dict)
async def get_style_profiles(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量")
) -> Any:
    """获取风格档案列表"""
    # 计算偏移量
    skip = (page - 1) * page_size
    
    # 获取风格档案列表
    style_profiles = await style_crud.get_by_user(
        db,
        user_id=current_user.id,
        skip=skip,
        limit=page_size
    )
    
    # 获取总数
    total = await style_crud.count_by_user(db, user_id=current_user.id)
    
    return {
        "code": 200,
        "message": "获取风格档案列表成功",
        "data": {
            "items": [StyleProfileResponse.from_orm(style).dict() for style in style_profiles],
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": (total + page_size - 1) // page_size
        }
    }


@router.post("/articles", response_model=dict)
async def upload_article(
    article_in: ArticleForAnalysisCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Any:
    """上传历史文章"""
    # 创建文章记录
    article = await article_crud.create(
        db,
        obj_in=article_in,
        user_id=current_user.id
    )
    
    return {
        "code": 200,
        "message": "文章上传成功",
        "data": ArticleForAnalysisResponse.from_orm(article).dict()
    }


@router.get("/articles", response_model=dict)
async def get_articles(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    platform: Optional[str] = Query(None, description="平台筛选")
) -> Any:
    """获取历史文章列表"""
    # 计算偏移量
    skip = (page - 1) * page_size
    
    # 获取文章列表
    articles = await article_crud.get_by_user(
        db,
        user_id=current_user.id,
        skip=skip,
        limit=page_size,
        platform=platform
    )
    
    # 获取总数
    total = await article_crud.count_by_user(
        db,
        user_id=current_user.id,
        platform=platform
    )
    
    return {
        "code": 200,
        "message": "获取历史文章列表成功",
        "data": {
            "items": [ArticleForAnalysisResponse.from_orm(article).dict() for article in articles],
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": (total + page_size - 1) // page_size
        }
    }


@router.post("/upload-avatar", response_model=dict)
async def upload_avatar(
    avatar: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Any:
    """上传头像"""
    # 检查文件类型
    if not avatar.content_type.startswith("image/"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="只支持图片文件"
        )
    
    # 检查文件大小 (10MB)
    if avatar.size is not None and avatar.size > 10 * 1024 * 1024:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="文件大小不能超过10MB"
        )
    
    try:
        # 保存文件
        import os
        from datetime import datetime
        
        # 创建上传目录
        upload_dir = "./uploads/avatars"
        os.makedirs(upload_dir, exist_ok=True)
        
        # 生成文件名
        file_ext = avatar.filename.split(".")[-1]
        filename = f"{current_user.id}_{datetime.now().strftime('%Y%m%d%H%M%S')}.{file_ext}"
        file_path = os.path.join(upload_dir, filename)
        
        # 保存文件
        with open(file_path, "wb") as buffer:
            content = await avatar.read()
            buffer.write(content)
        
        # 更新用户头像URL
        avatar_url = f"/uploads/avatars/{filename}"
        user_update = UserUpdate(avatar_url=avatar_url)
        await user_crud.update(db, db_obj=current_user, obj_in=user_update)
        
        return {
            "code": 200,
            "message": "头像上传成功",
            "data": {
                "avatar_url": avatar_url
            }
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"头像上传失败: {str(e)}"
        )