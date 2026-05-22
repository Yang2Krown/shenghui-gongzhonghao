"""
选题服务模块
提供选题的业务逻辑处理
"""
import logging
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_

from app.models.topic import Topic, TopicCollection
from app.models.user import User
from app.schemas.topic import TopicCreate, TopicUpdate, TopicCollectionCreate
from app.crud.topic import topic as topic_crud
from app.crud.topic import topic_collection as collection_crud
from app.services.ai_service import get_ai_service

logger = logging.getLogger(__name__)


class TopicService:
    """选题服务类"""

    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)

    async def get_topics(
        self,
        db: AsyncSession,
        *,
        user_id: Optional[str] = None,
        category: Optional[str] = None,
        platform: Optional[str] = None,
        keyword: Optional[str] = None,
        days: Optional[int] = None,
        page: int = 1,
        page_size: int = 20
    ) -> Dict[str, Any]:
        """
        获取选题列表
        
        Args:
            db: 数据库会话
            user_id: 用户ID（用于过滤已收藏）
            category: 分类筛选
            platform: 平台筛选
            keyword: 关键词搜索
            days: 最近N天的选题
            page: 页码
            page_size: 每页数量
            
        Returns:
            包含选题列表和分页信息的字典
        """
        try:
            # 构建查询条件
            filters = []
            
            if category:
                filters.append(Topic.category == category)
            
            if platform:
                filters.append(Topic.source_platform == platform)
            
            if keyword:
                keyword_filter = or_(
                    Topic.title.ilike(f"%{keyword}%"),
                    Topic.content_summary.ilike(f"%{keyword}%"),
                    Topic.keywords.ilike(f"%{keyword}%")
                )
                filters.append(keyword_filter)
            
            if days:
                cutoff_date = datetime.utcnow() - timedelta(days=days)
                filters.append(Topic.scraped_at >= cutoff_date)
            
            # 获取总数
            count_query = select(func.count(Topic.id))
            if filters:
                count_query = count_query.where(and_(*filters))
            
            result = await db.execute(count_query)
            total = result.scalar()
            
            # 获取分页数据
            query = select(Topic).order_by(Topic.heat_score.desc(), Topic.scraped_at.desc())
            if filters:
                query = query.where(and_(*filters))
            
            query = query.offset((page - 1) * page_size).limit(page_size)
            result = await db.execute(query)
            topics = result.scalars().all()
            
            # 如果用户已登录，标记已收藏的选题
            collected_topic_ids = []
            if user_id:
                collected_query = select(TopicCollection.topic_id).where(
                    TopicCollection.user_id == user_id
                )
                collected_result = await db.execute(collected_query)
                collected_topic_ids = [row[0] for row in collected_result.all()]
            
            # 构建响应数据
            topic_list = []
            for topic in topics:
                topic_dict = {
                    "id": topic.id,
                    "title": topic.title,
                    "content_summary": topic.content_summary,
                    "source_platform": topic.source_platform,
                    "source_url": topic.source_url,
                    "category": topic.category,
                    "heat_score": topic.heat_score,
                    "published_at": topic.published_at.isoformat() if topic.published_at else None,
                    "scraped_at": topic.scraped_at.isoformat() if topic.scraped_at else None,
                    "keywords": topic.keywords,
                    "is_collected": topic.id in collected_topic_ids
                }
                topic_list.append(topic_dict)
            
            return {
                "items": topic_list,
                "total": total,
                "page": page,
                "page_size": page_size,
                "total_pages": (total + page_size - 1) // page_size
            }
            
        except Exception as e:
            self.logger.error(f"获取选题列表失败: {e}")
            raise

    async def get_topic_detail(
        self,
        db: AsyncSession,
        *,
        topic_id: str,
        user_id: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        获取选题详情
        
        Args:
            db: 数据库会话
            topic_id: 选题ID
            user_id: 用户ID
            
        Returns:
            选题详情字典
        """
        try:
            topic = await topic_crud.get(db=db, id=topic_id)
            if not topic:
                return None
            
            # 检查是否已收藏
            is_collected = False
            if user_id:
                collection = await collection_crud.get_by_user_and_topic(
                    db=db, user_id=user_id, topic_id=topic_id
                )
                is_collected = collection is not None
            
            return {
                "id": topic.id,
                "title": topic.title,
                "content_summary": topic.content_summary,
                "source_platform": topic.source_platform,
                "source_url": topic.source_url,
                "category": topic.category,
                "heat_score": topic.heat_score,
                "published_at": topic.published_at.isoformat() if topic.published_at else None,
                "scraped_at": topic.scraped_at.isoformat() if topic.scraped_at else None,
                "keywords": topic.keywords,
                "is_processed": topic.is_processed,
                "is_collected": is_collected
            }
            
        except Exception as e:
            self.logger.error(f"获取选题详情失败: {e}")
            raise

    async def collect_topic(
        self,
        db: AsyncSession,
        *,
        user_id: str,
        topic_id: str,
        notes: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        收藏选题
        
        Args:
            db: 数据库会话
            user_id: 用户ID
            topic_id: 选题ID
            notes: 备注
            
        Returns:
            收藏记录
        """
        try:
            # 检查选题是否存在
            topic = await topic_crud.get(db=db, id=topic_id)
            if not topic:
                raise ValueError("选题不存在")
            
            # 检查是否已收藏
            existing = await collection_crud.get_by_user_and_topic(
                db=db, user_id=user_id, topic_id=topic_id
            )
            if existing:
                raise ValueError("已收藏该选题")
            
            # 创建收藏记录
            collection_in = TopicCollectionCreate(
                topic_id=topic_id,
                notes=notes
            )
            collection = await collection_crud.create(
                db=db, obj_in=collection_in, user_id=user_id
            )
            
            return {
                "id": collection.id,
                "user_id": collection.user_id,
                "topic_id": collection.topic_id,
                "collected_at": collection.collected_at.isoformat(),
                "notes": collection.notes
            }
            
        except Exception as e:
            self.logger.error(f"收藏选题失败: {e}")
            raise

    async def uncollect_topic(
        self,
        db: AsyncSession,
        *,
        user_id: str,
        topic_id: str
    ) -> bool:
        """
        取消收藏选题
        
        Args:
            db: 数据库会话
            user_id: 用户ID
            topic_id: 选题ID
            
        Returns:
            是否成功
        """
        try:
            collection = await collection_crud.get_by_user_and_topic(
                db=db, user_id=user_id, topic_id=topic_id
            )
            if not collection:
                raise ValueError("未收藏该选题")
            
            await collection_crud.remove(db=db, id=collection.id)
            return True
            
        except Exception as e:
            self.logger.error(f"取消收藏选题失败: {e}")
            raise

    async def get_collected_topics(
        self,
        db: AsyncSession,
        *,
        user_id: str,
        page: int = 1,
        page_size: int = 20
    ) -> Dict[str, Any]:
        """
        获取用户收藏的选题
        
        Args:
            db: 数据库会话
            user_id: 用户ID
            page: 页码
            page_size: 每页数量
            
        Returns:
            收藏的选题列表
        """
        try:
            # 获取收藏的选题ID列表
            collections = await collection_crud.get_by_user(
                db=db, user_id=user_id, page=page, page_size=page_size
            )
            
            topic_ids = [c.topic_id for c in collections["items"]]
            
            # 获取选题详情
            topics = []
            for topic_id in topic_ids:
                topic = await topic_crud.get(db=db, id=topic_id)
                if topic:
                    topics.append({
                        "id": topic.id,
                        "title": topic.title,
                        "content_summary": topic.content_summary,
                        "source_platform": topic.source_platform,
                        "category": topic.category,
                        "heat_score": topic.heat_score,
                        "is_collected": True
                    })
            
            return {
                "items": topics,
                "total": collections["total"],
                "page": page,
                "page_size": page_size,
                "total_pages": collections["total_pages"]
            }
            
        except Exception as e:
            self.logger.error(f"获取收藏选题失败: {e}")
            raise

    async def refresh_topics(
        self,
        db: AsyncSession,
        *,
        platform: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        手动刷新选题
        
        Args:
            db: 数据库会话
            platform: 指定平台
            
        Returns:
            刷新结果
        """
        try:
            # 这里可以触发异步抓取任务
            # 实际实现会调用Celery任务
            self.logger.info(f"触发选题刷新，平台: {platform or '全部'}")
            
            return {
                "message": "选题刷新任务已提交",
                "platform": platform,
                "submitted_at": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"刷新选题失败: {e}")
            raise

    async def get_topic_suggestions(
        self,
        db: AsyncSession,
        *,
        user_id: str,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        获取选题建议（基于用户历史）
        
        Args:
            db: 数据库会话
            user_id: 用户ID
            limit: 返回数量
            
        Returns:
            选题建议列表
        """
        try:
            # 获取用户收藏的选题分类
            collections = await collection_crud.get_by_user(db=db, user_id=user_id, page=1, page_size=100)
            collected_topic_ids = [c.topic_id for c in collections["items"]]
            
            # 获取用户收藏选题的分类
            categories = []
            for topic_id in collected_topic_ids:
                topic = await topic_crud.get(db=db, id=topic_id)
                if topic and topic.category:
                    categories.append(topic.category)
            
            # 获取高频分类
            from collections import Counter
            category_counts = Counter(categories)
            top_categories = [cat for cat, _ in category_counts.most_common(3)]
            
            # 获取这些分类的热门选题
            suggestions = []
            for category in top_categories:
                topics = await topic_crud.get_by_category(
                    db=db, category=category, limit=limit // len(top_categories)
                )
                for topic in topics:
                    if topic.id not in collected_topic_ids:
                        suggestions.append({
                            "id": topic.id,
                            "title": topic.title,
                            "content_summary": topic.content_summary,
                            "category": topic.category,
                            "heat_score": topic.heat_score,
                            "reason": f"基于您对{category}类内容的兴趣"
                        })
            
            return suggestions[:limit]
            
        except Exception as e:
            self.logger.error(f"获取选题建议失败: {e}")
            raise


# 创建全局选题服务实例
topic_service = TopicService()
