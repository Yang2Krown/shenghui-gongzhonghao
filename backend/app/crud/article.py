from typing import Any, Dict, List, Optional, Union
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime

from app.crud.base import CRUDBase
from app.models.style import ArticleForAnalysis
from app.schemas.article import (
    ArticleForAnalysisCreate,
    ArticleForAnalysisUpdate
)


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


# 创建分析文章CRUD实例
article = CRUDArticleForAnalysis(ArticleForAnalysis)