import json
import logging
from typing import Any, Dict, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.style import style as style_crud
from app.crud.style import style_source as source_crud
from app.models.style import StyleProfile, ArticleForAnalysis
from app.services.ai_service import ai_service

logger = logging.getLogger(__name__)

RADAR_KEYS = ['语气温度', '专业密度', '句式节奏', '情绪强度', '修辞偏好', '结构习惯']

TRAIN_SYSTEM_PROMPT = """你是一位专业的写作风格分析师。请仔细分析以下语料，提取作者的写作风格特征。

输出要求（严格 JSON，不要多余文字）：
{
  "signature": "3-5个关键词，用顿号分隔，高度概括风格，如：温暖克制、擅讲案例、节奏轻快",
  "radar": {
    "语气温度": 7.5,
    "专业密度": 6.0,
    "句式节奏": 8.0,
    "情绪强度": 5.0,
    "修辞偏好": 6.5,
    "结构习惯": 7.0
  },
  "traits": [
    {"text": "特征描述1", "primary": true},
    {"text": "特征描述2", "primary": true},
    {"text": "特征描述3", "primary": false},
    {"text": "特征描述4", "primary": false},
    {"text": "特征描述5", "primary": false},
    {"text": "特征描述6", "primary": false},
    {"text": "特征描述7", "primary": false},
    {"text": "特征描述8", "primary": false}
  ]
}

维度说明（每项 1-10 分）：
- 语气温度：1=冰冷客观，10=热情亲切
- 专业密度：1=纯口语，10=大量专业术语
- 句式节奏：1=缓慢冗长，10=短促有力
- 情绪强度：1=平静克制，10=情绪饱满
- 修辞偏好：1=平铺直叙，10=大量修辞手法
- 结构习惯：1=松散自由，10=严谨工整

traits 要求：
- 共 8 条，其中 2-3 条标记 primary: true（核心特征）
- 每条 8-20 字，描述具体风格特点
- 从用词、句式、节奏、结构、情感、修辞等维度提取"""

PREVIEW_SYSTEM_PROMPT = """你是一位资深的公众号写手。请严格模仿以下风格特征写作一段 200-350 字的内容。

风格签名：{signature}
维度评分：{radar}
风格特征：{traits}

要求：
1. 严格模仿上述风格特征
2. 围绕给定主题展开
3. 200-350 字
4. 自然流畅，不要刻意堆砌"""


