from typing import Any, List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.ai import (
    StyleAnalysisRequest,
    StyleAnalysisResponse,
    ContentGenerationRequest,
    ContentGenerationResponse,
    ContentSummaryRequest,
    ContentSummaryResponse,
    TitleSuggestionRequest,
    TitleSuggestionResponse
)

router = APIRouter()


@router.post("/analyze-style", response_model=dict)
async def analyze_style(
    request: StyleAnalysisRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Any:
    """分析写作风格"""
    try:
        # 调用风格分析服务
        from app.services.style_service import style_service
        
        # 获取用户上传的文章
        from app.crud.article import article as article_crud
        articles = await article_crud.get_by_ids(
            db,
            article_ids=request.article_ids,
            user_id=current_user.id
        )
        
        if not articles:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="未找到指定的文章"
            )
        
        # 分析风格
        style_features = await style_service.analyze_style(articles)
        
        # 如果指定了风格档案ID，更新该档案
        if request.style_profile_id:
            from app.crud.style import style as style_crud
            style_profile = await style_crud.get(db, id=request.style_profile_id)
            
            if style_profile and style_profile.user_id == current_user.id:
                await style_crud.update_features(
                    db,
                    db_obj=style_profile,
                    features=style_features
                )
        
        return {
            "code": 200,
            "message": "风格分析完成",
            "data": {
                "style_features": style_features,
                "analysis_summary": style_service.generate_summary(style_features)
            }
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"风格分析失败: {str(e)}"
        )


@router.post("/generate-content", response_model=dict)
async def generate_content(
    request: ContentGenerationRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Any:
    """生成内容"""
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
        
        return {
            "code": 200,
            "message": "内容生成成功",
            "data": {
                "generated_content": generated_content,
                "word_count": len(generated_content),
                "content_type": request.content_type
            }
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"内容生成失败: {str(e)}"
        )


@router.post("/summarize", response_model=dict)
async def summarize_content(
    request: ContentSummaryRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Any:
    """内容摘要"""
    try:
        # 调用AI服务生成摘要
        from app.services.ai_service import ai_service
        
        # 生成摘要
        summary = await ai_service.summarize_content(
            content=request.content,
            max_length=request.max_length,
            style=request.summary_style
        )
        
        return {
            "code": 200,
            "message": "摘要生成成功",
            "data": {
                "summary": summary,
                "original_length": len(request.content),
                "summary_length": len(summary)
            }
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"摘要生成失败: {str(e)}"
        )


@router.post("/suggest-titles", response_model=dict)
async def suggest_titles(
    request: TitleSuggestionRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Any:
    """标题建议"""
    try:
        # 调用AI服务生成标题建议
        from app.services.ai_service import ai_service
        
        # 生成标题建议
        titles = await ai_service.suggest_titles(
            content=request.content,
            topic=request.topic,
            count=request.count,
            style=request.title_style
        )
        
        return {
            "code": 200,
            "message": "标题建议生成成功",
            "data": {
                "titles": titles,
                "count": len(titles)
            }
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"标题建议生成失败: {str(e)}"
        )