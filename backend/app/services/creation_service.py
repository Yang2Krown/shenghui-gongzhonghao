"""
创作服务模块
提供内容创作的业务逻辑处理
"""
import logging
from typing import List, Optional, Dict, Any
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.models.creation import ContentCreation
from app.models.topic import Topic
from app.models.style import StyleProfile
from app.schemas.creation import (
    ContentCreationCreate,
    ContentCreationUpdate,
    ContentGenerationRequest
)
from app.crud.creation import content_creation as creation_crud
from app.services.ai_service import get_ai_service

logger = logging.getLogger(__name__)


class CreationService:
    """创作服务类"""

    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)

    async def get_creations(
        self,
        db: AsyncSession,
        *,
        user_id: str,
        status: Optional[str] = None,
        keyword: Optional[str] = None,
        page: int = 1,
        page_size: int = 20
    ) -> Dict[str, Any]:
        """
        获取创作列表
        
        Args:
            db: 数据库会话
            user_id: 用户ID
            status: 状态筛选
            keyword: 关键词搜索
            page: 页码
            page_size: 每页数量
            
        Returns:
            创作列表和分页信息
        """
        try:
            # 构建查询
            query = select(ContentCreation).where(
                ContentCreation.user_id == user_id
            )
            
            if status:
                query = query.where(ContentCreation.status == status)
            
            if keyword:
                query = query.where(
                    ContentCreation.title.ilike(f"%{keyword}%") |
                    ContentCreation.content.ilike(f"%{keyword}%")
                )
            
            # 获取总数
            count_query = select(func.count(ContentCreation.id)).where(
                ContentCreation.user_id == user_id
            )
            if status:
                count_query = count_query.where(ContentCreation.status == status)
            if keyword:
                count_query = count_query.where(
                    ContentCreation.title.ilike(f"%{keyword}%") |
                    ContentCreation.content.ilike(f"%{keyword}%")
                )
            
            result = await db.execute(count_query)
            total = result.scalar()
            
            # 获取分页数据
            query = query.order_by(ContentCreation.updated_at.desc())
            query = query.offset((page - 1) * page_size).limit(page_size)
            result = await db.execute(query)
            creations = result.scalars().all()
            
            # 构建响应
            creation_list = []
            for creation in creations:
                creation_list.append({
                    "id": creation.id,
                    "title": creation.title,
                    "content": creation.content[:200] + "..." if len(creation.content) > 200 else creation.content,
                    "status": creation.status,
                    "topic_id": creation.topic_id,
                    "style_profile_id": creation.style_profile_id,
                    "created_at": creation.created_at.isoformat(),
                    "updated_at": creation.updated_at.isoformat()
                })
            
            return {
                "items": creation_list,
                "total": total,
                "page": page,
                "page_size": page_size,
                "total_pages": (total + page_size - 1) // page_size
            }
            
        except Exception as e:
            self.logger.error(f"获取创作列表失败: {e}")
            raise

    async def get_creation_detail(
        self,
        db: AsyncSession,
        *,
        creation_id: str,
        user_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        获取创作详情
        
        Args:
            db: 数据库会话
            creation_id: 创作ID
            user_id: 用户ID
            
        Returns:
            创作详情
        """
        try:
            creation = await creation_crud.get(db=db, id=creation_id)
            if not creation or creation.user_id != user_id:
                return None
            
            return {
                "id": creation.id,
                "title": creation.title,
                "content": creation.content,
                "status": creation.status,
                "topic_id": creation.topic_id,
                "style_profile_id": creation.style_profile_id,
                "created_at": creation.created_at.isoformat(),
                "updated_at": creation.updated_at.isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"获取创作详情失败: {e}")
            raise

    async def create_creation(
        self,
        db: AsyncSession,
        *,
        user_id: str,
        creation_in: ContentCreationCreate
    ) -> Dict[str, Any]:
        """
        创建新创作
        
        Args:
            db: 数据库会话
            user_id: 用户ID
            creation_in: 创作数据
            
        Returns:
            创建的创作
        """
        try:
            creation = await creation_crud.create(
                db=db, obj_in=creation_in, user_id=user_id
            )
            
            return {
                "id": creation.id,
                "title": creation.title,
                "content": creation.content,
                "status": creation.status,
                "topic_id": creation.topic_id,
                "style_profile_id": creation.style_profile_id,
                "created_at": creation.created_at.isoformat(),
                "updated_at": creation.updated_at.isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"创建创作失败: {e}")
            raise

    async def update_creation(
        self,
        db: AsyncSession,
        *,
        creation_id: str,
        user_id: str,
        creation_in: ContentCreationUpdate
    ) -> Optional[Dict[str, Any]]:
        """
        更新创作
        
        Args:
            db: 数据库会话
            creation_id: 创作ID
            user_id: 用户ID
            creation_in: 更新数据
            
        Returns:
            更新后的创作
        """
        try:
            creation = await creation_crud.get(db=db, id=creation_id)
            if not creation or creation.user_id != user_id:
                return None
            
            updated_creation = await creation_crud.update(
                db=db, db_obj=creation, obj_in=creation_in
            )
            
            return {
                "id": updated_creation.id,
                "title": updated_creation.title,
                "content": updated_creation.content,
                "status": updated_creation.status,
                "topic_id": updated_creation.topic_id,
                "style_profile_id": updated_creation.style_profile_id,
                "created_at": updated_creation.created_at.isoformat(),
                "updated_at": updated_creation.updated_at.isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"更新创作失败: {e}")
            raise

    async def delete_creation(
        self,
        db: AsyncSession,
        *,
        creation_id: str,
        user_id: str
    ) -> bool:
        """
        删除创作
        
        Args:
            db: 数据库会话
            creation_id: 创作ID
            user_id: 用户ID
            
        Returns:
            是否成功
        """
        try:
            creation = await creation_crud.get(db=db, id=creation_id)
            if not creation or creation.user_id != user_id:
                return False
            
            await creation_crud.remove(db=db, id=creation_id)
            return True
            
        except Exception as e:
            self.logger.error(f"删除创作失败: {e}")
            raise

    async def publish_creation(
        self,
        db: AsyncSession,
        *,
        creation_id: str,
        user_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        发布创作
        
        Args:
            db: 数据库会话
            creation_id: 创作ID
            user_id: 用户ID
            
        Returns:
            发布后的创作
        """
        try:
            creation = await creation_crud.get(db=db, id=creation_id)
            if not creation or creation.user_id != user_id:
                return None
            
            # 更新状态为已发布
            updated_creation = await creation_crud.update(
                db=db,
                db_obj=creation,
                obj_in=ContentCreationUpdate(status="published")
            )
            
            return {
                "id": updated_creation.id,
                "title": updated_creation.title,
                "content": updated_creation.content,
                "status": updated_creation.status,
                "created_at": updated_creation.created_at.isoformat(),
                "updated_at": updated_creation.updated_at.isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"发布创作失败: {e}")
            raise

    async def generate_content(
        self,
        db: AsyncSession,
        *,
        user_id: str,
        request: ContentGenerationRequest
    ) -> Dict[str, Any]:
        """
        AI生成内容
        
        Args:
            db: 数据库会话
            user_id: 用户ID
            request: 生成请求
            
        Returns:
            生成的内容
        """
        try:
            # 获取选题信息
            topic = None
            if request.topic_id:
                from app.crud.topic import topic as topic_crud
                topic = await topic_crud.get(db=db, id=request.topic_id)
            
            # 获取风格档案
            style_features = None
            if request.style_profile_id:
                from app.crud.style import style as style_crud
                style_profile = await style_crud.get(db=db, id=request.style_profile_id)
                if style_profile:
                    style_features = style_profile.style_features
            
            # 调用AI服务生成内容
            ai_service = get_ai_service()
            
            prompt = self._build_generation_prompt(
                topic=topic,
                style_features=style_features,
                custom_prompt=request.custom_prompt,
                content_type=request.content_type
            )
            
            generated_content = await ai_service.generate_content(
                prompt=prompt,
                style=style_features
            )
            
            # 创建新创作
            creation_in = ContentCreationCreate(
                title=request.title or (f"AI生成 - {topic.title}" if topic else "AI生成内容"),
                content=generated_content,
                topic_id=request.topic_id,
                style_profile_id=request.style_profile_id,
                status="draft"
            )
            
            creation = await creation_crud.create(
                db=db, obj_in=creation_in, user_id=user_id
            )
            
            return {
                "id": creation.id,
                "title": creation.title,
                "content": creation.content,
                "status": creation.status,
                "topic_id": creation.topic_id,
                "style_profile_id": creation.style_profile_id,
                "created_at": creation.created_at.isoformat(),
                "updated_at": creation.updated_at.isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"AI生成内容失败: {e}")
            raise

    async def optimize_content(
        self,
        db: AsyncSession,
        *,
        creation_id: str,
        user_id: str,
        optimization_type: str = "general"
    ) -> Optional[Dict[str, Any]]:
        """
        AI优化内容
        
        Args:
            db: 数据库会话
            creation_id: 创作ID
            user_id: 用户ID
            optimization_type: 优化类型
            
        Returns:
            优化后的内容
        """
        try:
            creation = await creation_crud.get(db=db, id=creation_id)
            if not creation or creation.user_id != user_id:
                return None
            
            # 获取风格档案
            style_features = None
            if creation.style_profile_id:
                from app.crud.style import style as style_crud
                style_profile = await style_crud.get(db=db, id=creation.style_profile_id)
                if style_profile:
                    style_features = style_profile.style_features
            
            # 调用AI服务优化内容
            ai_service = get_ai_service()
            
            optimized_content = await ai_service.optimize_content(
                content=creation.content,
                style=style_features,
                optimization_type=optimization_type
            )
            
            # 更新创作内容
            updated_creation = await creation_crud.update(
                db=db,
                db_obj=creation,
                obj_in=ContentCreationUpdate(content=optimized_content)
            )
            
            return {
                "id": updated_creation.id,
                "title": updated_creation.title,
                "content": updated_creation.content,
                "status": updated_creation.status,
                "created_at": updated_creation.created_at.isoformat(),
                "updated_at": updated_creation.updated_at.isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"AI优化内容失败: {e}")
            raise

    def _build_generation_prompt(
        self,
        *,
        topic: Optional[Topic] = None,
        style_features: Optional[Dict[str, Any]] = None,
        custom_prompt: Optional[str] = None,
        content_type: str = "article"
    ) -> str:
        """
        构建内容生成提示词
        
        Args:
            topic: 选题信息
            style_features: 风格特征
            custom_prompt: 自定义提示词
            content_type: 内容类型
            
        Returns:
            提示词
        """
        prompt_parts = []
        
        # 基础指令
        if content_type == "article":
            prompt_parts.append("请根据以下选题，撰写一篇公众号文章。")
        elif content_type == "summary":
            prompt_parts.append("请根据以下选题，撰写一篇摘要。")
        elif content_type == "outline":
            prompt_parts.append("请根据以下选题，生成文章大纲。")
        
        # 添加选题信息
        if topic:
            prompt_parts.append(f"\n选题标题：{topic.title}")
            if topic.content_summary:
                prompt_parts.append(f"选题摘要：{topic.content_summary}")
            if topic.keywords:
                prompt_parts.append(f"关键词：{topic.keywords}")
        
        # 添加风格要求
        if style_features:
            prompt_parts.append("\n写作风格要求：")
            if "tone" in style_features:
                prompt_parts.append(f"- 语气：{style_features['tone']}")
            if "style" in style_features:
                prompt_parts.append(f"- 风格：{style_features['style']}")
            if "structure" in style_features:
                prompt_parts.append(f"- 结构：{style_features['structure']}")
        
        # 添加自定义提示词
        if custom_prompt:
            prompt_parts.append(f"\n{custom_prompt}")
        
        return "\n".join(prompt_parts)


# 创建全局创作服务实例
creation_service = CreationService()
