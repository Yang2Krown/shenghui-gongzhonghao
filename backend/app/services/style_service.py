import logging
from typing import Any, Dict, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.style import style as style_crud
from app.crud.article import article as article_crud
from app.models.style import StyleProfile, ArticleForAnalysis
from app.services.ai_service import ai_service

logger = logging.getLogger(__name__)


class StyleService:
    """风格服务类"""
    
    async def get_style_profile(
        self,
        db: AsyncSession,
        *,
        style_id: int,
        user_id: int
    ) -> Optional[StyleProfile]:
        """
        获取风格档案
        :param db: 数据库会话
        :param style_id: 风格档案ID
        :param user_id: 用户ID
        :return: 风格档案或None
        """
        style_profile = await style_crud.get(db, id=style_id)
        
        if not style_profile or style_profile.user_id != user_id:
            return None
        
        return style_profile
    
    async def get_user_styles(
        self,
        db: AsyncSession,
        *,
        user_id: int,
        skip: int = 0,
        limit: int = 100
    ) -> List[StyleProfile]:
        """
        获取用户风格档案列表
        :param db: 数据库会话
        :param user_id: 用户ID
        :param skip: 跳过记录数
        :param limit: 限制记录数
        :return: 风格档案列表
        """
        return await style_crud.get_by_user(
            db,
            user_id=user_id,
            skip=skip,
            limit=limit
        )
    
    async def create_style_profile(
        self,
        db: AsyncSession,
        *,
        user_id: int,
        name: str,
        description: Optional[str] = None,
        style_features: Optional[Dict[str, Any]] = None
    ) -> StyleProfile:
        """
        创建风格档案
        :param db: 数据库会话
        :param user_id: 用户ID
        :param name: 风格名称
        :param description: 风格描述
        :param style_features: 风格特征
        :return: 创建的风格档案
        """
        from app.schemas.style import StyleProfileCreate
        
        style_data = StyleProfileCreate(
            name=name,
            description=description,
            style_features=style_features or {}
        )
        
        return await style_crud.create(db, obj_in=style_data, user_id=user_id)
    
    async def analyze_style(
        self,
        articles: List[ArticleForAnalysis]
    ) -> Dict[str, Any]:
        """
        分析文章风格
        :param articles: 文章列表
        :return: 风格特征
        """
        try:
            # 准备文章数据
            article_data = []
            for article in articles:
                article_data.append({
                    "title": article.title or "无标题",
                    "content": article.content[:2000],  # 限制长度
                    "platform": article.platform
                })
            
            # 调用AI服务分析风格
            style_features = await ai_service.analyze_style(article_data)
            
            # 标记文章为已处理
            for article in articles:
                await article_crud.mark_as_processed(db=None, db_obj=article)
            
            return style_features
            
        except Exception as e:
            logger.error(f"风格分析失败: {e}")
            raise
    
    async def analyze_and_update_style(
        self,
        db: AsyncSession,
        *,
        style_id: int,
        user_id: int,
        article_ids: List[int]
    ) -> StyleProfile:
        """
        分析并更新风格档案
        :param db: 数据库会话
        :param style_id: 风格档案ID
        :param user_id: 用户ID
        :param article_ids: 文章ID列表
        :return: 更新后的风格档案
        """
        try:
            # 获取风格档案
            style_profile = await self.get_style_profile(
                db,
                style_id=style_id,
                user_id=user_id
            )
            
            if not style_profile:
                raise ValueError("风格档案不存在")
            
            # 获取文章
            articles = await article_crud.get_by_ids(
                db,
                article_ids=article_ids,
                user_id=user_id
            )
            
            if not articles:
                raise ValueError("未找到指定的文章")
            
            # 分析风格
            style_features = await self.analyze_style(articles)
            
            # 更新风格档案
            updated_style = await style_crud.update_features(
                db,
                db_obj=style_profile,
                features=style_features
            )
            
            return updated_style
            
        except Exception as e:
            logger.error(f"风格分析更新失败: {e}")
            raise
    
    async def get_style_for_generation(
        self,
        db: AsyncSession,
        *,
        user_id: int,
        style_id: Optional[int] = None
    ) -> Optional[Dict[str, Any]]:
        """
        获取用于内容生成的风格信息
        :param db: 数据库会话
        :param user_id: 用户ID
        :param style_id: 风格档案ID（可选）
        :return: 风格信息字典
        """
        try:
            style_profile = None
            
            if style_id:
                # 获取指定风格档案
                style_profile = await self.get_style_profile(
                    db,
                    style_id=style_id,
                    user_id=user_id
                )
            else:
                # 获取默认风格档案
                style_profile = await style_crud.get_default(db, user_id=user_id)
            
            if not style_profile:
                return None
            
            # 构建风格信息
            style_info = {
                "id": style_profile.id,
                "name": style_profile.name,
                "tone": style_profile.tone or "专业",
                "language_style": style_profile.language_style or "简洁明了",
                "sentence_structure": style_profile.sentence_structure or "多样化",
                "vocabulary_level": style_profile.vocabulary_level or "中等",
                "paragraph_length": style_profile.paragraph_length or "中等",
                "use_emoji": style_profile.use_emoji,
                "use_questions": style_profile.use_questions,
                "use_statistics": style_profile.use_statistics,
                "style_features": style_profile.style_features or {}
            }
            
            return style_info
            
        except Exception as e:
            logger.error(f"获取风格信息失败: {e}")
            return None
    
    async def generate_summary(
        self,
        style_features: Dict[str, Any]
    ) -> str:
        """
        生成风格分析摘要
        :param style_features: 风格特征
        :return: 分析摘要
        """
        try:
            # 构建摘要
            summary_parts = []
            
            if "tone" in style_features:
                summary_parts.append(f"语气特点：{style_features['tone']}")
            
            if "language_style" in style_features:
                summary_parts.append(f"语言风格：{style_features['language_style']}")
            
            if "sentence_structure" in style_features:
                summary_parts.append(f"句式结构：{style_features['sentence_structure']}")
            
            if "common_words" in style_features:
                words = ", ".join(style_features["common_words"][:5])
                summary_parts.append(f"常用词汇：{words}")
            
            if "paragraph_length" in style_features:
                summary_parts.append(f"段落长度：{style_features['paragraph_length']}")
            
            if not summary_parts:
                return "风格分析完成，未发现明显特征。"
            
            return "风格分析结果：" + "；".join(summary_parts) + "。"
            
        except Exception as e:
            logger.error(f"生成风格摘要失败: {e}")
            return "风格分析完成。"
    
    async def compare_styles(
        self,
        style1: Dict[str, Any],
        style2: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        比较两种风格
        :param style1: 风格1
        :param style2: 风格2
        :return: 比较结果
        """
        try:
            comparison = {
                "similarities": [],
                "differences": [],
                "recommendations": []
            }
            
            # 比较语气
            if style1.get("tone") == style2.get("tone"):
                comparison["similarities"].append("语气特点相似")
            else:
                comparison["differences"].append(f"语气不同：{style1.get('tone')} vs {style2.get('tone')}")
            
            # 比较语言风格
            if style1.get("language_style") == style2.get("language_style"):
                comparison["similarities"].append("语言风格相似")
            else:
                comparison["differences"].append(f"语言风格不同：{style1.get('language_style')} vs {style2.get('language_style')}")
            
            # 比较常用词汇
            words1 = set(style1.get("common_words", []))
            words2 = set(style2.get("common_words", []))
            common_words = words1.intersection(words2)
            
            if common_words:
                comparison["similarities"].append(f"有{len(common_words)}个共同常用词汇")
            
            if len(comparison["similarities"]) > len(comparison["differences"]):
                comparison["recommendations"].append("两种风格较为相似，可以融合使用")
            else:
                comparison["recommendations"].append("两种风格差异较大，建议选择主要风格")
            
            return comparison
            
        except Exception as e:
            logger.error(f"风格比较失败: {e}")
            return {"similarities": [], "differences": [], "recommendations": []}

    async def analyze_article_style(
        self,
        content: str,
        title: str = None
    ) -> Dict[str, Any]:
        """
        分析单篇文章风格
        :param content: 文章内容
        :param title: 文章标题
        :return: 风格分析结果
        """
        try:
            # 准备文章数据
            article_data = [{
                "title": title or "无标题",
                "content": content[:2000],  # 限制长度
                "platform": "user_input"
            }]
            
            # 调用AI服务分析风格
            style_features = await ai_service.analyze_style(article_data)
            
            # 生成摘要
            summary = await self.generate_summary(style_features)
            
            return {
                "style_features": style_features,
                "summary": summary,
                "title": title,
                "word_count": len(content)
            }
            
        except Exception as e:
            logger.error(f"文章风格分析失败: {e}")
            raise

    async def get_style_suggestions(
        self,
        user_id: int,
        db: AsyncSession
    ) -> List[Dict[str, Any]]:
        """
        获取风格建议
        :param user_id: 用户ID
        :param db: 数据库会话
        :return: 风格建议列表
        """
        try:
            # 获取用户现有风格档案
            user_styles = await style_crud.get_by_user(db, user_id=user_id, limit=5)
            
            suggestions = []
            
            # 基于现有风格提供建议
            for style in user_styles:
                if style.style_features:
                    # 分析风格特征
                    features = style.style_features
                    
                    if features.get("tone") == "专业" and not features.get("use_statistics"):
                        suggestions.append({
                            "type": "improvement",
                            "style_id": style.id,
                            "style_name": style.name,
                            "suggestion": "建议增加统计数据的使用，提升专业性",
                            "priority": "medium"
                        })
                    
                    if features.get("language_style") == "简洁" and features.get("paragraph_length") == "长":
                        suggestions.append({
                            "type": "consistency",
                            "style_id": style.id,
                            "style_name": style.name,
                            "suggestion": "简洁风格与长段落可能存在冲突，建议调整",
                            "priority": "high"
                        })
            
            # 通用建议
            if len(user_styles) < 3:
                suggestions.append({
                    "type": "new_style",
                    "suggestion": "建议创建更多风格档案，适应不同场景",
                    "priority": "low"
                })
            
            return suggestions
            
        except Exception as e:
            logger.error(f"获取风格建议失败: {e}")
            return []

    async def apply_style(
        self,
        content: str,
        style: StyleProfile
    ) -> Dict[str, Any]:
        """
        将风格应用到内容
        :param content: 原始内容
        :param style: 风格档案
        :return: 应用风格后的内容
        """
        try:
            # 构建风格指令
            style_instruction = self._build_style_instruction(style)
            
            # 调用AI服务应用风格
            result = await ai_service.apply_style_to_content(
                content=content,
                style_instruction=style_instruction
            )
            
            return {
                "original_content": content,
                "styled_content": result,
                "style_name": style.name,
                "style_id": style.id
            }
            
        except Exception as e:
            logger.error(f"应用风格失败: {e}")
            raise

    def _build_style_instruction(self, style: StyleProfile) -> str:
        """
        构建风格指令
        :param style: 风格档案
        :return: 风格指令字符串
        """
        instructions = []
        
        if style.tone:
            instructions.append(f"语气：{style.tone}")
        
        if style.language_style:
            instructions.append(f"语言风格：{style.language_style}")
        
        if style.sentence_structure:
            instructions.append(f"句式结构：{style.sentence_structure}")
        
        if style.vocabulary_level:
            instructions.append(f"词汇水平：{style.vocabulary_level}")
        
        if style.paragraph_length:
            instructions.append(f"段落长度：{style.paragraph_length}")
        
        if style.use_emoji:
            instructions.append("适当使用表情符号")
        
        if style.use_questions:
            instructions.append("使用反问句增强互动")
        
        if style.use_statistics:
            instructions.append("引用数据和统计")
        
        if style.style_features:
            features = style.style_features
            if "common_words" in features:
                words = ", ".join(features["common_words"][:5])
                instructions.append(f"常用词汇：{words}")
        
        return "；".join(instructions) if instructions else "保持自然流畅的写作风格"


# 创建风格服务实例
style_service = StyleService()