class StyleService:
    """风格服务类"""

    async def get_style_profile(
        self,
        db: AsyncSession,
        *,
        style_id: int,
        user_id: int
    ) -> Optional[StyleProfile]:
        """获取风格档案"""
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
        """获取用户风格档案列表"""
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
        """创建风格档案"""
        from app.schemas.style import StyleProfileCreate

        style_data = StyleProfileCreate(
            name=name,
            description=description,
            style_features=style_features or {}
        )
        return await style_crud.create(db, obj_in=style_data, user_id=user_id)

    async def train_style(
        self,
        corpus: str,
        model: str = None
    ) -> Dict[str, Any]:
        """
        训练风格：分析语料提取风格特征
        :param corpus: 合并后的语料文本
        :param model: AI 模型
        :return: 风格训练结果
        """
        try:
            # 调用 AI 分析
            messages = [
                {"role": "system", "content": TRAIN_SYSTEM_PROMPT},
                {"role": "user", "content": f"以下是待分析的写作风格语料：\n\n{corpus[:8000]}"}
            ]

            response = await ai_service.chat(
                messages=messages,
                model=model,
                temperature=0.7,
                max_tokens=3000
            )

            # 解析 JSON
            content = response.get("content", "")
            logger.info(f"AI 训练原始返回长度: {len(content)}")
            # 提取 JSON 部分
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                content = content.split("```")[1].split("```")[0]
            content = content.strip()

            # 尝试解析；如果失败，尝试截到最后一个 } 再解一次（兜底截断的 JSON）
            try:
                result = json.loads(content)
            except json.JSONDecodeError:
                last_brace = content.rfind("}")
                if last_brace > 0:
                    salvaged = content[: last_brace + 1]
                    logger.warning(f"JSON 截断，尝试修复后再解析（保留 {len(salvaged)}/{len(content)} 字符）")
                    result = json.loads(salvaged)
                else:
                    raise

            # 验证结构
            signature = result.get("signature", "")
            radar = result.get("radar", {})
            traits = result.get("traits", [])

            # 确保 radar 包含所有维度
            for key in RADAR_KEYS:
                if key not in radar:
                    radar[key] = 5.0

            # 确保 traits 格式正确
            formatted_traits = []
            for t in traits[:8]:
                if isinstance(t, dict):
                    formatted_traits.append({
                        "text": t.get("text", ""),
                        "primary": t.get("primary", False)
                    })

            return {
                "signature": signature,
                "radar": radar,
                "traits": formatted_traits
            }

        except json.JSONDecodeError as e:
            logger.error(f"AI 返回格式错误: {e}")
            raise ValueError("AI 返回的格式不正确，请重试")
        except Exception as e:
            logger.error(f"训练风格失败: {e}")
            raise

    async def preview_style(
        self,
        profile: StyleProfile,
        topic: str,
        model: str = None
    ) -> str:
        """
        风格预览：用用户风格生成内容
        :param profile: 风格档案
        :param topic: 主题
        :param model: AI 模型
        :return: 生成的内容
        """
        try:
            # 构建提示词
            system_prompt = PREVIEW_SYSTEM_PROMPT.format(
                signature=profile.signature or "自然流畅",
                radar=json.dumps(profile.radar or {}, ensure_ascii=False),
                traits=json.dumps(profile.traits or [], ensure_ascii=False)
            )

            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"主题：{topic}"}
            ]

            response = await ai_service.chat(
                messages=messages,
                model=model,
                temperature=0.8,
                max_tokens=800
            )

            return response.get("content", "生成失败")

        except Exception as e:
            logger.error(f"风格预览失败: {e}")
            raise

    async def analyze_style(
        self,
        articles: List[ArticleForAnalysis]
    ) -> Dict[str, Any]:
        """分析文章风格"""
        try:
            article_data = []
            for article in articles:
                article_data.append({
                    "title": article.title or "无标题",
                    "content": article.content[:2000],
                    "platform": article.platform
                })
            style_features = await ai_service.analyze_style(article_data)
            return style_features
        except Exception as e:
            logger.error(f"风格分析失败: {e}")
            raise

    async def analyze_article_style(
        self,
        content: str,
        title: str = None
    ) -> Dict[str, Any]:
        """分析单篇文章风格"""
        try:
            article_data = [{
                "title": title or "无标题",
                "content": content[:2000],
                "platform": "user_input"
            }]
            style_features = await ai_service.analyze_style(article_data)
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

    async def generate_summary(
        self,
        style_features: Dict[str, Any]
    ) -> str:
        """生成风格分析摘要"""
        try:
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

    async def get_style_for_generation(
        self,
        db: AsyncSession,
        *,
        user_id: int,
        style_id: Optional[int] = None
    ) -> Optional[Dict[str, Any]]:
        """获取用于内容生成的风格信息"""
        try:
            style_profile = None
            if style_id:
                style_profile = await self.get_style_profile(db, style_id=style_id, user_id=user_id)
            else:
                style_profile = await style_crud.get_default(db, user_id=user_id)

            if not style_profile:
                return None

            # 优先使用新的训练结果
            if style_profile.signature:
                return {
                    "id": style_profile.id,
                    "name": style_profile.name,
                    "signature": style_profile.signature,
                    "radar": style_profile.radar,
                    "traits": style_profile.traits,
                    "tone": style_profile.tone or "专业",
                    "language_style": style_profile.language_style or "简洁明了",
                    "style_features": style_profile.style_features or {}
                }

            # 回退到旧字段
            return {
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
        except Exception as e:
            logger.error(f"获取风格信息失败: {e}")
            return None

    async def apply_style(
        self,
        content: str,
        style: StyleProfile
    ) -> Dict[str, Any]:
        """将风格应用到内容"""
        try:
            style_instruction = self._build_style_instruction(style)
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
        """构建风格指令"""
        instructions = []

        # 优先使用新的训练结果
        if style.signature:
            instructions.append(f"风格签名：{style.signature}")

        if style.traits:
            trait_texts = [t.get("text", "") for t in style.traits if isinstance(t, dict)]
            if trait_texts:
                instructions.append(f"风格特征：{'、'.join(trait_texts)}")

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

        return "；".join(instructions) if instructions else "保持自然流畅的写作风格"

    async def get_style_suggestions(
        self,
        user_id: int,
        db: AsyncSession
    ) -> List[Dict[str, Any]]:
        """获取风格建议"""
        try:
            user_styles = await style_crud.get_by_user(db, user_id=user_id, limit=5)
            suggestions = []

            for style in user_styles:
                if style.style_features:
                    features = style.style_features
                    if features.get("tone") == "专业" and not features.get("use_statistics"):
                        suggestions.append({
                            "type": "improvement",
                            "style_id": style.id,
                            "style_name": style.name,
                            "suggestion": "建议增加统计数据的使用，提升专业性",
                            "priority": "medium"
                        })

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

    async def compare_styles(
        self,
        style1: Dict[str, Any],
        style2: Dict[str, Any]
    ) -> Dict[str, Any]:
        """比较两种风格"""
        try:
            comparison = {
                "similarities": [],
                "differences": [],
                "recommendations": []
            }

            if style1.get("tone") == style2.get("tone"):
                comparison["similarities"].append("语气特点相似")
            else:
                comparison["differences"].append(f"语气不同：{style1.get('tone')} vs {style2.get('tone')}")

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


# 创建风格服务实例
style_service = StyleService()
