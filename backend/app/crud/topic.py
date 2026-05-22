from typing import Any, Dict, List, Optional, Union
from sqlalchemy import select, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.base import CRUDBase
from app.models.topic import Topic, TopicCollection
from app.schemas.topic import (
    TopicCreate,
    TopicUpdate,
    TopicCollectionCreate,
    TopicFilter
)


class CRUDTopic(CRUDBase[Topic, TopicCreate, TopicUpdate]):
    """选题CRUD操作类"""
    
    async def get_multi(
        self,
        db: AsyncSession,
        *,
        skip: int = 0,
        limit: int = 100,
        filters: TopicFilter = None
    ) -> List[Topic]:
        """
        获取选题列表
        :param db: 数据库会话
        :param skip: 跳过记录数
        :param limit: 限制记录数
        :param filters: 筛选条件
        :return: 选题列表
        """
        statement = select(Topic)
        
        if filters:
            # 应用筛选条件
            if filters.category:
                statement = statement.where(Topic.category == filters.category)
            
            if filters.platform:
                statement = statement.where(Topic.source_platform == filters.platform)
            
            if filters.keyword:
                keyword_filter = or_(
                    Topic.title.contains(filters.keyword),
                    Topic.content_summary.contains(filters.keyword),
                    Topic.keywords.contains(filters.keyword)
                )
                statement = statement.where(keyword_filter)
            
            if filters.start_date:
                statement = statement.where(Topic.published_at >= filters.start_date)
            
            if filters.end_date:
                statement = statement.where(Topic.published_at <= filters.end_date)
            
            if filters.min_heat_score is not None:
                statement = statement.where(Topic.heat_score >= filters.min_heat_score)
            
            # 排序
            sort_column = getattr(Topic, filters.sort_by, Topic.published_at)
            if filters.sort_order == "desc":
                statement = statement.order_by(sort_column.desc())
            else:
                statement = statement.order_by(sort_column.asc())
        else:
            # 默认按发布时间倒序
            statement = statement.order_by(Topic.published_at.desc())
        
        # 分页
        statement = statement.offset(skip).limit(limit)
        
        result = await db.execute(statement)
        return result.scalars().all()
    
    async def count(
        self,
        db: AsyncSession,
        *,
        filters: TopicFilter = None
    ) -> int:
        """
        统计选题数量
        :param db: 数据库会话
        :param filters: 筛选条件
        :return: 选题总数
        """
        from sqlalchemy import func
        statement = select(func.count()).select_from(Topic)
        
        if filters:
            # 应用筛选条件
            if filters.category:
                statement = statement.where(Topic.category == filters.category)
            
            if filters.platform:
                statement = statement.where(Topic.source_platform == filters.platform)
            
            if filters.keyword:
                keyword_filter = or_(
                    Topic.title.contains(filters.keyword),
                    Topic.content_summary.contains(filters.keyword),
                    Topic.keywords.contains(filters.keyword)
                )
                statement = statement.where(keyword_filter)
            
            if filters.start_date:
                statement = statement.where(Topic.published_at >= filters.start_date)
            
            if filters.end_date:
                statement = statement.where(Topic.published_at <= filters.end_date)
            
            if filters.min_heat_score is not None:
                statement = statement.where(Topic.heat_score >= filters.min_heat_score)
        
        result = await db.execute(statement)
        return result.scalar()
    
    async def get_by_source_url(
        self,
        db: AsyncSession,
        *,
        source_url: str
    ) -> Optional[Topic]:
        """
        根据来源URL获取选题
        :param db: 数据库会话
        :param source_url: 来源URL
        :return: 选题对象或None
        """
        statement = select(Topic).where(Topic.source_url == source_url)
        result = await db.execute(statement)
        return result.scalars().first()
    
    async def get_by_platform(
        self,
        db: AsyncSession,
        *,
        platform: str,
        skip: int = 0,
        limit: int = 100
    ) -> List[Topic]:
        """
        根据平台获取选题
        :param db: 数据库会话
        :param platform: 平台名称
        :param skip: 跳过记录数
        :param limit: 限制记录数
        :return: 选题列表
        """
        statement = (
            select(Topic)
            .where(Topic.source_platform == platform)
            .order_by(Topic.published_at.desc())
            .offset(skip)
            .limit(limit)
        )
        
        result = await db.execute(statement)
        return result.scalars().all()
    
    async def get_hot_topics(
        self,
        db: AsyncSession,
        *,
        limit: int = 10,
        days: int = 7
    ) -> List[Topic]:
        """
        获取热门选题
        :param db: 数据库会话
        :param limit: 限制数量
        :param days: 天数限制
        :return: 热门选题列表
        """
        from datetime import datetime, timedelta
        from sqlalchemy import func
        
        start_date = datetime.utcnow() - timedelta(days=days)
        
        statement = (
            select(Topic)
            .where(Topic.published_at >= start_date)
            .order_by(Topic.heat_score.desc())
            .limit(limit)
        )
        
        result = await db.execute(statement)
        return result.scalars().all()
    
    async def get_recommended_topics(
        self,
        db: AsyncSession,
        *,
        user_id: int,
        limit: int = 10
    ) -> List[Topic]:
        """
        获取推荐选题（基于用户收藏历史和热度）
        :param db: 数据库会话
        :param user_id: 用户ID
        :param limit: 限制数量
        :return: 推荐选题列表
        """
        from datetime import datetime, timedelta
        
        # 获取用户收藏的选题类别
        user_collections = await db.execute(
            select(TopicCollection)
            .where(TopicCollection.user_id == user_id)
            .limit(10)
        )
        collected_topics = user_collections.scalars().all()
        
        if collected_topics:
            # 获取用户收藏的选题
            collected_topic_ids = [c.topic_id for c in collected_topics]
            collected_topics_data = await db.execute(
                select(Topic)
                .where(Topic.id.in_(collected_topic_ids))
            )
            collected_topics_list = collected_topics_data.scalars().all()
            
            # 提取用户偏好的类别和平台
            preferred_categories = list(set(t.category for t in collected_topics_list if t.category))
            preferred_platforms = list(set(t.source_platform for t in collected_topics_list if t.source_platform))
            
            # 获取相似选题（同类别或同平台，排除已收藏）
            start_date = datetime.utcnow() - timedelta(days=30)
            
            statement = (
                select(Topic)
                .where(
                    and_(
                        Topic.published_at >= start_date,
                        ~Topic.id.in_(collected_topic_ids)
                    )
                )
            )
            
            if preferred_categories:
                statement = statement.where(Topic.category.in_(preferred_categories))
            
            statement = (
                statement
                .order_by(Topic.heat_score.desc())
                .limit(limit)
            )
            
            result = await db.execute(statement)
            recommended = result.scalars().all()
            
            # 如果推荐数量不足，补充热门选题
            if len(recommended) < limit:
                remaining = limit - len(recommended)
                recommended_ids = [t.id for t in recommended]
                
                supplement_stmt = (
                    select(Topic)
                    .where(
                        and_(
                            Topic.published_at >= start_date,
                            ~Topic.id.in_(recommended_ids + collected_topic_ids)
                        )
                    )
                    .order_by(Topic.heat_score.desc())
                    .limit(remaining)
                )
                
                supplement_result = await db.execute(supplement_stmt)
                recommended.extend(supplement_result.scalars().all())
            
            return recommended
        else:
            # 用户没有收藏历史，返回热门选题
            return await self.get_hot_topics(db, limit=limit)


