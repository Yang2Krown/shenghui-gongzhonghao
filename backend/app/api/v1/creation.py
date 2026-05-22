from typing import Any, List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_current_user
from app.crud.creation import creation as creation_crud
from app.db.session import get_db
from app.models.user import User
from app.models.creation import ContentCreation
from app.schemas.creation import (
    ContentCreationCreate,
    ContentCreationUpdate,
    ContentCreationResponse,
    ContentCreationListResponse,
    ContentGenerationRequest,
    ContentGenerationResponse
)

router = APIRouter()


@router.post("", response_model=dict)
async def create_creation(
    creation_in: ContentCreationCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Any:
    """创建新创作"""
    # 创建创作记录
    creation = await creation_crud.create(
        db,
        obj_in=creation_in,
        user_id=current_user.id
    )
    
    return {
        "code": 200,
        "message": "创作创建成功",
        "data": ContentCreationResponse.from_orm(creation).dict()
    }


@router.get("", response_model=dict)
async def get_creations(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    status: Optional[str] = Query(None, description="状态筛选"),
    topic_id: Optional[int] = Query(None, description="选题ID筛选")
) -> Any:
    """获取创作列表"""
    # 计算偏移量
    skip = (page - 1) * page_size
    
    # 获取创作列表
    creations = await creation_crud.get_by_user(
        db,
        user_id=current_user.id,
        skip=skip,
        limit=page_size,
        status=status,
        topic_id=topic_id
    )
    
    # 获取总数
    total = await creation_crud.count_by_user(
        db,
        user_id=current_user.id,
        status=status,
        topic_id=topic_id
    )
    
    return {
        "code": 200,
        "message": "获取创作列表成功",
        "data": {
            "items": [ContentCreationResponse.from_orm(creation).dict() for creation in creations],
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": (total + page_size - 1) // page_size
        }
    }


@router.get("/{creation_id}", response_model=dict)
async def get_creation(
    creation_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Any:
    """获取创作详情"""
    creation = await creation_crud.get(db, id=creation_id)
    if not creation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="创作不存在"
        )
    
    # 检查是否是当前用户的创作
    if creation.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权访问他人创作"
        )
    
    return {
        "code": 200,
        "message": "获取创作详情成功",
        "data": ContentCreationResponse.from_orm(creation).dict()
    }


@router.put("/{creation_id}", response_model=dict)
async def update_creation(
    creation_id: int,
    creation_in: ContentCreationUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Any:
    """更新创作内容"""
    # 获取创作记录
    creation = await creation_crud.get(db, id=creation_id)
    if not creation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="创作不存在"
        )
    
    # 检查是否是当前用户的创作
    if creation.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权修改他人创作"
        )
    
    # 更新创作
    updated_creation = await creation_crud.update(
        db,
        db_obj=creation,
        obj_in=creation_in
    )
    
    return {
        "code": 200,
        "message": "创作更新成功",
        "data": ContentCreationResponse.from_orm(updated_creation).dict()
    }


@router.delete("/{creation_id}", response_model=dict)
async def delete_creation(
    creation_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Any:
    """删除创作"""
    # 获取创作记录
    creation = await creation_crud.get(db, id=creation_id)
    if not creation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="创作不存在"
        )
    
    # 检查是否是当前用户的创作
    if creation.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权删除他人创作"
        )
    
    # 删除创作
    await creation_crud.remove(db, id=creation_id)
    
    return {
        "code": 200,
        "message": "创作删除成功",
        "data": None
    }


@router.post("/{creation_id}/publish", response_model=dict)
async def publish_creation(
    creation_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Any:
    """发布创作"""
    # 获取创作记录
    creation = await creation_crud.get(db, id=creation_id)
    if not creation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="创作不存在"
        )
    
    # 检查是否是当前用户的创作
    if creation.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权发布他人创作"
        )
    
    # 检查状态
    if creation.status == "published":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="创作已发布"
        )
    
    # 发布创作
    published_creation = await creation_crud.publish(db, db_obj=creation)
    
    return {
        "code": 200,
        "message": "创作发布成功",
        "data": ContentCreationResponse.from_orm(published_creation).dict()
    }


@router.post("/generate", response_model=dict)
async def generate_content(
    request: ContentGenerationRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Any:
    """AI生成内容"""
    try:
        # 调用AI服务生成内容
        from app.services.ai_service import ai_service
        from app.services.style_service import style_service
        
        # 获取用户风格
        style_profile = None
        if request.style_profile_id:
            style_profile = await style_service.get_style_profile(
                db,
                style_id=request.style_profile_id,
                user_id=current_user.id
            )
        
        # 生成内容
        generated_content = await ai_service.generate_content(
            topic_title=request.topic_title,
            topic_summary=request.topic_summary,
            style_profile=style_profile,
            custom_prompt=request.custom_prompt,
            content_type=request.content_type
        )
        
        # 创建创作记录
        creation_data = ContentCreationCreate(
            topic_id=request.topic_id,
            title=request.topic_title,
            content=generated_content,
            status="draft"
        )
        
        creation = await creation_crud.create(
            db,
            obj_in=creation_data,
            user_id=current_user.id
        )
        
        return {
            "code": 200,
            "message": "内容生成成功",
            "data": {
                "creation": ContentCreationResponse.from_orm(creation).dict(),
                "generated_content": generated_content
            }
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"内容生成失败: {str(e)}"
        )