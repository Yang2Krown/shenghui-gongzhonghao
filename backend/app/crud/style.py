from typing import Any, Dict, List, Optional, Union
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime

from app.crud.base import CRUDBase
from app.models.style import StyleProfile, ArticleForAnalysis
from app.schemas.style import (
    StyleProfileCreate,
    StyleProfileUpdate,
    ArticleForAnalysisCreate,
    ArticleForAnalysisUpdate
)


class CRUDStyleProfile(CRUDBase[StyleProfile, StyleProfileCreate, StyleProfileUpdate]):
    """风格档案CRUD操作类"""
    
    async def get_by_user(
        self,
        db: AsyncSession,
        *,
        user_id: int,
        skip: int = 0,
        limit: int = 100
    ) -> List[StyleProfile]:
        """
        获取用户的风格档案列表
        :param db: 数据库会话
        :param user_id: 用户ID
        :param skip: 跳过记录数
        :param limit: 限制记录数
        :return: 风格档案列表
        """
        statement = (
            select(StyleProfile)
            .where(StyleProfile.user_id == user_id)
            .order_by(StyleProfile.created_at.desc())
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
        统计用户风格档案数量
        :param db: 数据库会话
        :param user_id: 用户ID
        :return: 风格档案总数
        """
        from sqlalchemy import func
        statement = (
            select(func.count())
            .select_from(StyleProfile)
            .where(StyleProfile.user_id == user_id)
        )
        
        result = await db.execute(statement)
        return result.scalar()
    
    async def get_by_name(
        self,
        db: AsyncSession,
        *,
        name: str,
        user_id: int = None
    ) -> Optional[StyleProfile]:
        """
        根据名称获取风格档案
        :param db: 数据库会话
        :param name: 风格名称
        :param user_id: 用户ID（可选）
        :return: 风格档案对象或None
        """
        statement = select(StyleProfile).where(StyleProfile.name == name)
        
        if user_id:
            statement = statement.where(StyleProfile.user_id == user_id)
        
        result = await db.execute(statement)
        return result.scalars().first()
    
    async def get_default(
        self,
        db: AsyncSession,
        *,
        user_id: int
    ) -> Optional[StyleProfile]:
        """
        获取用户默认风格档案
        :param db: 数据库会话
        :param user_id: 用户ID
        :return: 默认风格档案或None
        """
        statement = (
            select(StyleProfile)
            .where(
                and_(
                    StyleProfile.user_id == user_id,
                    StyleProfile.is_default == True
                )
            )
        )
        
        result = await db.execute(statement)
        return result.scalars().first()
    
    async def create(
        self,
        db: AsyncSession,
        *,
        obj_in: StyleProfileCreate,
        user_id: int
    ) -> StyleProfile:
        """
        创建风格档案
        :param db: 数据库会话
        :param obj_in: 创建数据
        :param user_id: 用户ID
        :return: 创建的风格档案
        """
        db_obj = StyleProfile(
            user_id=user_id,
            name=obj_in.name,
            description=obj_in.description,
            style_features=obj_in.style_features or {},
            is_active=obj_in.is_active if obj_in.is_active is not None else True,
            is_default=obj_in.is_default if obj_in.is_default is not None else False,
            tone=obj_in.tone,
            language_style=obj_in.language_style,
            sentence_structure=obj_in.sentence_structure,
            vocabulary_level=obj_in.vocabulary_level,
            paragraph_length=obj_in.paragraph_length,
            use_emoji=obj_in.use_emoji if obj_in.use_emoji is not None else False,
            use_questions=obj_in.use_questions if obj_in.use_questions is not None else True,
            use_statistics=obj_in.use_statistics if obj_in.use_statistics is not None else True,
            confidence_score=0.0
        )
        
        db.add(db_obj)
        await db.commit()
        await db.refresh(db_obj)
        return db_obj
    
    async def update_features(
        self,
        db: AsyncSession,
        *,
        db_obj: StyleProfile,
        features: Dict[str, Any]
    ) -> StyleProfile:
        """
        更新风格特征
        :param db: 数据库会话
        :param db_obj: 数据库风格档案对象
        :param features: 风格特征
        :return: 更新后的风格档案
        """
        db_obj.style_features = features
        db_obj.updated_at = datetime.utcnow()
        
        db.add(db_obj)
        await db.commit()
        await db.refresh(db_obj)
        return db_obj
    
    async def set_default(
        self,
        db: AsyncSession,
        *,
        db_obj: StyleProfile
    ) -> StyleProfile:
        """
        设置为默认风格
        :param db: 数据库会话
        :param db_obj: 数据库风格档案对象
        :return: 更新后的风格档案
        """
        # 先取消其他默认风格
        statement = (
            select(StyleProfile)
            .where(
                and_(
                    StyleProfile.user_id == db_obj.user_id,
                    StyleProfile.is_default == True,
                    StyleProfile.id != db_obj.id
                )
            )
        )
        result = await db.execute(statement)
        other_defaults = result.scalars().all()
        
        for other in other_defaults:
            other.is_default = False
            db.add(other)
        
        # 设置当前为默认
        db_obj.is_default = True
        db.add(db_obj)
        
        await db.commit()
        await db.refresh(db_obj)
        return db_obj


class CRUDArticleForAnalysis(CRUDBase[ArticleForAnalysis, ArticleForAnalysisCreate, ArticleForAnalysisUpdate]):
    """分析文章CRUD操作类"""
    
    async def get_by_user(
        self,
        db: AsyncSession,
        *,
        user_id: int,
        skip: int = 0,
        limit: int = 100,
        platform: str = None
    ) -> List[ArticleForAnalysis]:
        """
        获取用户的文章列表
        :param db: 数据库会话
        :param user_id: 用户ID
        :param skip: 跳过记录数
        :param limit: 限制记录数
        :param platform: 平台筛选
        :return: 文章列表
        """
        statement = (
            select(ArticleForAnalysis)
            .where(ArticleForAnalysis.user_id == user_id)
        )
        
        if platform:
            statement = statement.where(ArticleForAnalysis.platform == platform)
        
        statement = (
            statement
            .order_by(ArticleForAnalysis.created_at.desc())
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
        platform: str = None
    ) -> int:
        """
        统计用户文章数量
        :param db: 数据库会话
        :param user_id: 用户ID
        :param platform: 平台筛选
        :return: 文章总数
        """
        from sqlalchemy import func
        statement = (
            select(func.count())
            .select_from(ArticleForAnalysis)
            .where(ArticleForAnalysis.user_id == user_id)
        )
        
        if platform:
            statement = statement.where(ArticleForAnalysis.platform == platform)
        
        result = await db.execute(statement)
        return result.scalar()
    
    async def get_by_ids(
        self,
        db: AsyncSession,
        *,
        article_ids: List[int],
        user_id: int
    ) -> List[ArticleForAnalysis]:
        """
        根据ID列表获取文章
        :param db: 数据库会话
        :param article_ids: 文章ID列表
        :param user_id: 用户ID
        :return: 文章列表
        """
        statement = (
            select(ArticleForAnalysis)
            .where(
                and_(
                    ArticleForAnalysis.id.in_(article_ids),
                    ArticleForAnalysis.user_id == user_id
                )
            )
        )
        
        result = await db.execute(statement)
        return result.scalars().all()
    
    async def get_unprocessed(
        self,
        db: AsyncSession,
        *,
        limit: int = 100
    ) -> List[ArticleForAnalysis]:
        """
        获取未处理的文章
        :param db: 数据库会话
        :param limit: 限制数量
        :return: 未处理文章列表
        """
        statement = (
            select(ArticleForAnalysis)
            .where(ArticleForAnalysis.is_processed == False)
            .order_by(ArticleForAnalysis.created_at.asc())
            .limit(limit)
        )
        
        result = await db.execute(statement)
        return result.scalars().all()
    
    async def mark_as_processed(
        self,
        db: AsyncSession,
        *,
        db_obj: ArticleForAnalysis
    ) -> ArticleForAnalysis:
        """
        标记文章为已处理
        :param db: 数据库会话
        :param db_obj: 数据库文章对象
        :return: 更新后的文章
        """
        db_obj.is_processed = True
        db_obj.processing_status = "completed"
        db_obj.updated_at = datetime.utcnow()
        
        db.add(db_obj)
        await db.commit()
        await db.refresh(db_obj)
        return db_obj


# 创建风格档案CRUD实例
style = CRUDStyleProfile(StyleProfile)
article = CRUDArticleForAnalysis(ArticleForAnalysis)