class CRUDTopicCollection(CRUDBase[TopicCollection, TopicCollectionCreate, None]):
    """选题收藏CRUD操作类"""
    
    async def get_by_user(
        self,
        db: AsyncSession,
        *,
        user_id: int,
        skip: int = 0,
        limit: int = 100
    ) -> List[TopicCollection]:
        """
        获取用户收藏的选题
        :param db: 数据库会话
        :param user_id: 用户ID
        :param skip: 跳过记录数
        :param limit: 限制记录数
        :return: 收藏列表
        """
        statement = (
            select(TopicCollection)
            .where(TopicCollection.user_id == user_id)
            .order_by(TopicCollection.collected_at.desc())
            .offset(skip)
            .limit(limit)
        )
        
        result = await db.execute(statement)
        return result.scalars().all()
    
    async def count_by_user(
        self,
        db: AsyncSession,
        *,
        user_id: int
    ) -> int:
        """
        统计用户收藏数量
        :param db: 数据库会话
        :param user_id: 用户ID
        :return: 收藏总数
        """
        from sqlalchemy import func
        statement = (
            select(func.count())
            .select_from(TopicCollection)
            .where(TopicCollection.user_id == user_id)
        )
        
        result = await db.execute(statement)
        return result.scalar()
    
    async def exists(
        self,
        db: AsyncSession,
        *,
        user_id: int,
        topic_id: int
    ) -> bool:
        """
        检查用户是否已收藏选题
        :param db: 数据库会话
        :param user_id: 用户ID
        :param topic_id: 选题ID
        :return: 是否已收藏
        """
        statement = (
            select(func.count())
            .select_from(TopicCollection)
            .where(
                and_(
                    TopicCollection.user_id == user_id,
                    TopicCollection.topic_id == topic_id
                )
            )
        )
        
        result = await db.execute(statement)
        return result.scalar() > 0
    
    async def create(
        self,
        db: AsyncSession,
        *,
        obj_in: TopicCollectionCreate,
        user_id: int
    ) -> TopicCollection:
        """
        创建收藏
        :param db: 数据库会话
        :param obj_in: 创建数据
        :param user_id: 用户ID
        :return: 创建的收藏记录
        """
        db_obj = TopicCollection(
            user_id=user_id,
            topic_id=obj_in.topic_id,
            notes=obj_in.notes
        )
        
        db.add(db_obj)
        await db.commit()
        await db.refresh(db_obj)
        return db_obj


# 创建选题CRUD实例
topic = CRUDTopic(Topic)
topic_collection = CRUDTopicCollection(TopicCollection)