from typing import Any, List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_current_user
from app.crud.topic import topic as topic_crud
from app.crud.topic import topic_collection as collection_crud
from app.db.session import get_db
from app.models.user import User
from app.models.topic import Topic, TopicCollection
from app.schemas.topic import (
    TopicCreate,
    TopicUpdate,
    TopicResponse,
    TopicListResponse,
    TopicCollectionCreate,
    TopicCollectionResponse,
    TopicFilter
)

router = APIRouter()


@router.get("", response_model=dict)
async def get_topics(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    category: Optional[str] = Query(None, description="分类筛选"),
    platform: Optional[str] = Query(None, description="平台筛选"),
    keyword: Optional[str] = Query(None, description="关键词搜索"),
    sort_by: str = Query("published_at", description="排序字段"),
    sort_order: str = Query("desc", description="排序方式")
) -> Any:
    """获取选题列表"""
    # 计算偏移量
    skip = (page - 1) * page_size
    
    # 构建筛选条件
    filters = TopicFilter(
        category=category,
        platform=platform,
        keyword=keyword,
        sort_by=sort_by,
        sort_order=sort_order
    )
    
    # 获取选题列表
    topics = await topic_crud.get_multi(
        db,
        skip=skip,
        limit=page_size,
        filters=filters
    )
    
    # 获取总数
    total = await topic_crud.count(db, filters=filters)
    
    return {
        "code": 200,
        "message": "获取选题列表成功",
        "data": {
            "items": [TopicResponse.from_orm(topic).dict() for topic in topics],
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": (total + page_size - 1) // page_size
        }
    }


@router.get("/{topic_id}", response_model=dict)
async def get_topic(
    topic_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Any:
    """获取选题详情"""
    topic = await topic_crud.get(db, id=topic_id)
    if not topic:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="选题不存在"
        )
    
    # 检查用户是否已收藏
    is_collected = await collection_crud.exists(
        db,
        user_id=current_user.id,
        topic_id=topic_id
    )
    
    topic_data = TopicResponse.from_orm(topic).dict()
    topic_data["is_collected"] = is_collected
    
    return {
        "code": 200,
        "message": "获取选题详情成功",
        "data": topic_data
    }


@router.post("/collect", response_model=dict)
async def collect_topic(
    collection_in: TopicCollectionCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Any:
    """收藏选题"""
    # 检查选题是否存在
    topic = await topic_crud.get(db, id=collection_in.topic_id)
    if not topic:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="选题不存在"
        )
    
    # 检查是否已收藏
    existing_collection = await collection_crud.exists(
        db,
        user_id=current_user.id,
        topic_id=collection_in.topic_id
    )
    
    if existing_collection:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="已收藏该选题"
        )
    
    # 创建收藏
    collection = await collection_crud.create(
        db,
        obj_in=collection_in,
        user_id=current_user.id
    )
    
    return {
        "code": 200,
        "message": "收藏成功",
        "data": TopicCollectionResponse.from_orm(collection).dict()
    }


@router.delete("/collect/{collection_id}", response_model=dict)
async def cancel_collection(
    collection_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Any:
    """取消收藏"""
    # 获取收藏记录
    collection = await collection_crud.get(db, id=collection_id)
    if not collection:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="收藏记录不存在"
        )
    
    # 检查是否是当前用户的收藏
    if collection.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权取消他人收藏"
        )
    
    # 删除收藏
    await collection_crud.remove(db, id=collection_id)
    
    return {
        "code": 200,
        "message": "取消收藏成功",
        "data": None
    }


@router.get("/collected", response_model=dict)
async def get_collected_topics(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量")
) -> Any:
    """获取用户收藏的选题"""
    # 计算偏移量
    skip = (page - 1) * page_size
    
    # 获取收藏列表
    collections = await collection_crud.get_by_user(
        db,
        user_id=current_user.id,
        skip=skip,
        limit=page_size
    )
    
    # 获取总数
    total = await collection_crud.count_by_user(db, user_id=current_user.id)
    
    # 获取选题详情
    topics = []
    for collection in collections:
        topic = await topic_crud.get(db, id=collection.topic_id)
        if topic:
            topic_data = TopicResponse.from_orm(topic).dict()
            topic_data["collection_id"] = collection.id
            topic_data["collected_at"] = collection.collected_at
            topic_data["notes"] = collection.notes
            topics.append(topic_data)
    
    return {
        "code": 200,
        "message": "获取收藏选题成功",
        "data": {
            "items": topics,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": (total + page_size - 1) // page_size
        }
    }


@router.post("/refresh", response_model=dict)
async def refresh_topics(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Any:
    """手动刷新选题（触发数据抓取）"""
    try:
        # 调用数据抓取服务
        from app.services.scraper_service import scraper_service
        result = await scraper_service.fetch_and_save_topics(db)
        
        return {
            "code": 200,
            "message": "选题刷新成功",
            "data": {
                "new_topics": result.get("new_topics", 0),
                "updated_topics": result.get("updated_topics", 0),
                "failed_topics": result.get("failed_topics", 0)
            }
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"选题刷新失败: {str(e)}"
        )


@router.get("/hot", response_model=dict)
async def get_hot_topics(
    limit: int = Query(10, ge=1, le=50, description="数量限制"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Any:
    """获取热门选题"""
    # 按热度分数排序获取热门选题
    topics = await topic_crud.get_hot_topics(db, limit=limit)
    
    return {
        "code": 200,
        "message": "获取热门选题成功",
        "data": [TopicResponse.from_orm(topic).dict() for topic in topics]
    }


@router.get("/recommended", response_model=dict)
async def get_recommended_topics(
    limit: int = Query(10, ge=1, le=50, description="数量限制"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Any:
    """获取推荐选题"""
    # 获取推荐选题（基于用户偏好和热度）
    topics = await topic_crud.get_recommended_topics(db, user_id=current_user.id, limit=limit)
    
    return {
        "code": 200,
        "message": "获取推荐选题成功",
        "data": [TopicResponse.from_orm(topic).dict() for topic in topics]
    }