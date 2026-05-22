from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.models.style import StyleProfile
from app.schemas.style import (
    StyleProfileCreate,
    StyleProfileUpdate,
    StyleProfileResponse,
    StyleAnalysisRequest,
    StyleAnalysisResponse
)
from app.crud.style import style as style_crud
from app.services.style_service import style_service

router = APIRouter()


@router.get("", response_model=List[StyleProfileResponse])
async def get_styles(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    skip: int = 0,
    limit: int = 100
):
    """获取用户的风格档案列表"""
    styles = await style_crud.get_by_user(
        db=db,
        user_id=current_user.id,
        skip=skip,
        limit=limit
    )
    return styles


@router.get("/{style_id}", response_model=StyleProfileResponse)
async def get_style(
    style_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取风格档案详情"""
    style = await style_crud.get(db=db, id=style_id)
    if not style:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="风格档案不存在"
        )
    
    # 检查权限
    if style.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="没有权限访问此风格档案"
        )
    
    return style


@router.post("", response_model=StyleProfileResponse)
async def create_style(
    style_in: StyleProfileCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """创建风格档案"""
    style = await style_crud.create(
        db=db,
        obj_in=style_in,
        user_id=current_user.id
    )
    return style


@router.put("/{style_id}", response_model=StyleProfileResponse)
async def update_style(
    style_id: int,
    style_in: StyleProfileUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """更新风格档案"""
    style = await style_crud.get(db=db, id=style_id)
    if not style:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="风格档案不存在"
        )
    
    # 检查权限
    if style.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="没有权限修改此风格档案"
        )
    
    style = await style_crud.update(
        db=db,
        db_obj=style,
        obj_in=style_in
    )
    return style


@router.delete("/{style_id}", response_model=StyleProfileResponse)
async def delete_style(
    style_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """删除风格档案"""
    style = await style_crud.get(db=db, id=style_id)
    if not style:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="风格档案不存在"
        )
    
    # 检查权限
    if style.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="没有权限删除此风格档案"
        )
    
    style = await style_crud.remove(db=db, id=style_id)
    return style


@router.post("/analyze", response_model=StyleAnalysisResponse)
async def analyze_article_style(
    analysis_in: StyleAnalysisRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """分析文章风格"""
    try:
        result = await style_service.analyze_article_style(
            content=analysis_in.content,
            title=analysis_in.title
        )
        return result
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"风格分析失败: {str(e)}"
        )


@router.get("/suggestions")
async def get_style_suggestions(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取风格建议"""
    # 基于用户历史创作获取风格建议
    suggestions = await style_service.get_style_suggestions(
        user_id=current_user.id,
        db=db
    )
    return {"suggestions": suggestions}


@router.post("/apply")
async def apply_style_to_content(
    request: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """将风格应用到内容"""
    style_id = request.get("style_id")
    content = request.get("content")
    
    if not style_id or not content:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="缺少必要参数"
        )
    
    # 获取风格档案
    style = await style_crud.get(db=db, id=style_id)
    if not style:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="风格档案不存在"
        )
    
    # 检查权限
    if style.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="没有权限使用此风格档案"
        )
    
    try:
        result = await style_service.apply_style(
            content=content,
            style=style
        )
        return result
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"风格应用失败: {str(e)}"
        )