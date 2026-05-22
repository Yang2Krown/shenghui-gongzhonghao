from typing import Any, Dict, List, Optional, Union
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime

from app.crud.base import CRUDBase
from app.models.creation import ContentCreation
from app.schemas.creation import (
    ContentCreationCreate,
    ContentCreationUpdate
)


class CRUDContentCreation(CRUDBase[ContentCreation, ContentCreationCreate, ContentCreationUpdate]):
    """内容创作CRUD操作类"""
    
    async def get_by_user(
        self,
        db: AsyncSession,
        *,
        user_id: int,
        skip: int = 0,
        limit: int = 100,
        status: str = None,
        topic_id: int = None
    ) -> List[ContentCreation]:
        """
        获取用户的创作列表
        :param db: 数据库会话
        :param user_id: 用户ID
        :param skip: 跳过记录数
        :param limit: 限制记录数
        :param status: 状态筛选
        :param topic_id: 选题ID筛选
        :return: 创作列表
        """
        statement = (
            select(ContentCreation)
            .where(ContentCreation.user_id == user_id)
        )
        
        # 应用筛选条件
        if status:
            statement = statement.where(ContentCreation.status == status)
        
        if topic_id:
            statement = statement.where(ContentCreation.topic_id == topic_id)
        
        # 排序和分页
        statement = (
            statement
            .order_by(ContentCreation.updated_at.desc())
            .offset(skip)
            .limit(limit)
        )
        
        result = await db.execute(statement)
        return result.scalars().all()
    
    async def count_by_user(
        self,
        db: AsyncSession,
        *,
        user_id: int,
        status: str = None,
        topic_id: int = None
    ) -> int:
        """
        统计用户创作数量
        :param db: 数据库会话
        :param user_id: 用户ID
        :param status: 状态筛选
        :param topic_id: 选题ID筛选
        :return: 创作总数
        """
        from sqlalchemy import func
        statement = (
            select(func.count())
            .select_from(ContentCreation)
            .where(ContentCreation.user_id == user_id)
        )
        
        # 应用筛选条件
        if status:
            statement = statement.where(ContentCreation.status == status)
        
        if topic_id:
            statement = statement.where(ContentCreation.topic_id == topic_id)
        
        result = await db.execute(statement)
        return result.scalar()
    
    async def create(
        self,
        db: AsyncSession,
        *,
        obj_in: ContentCreationCreate,
        user_id: int
    ) -> ContentCreation:
        """
        创建创作
        :param db: 数据库会话
        :param obj_in: 创建数据
        :param user_id: 用户ID
        :return: 创建的创作记录
        """
        # 计算字数和阅读时间
        content = obj_in.content or ""
        word_count = len(content)
        reading_time = max(1, word_count // 500)  # 假设每分钟500字
        
        db_obj = ContentCreation(
            user_id=user_id,
            topic_id=obj_in.topic_id,
            title=obj_in.title,
            content=content,
            status=obj_in.status or "draft",
            style_profile_id=obj_in.style_profile_id,
            tags=obj_in.tags or [],
            summary=obj_in.summary,
            featured_image=obj_in.featured_image,
            word_count=word_count,
            reading_time=reading_time
        )
        
        db.add(db_obj)
        await db.commit()
        await db.refresh(db_obj)
        return db_obj
    
    async def update(
        self,
        db: AsyncSession,
        *,
        db_obj: ContentCreation,
        obj_in: Union[ContentCreationUpdate, Dict[str, Any]]
    ) -> ContentCreation:
        """
        更新创作
        :param db: 数据库会话
        :param db_obj: 数据库创作对象
        :param obj_in: 更新数据
        :return: 更新后的创作
        """
        # 获取更新数据
        if isinstance(obj_in, dict):
            update_data = obj_in
        else:
            update_data = obj_in.dict(exclude_unset=True)
        
        # 更新字段
        for field, value in update_data.items():
            if hasattr(db_obj, field):
                setattr(db_obj, field, value)
        
        # 如果内容更新，重新计算字数和阅读时间
        if "content" in update_data:
            content = update_data["content"] or ""
            db_obj.word_count = len(content)
            db_obj.reading_time = max(1, len(content) // 500)
        
        # 更新时间
        db_obj.updated_at = datetime.utcnow()
        
        db.add(db_obj)
        await db.commit()
        await db.refresh(db_obj)
        return db_obj
    
    async def publish(
        self,
        db: AsyncSession,
        *,
        db_obj: ContentCreation,
        platform: str = None,
        url: str = None
    ) -> ContentCreation:
        """
        发布创作
        :param db: 数据库会话
        :param db_obj: 数据库创作对象
        :param platform: 发布平台
        :param url: 平台URL
        :return: 更新后的创作
        """
        db_obj.status = "published"
        db_obj.published_at = datetime.utcnow()
        
        if platform:
            db_obj.published_platform = platform
        if url:
            db_obj.platform_url = url
        
        db.add(db_obj)
        await db.commit()
        await db.refresh(db_obj)
        return db_obj
    
    async def archive(
        self,
        db: AsyncSession,
        *,
        db_obj: ContentCreation
    ) -> ContentCreation:
        """
        归档创作
        :param db: 数据库会话
        :param db_obj: 数据库创作对象
        :return: 更新后的创作
        """
        db_obj.status = "archived"
        db_obj.updated_at = datetime.utcnow()
        
        db.add(db_obj)
        await db.commit()
        await db.refresh(db_obj)
        return db_obj
    
    async def get_drafts(
        self,
        db: AsyncSession,
        *,
        user_id: int,
        limit: int = 10
    ) -> List[ContentCreation]:
        """
        获取用户草稿
        :param db: 数据库会话
        :param user_id: 用户ID
        :param limit: 限制数量
        :return: 草稿列表
        """
        statement = (
            select(ContentCreation)
            .where(
                and_(
                    ContentCreation.user_id == user_id,
                    ContentCreation.status == "draft"
                )
            )
            .order_by(ContentCreation.updated_at.desc())
            .limit(limit)
        )
        
        result = await db.execute(statement)
        return result.scalars().all()
    
    async def get_published(
        self,
        db: AsyncSession,
        *,
        user_id: int,
        skip: int = 0,
        limit: int = 100
    ) -> List[ContentCreation]:
        """
        获取用户已发布创作
        :param db: 数据库会话
        :param user_id: 用户ID
        :param skip: 跳过记录数
        :param limit: 限制记录数
        :return: 已发布创作列表
        """
        statement = (
            select(ContentCreation)
            .where(
                and_(
                    ContentCreation.user_id == user_id,
                    ContentCreation.status == "published"
                )
            )
            .order_by(ContentCreation.published_at.desc())
            .offset(skip)
            .limit(limit)
        )
        
        result = await db.execute(statement)
        return result.scalars().all()
    
    async def increment_view_count(
        self,
        db: AsyncSession,
        *,
        db_obj: ContentCreation
    ) -> ContentCreation:
        """
        增加浏览次数
        :param db: 数据库会话
        :param db_obj: 数据库创作对象
        :return: 更新后的创作
        """
        db_obj.view_count += 1
        db.add(db_obj)
        await db.commit()
        await db.refresh(db_obj)
        return db_obj
    
    async def increment_like_count(
        self,
        db: AsyncSession,
        *,
        db_obj: ContentCreation
    ) -> ContentCreation:
        """
        增加点赞次数
        :param db: 数据库会话
        :param db_obj: 数据库创作对象
        :return: 更新后的创作
        """
        db_obj.like_count += 1
        db.add(db_obj)
        await db.commit()
        await db.refresh(db_obj)
        return db_obj


# 创建内容创作CRUD实例
creation = CRUDContentCreation(ContentCreation)