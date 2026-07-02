"""
Agent A - 标题创作员

角色定位: 百万粉 AI 公众号博主
核心任务: 基于选题和大纲，按阿枫科技标题风格生成10-15个标题候选
"""

from typing import Dict, Any, List, Optional
import logging
import re
from pathlib import Path

from app.services.title_generation.base import BaseAgent
from app.schemas.title_generation import TopicInfo, OutlineInfo
from app.core.config import settings

logger = logging.getLogger(__name__)

# 获取当前文件所在目录
CURRENT_DIR = Path(__file__).parent


ANTI_PATTERNS = ["震惊", "速看", "所有人都不知道", "保证100%", "包过"]


def _load_afeng_style_library() -> str:
    """加载阿枫科技标题风格资产，用于约束 AI 科技实测类语感。"""
    style_file = CURRENT_DIR / "assets" / "阿枫科技标题风格.md"
    if style_file.exists():
        return style_file.read_text(encoding="utf-8")
    return """# 阿枫科技标题风格（简化版）

标题要像真实 AI 科技博主刚测完工具后的口语判断。
优先组合：新品/新功能 + 我测过/试过 + 反差或强情绪 + 省事低门槛收益。
高频表达：我测完、试了、用了、终于、不香了、没那么简单、真有点东西、无需部署、下载就能用。
避免新闻稿式、课程式、产品公告式标题。"""


COLON_PATTERN = re.compile(r"[：:]")


class TitleCreatorAgent(BaseAgent):
    """
    Agent A - 标题创作员

    角色: 百万粉 AI 公众号博主
    任务: 按阿枫科技标题风格生成10-15个标题候选
    """

    def __init__(self, provider: Optional[str] = None):
        """
        初始化标题创作员

        Args:
            provider: LLM provider 名称（可选，默认使用 settings.LLM_PROVIDER）
                     支持: "deepseek", "anthropic", "aigocode"
        """
        self._provider = provider
        super().__init__()
        self.agent_name = "标题创作员"
        self.agent_role = "百万粉 AI 公众号博主"

        # 如果指定了 provider，覆盖默认的 LLM client
        if provider:
            from app.services.llm import get_llm_client
            self.llm_client = get_llm_client(provider)
            logger.info(f"使用 {provider} 作为标题生成模型")
    
    async def execute(self, **kwargs) -> Dict[str, Any]:
        """
        执行标题生成任务

        Args:
            topic: 选题信息
            outline: 大纲信息
            feedback: 重生反馈（可选）
            content: 正文信息（可选）

        Returns:
            包含候选标题列表的字典
        """
        topic = kwargs.get("topic")
        outline = kwargs.get("outline")
        feedback = kwargs.get("feedback")
        content = kwargs.get("content")

        return await self.generate_titles(topic, outline, feedback, content)

    async def generate_titles(
        self,
        topic: TopicInfo,
        outline: OutlineInfo,
        feedback: Optional[str] = None,
        content: Optional[dict] = None,
        min_candidates: Optional[int] = None,
        max_candidates: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        生成标题候选

        Schema 校验失败时自动重试，最多 3 次。

        Args:
            topic: 选题信息
            outline: 大纲信息
            feedback: 重生反馈（可选）
            content: 正文内容（可选）
            min_candidates: 最小候选数量（可选，默认使用 settings.MIN_CANDIDATES）
            max_candidates: 最大候选数量（可选，默认使用 settings.MAX_CANDIDATES）

        Returns:
            包含候选标题列表的字典
        """
        MAX_RETRIES = 3
        logger.info(f"Agent A 开始生成标题，选题: {topic.title}")

        prompt = self._build_prompt(topic, outline, feedback, content, min_candidates, max_candidates)
        system_prompt = self._get_system_prompt()

        last_response = ""
        for attempt in range(1, MAX_RETRIES + 1):
            extra = ""
            if attempt > 1:
                extra = (
                    "\n\n【重要】上一次输出格式不符合要求。"
                    "请严格输出 JSON，必须包含 candidates 数组，每个元素含 title、word_count、"
                    "method、modifiers、explanation 字段。不要输出 markdown 或解释文字。"
                    "标题里不要出现中英文冒号。"
                )

            response = await self.call_ai_model(
                prompt=prompt,
                system_prompt=system_prompt + extra,
                temperature=0.8,
                json_mode=True,
            )
            last_response = response

            result = self.parse_json_response(response)
            candidates = self._validate_candidates(result.get("candidates", []))

            if candidates:
                logger.info(f"Agent A 生成了 {len(candidates)} 个候选标题（第 {attempt} 次）")
                return {
                    "candidates": candidates,
                    "raw_response": response,
                }

            logger.warning(f"Agent A 第 {attempt}/{MAX_RETRIES} 次未生成有效候选")

        logger.error(f"[Agent A] {MAX_RETRIES} 次尝试均未生成有效候选")
        return {
            "candidates": [],
            "raw_response": last_response,
        }
    
    def _get_system_prompt(self) -> str:
        """获取系统提示词"""
        prompt_file = CURRENT_DIR / "prompts" / "agent_a_system.txt"
        if prompt_file.exists():
            return prompt_file.read_text(encoding="utf-8")
        # 回退到硬编码版本
        return """你是一位百万粉的 AI 公众号博主，深谙公众号读者打开决策机制。

你的核心能力：
1. 从一条选题+大纲里生成多角度、多语气的标题候选
2. 精通阿枫科技式 AI 工具实测标题：口语、亲测、反差、强判断
3. 每个标题都必须让读者在1秒内完成"三个一眼"判断

你的工作原则：
- 打开率优先，但不能牺牲正文兑现
- 多候选 + 多角度 > 单候选反复打磨
- 标题必须兑现承诺
- 避免一票否决词和冒号清单结构"""
    
    def _build_prompt(
        self,
        topic: TopicInfo,
        outline: OutlineInfo,
        feedback: Optional[str] = None,
        content: Optional[dict] = None,
        min_candidates: Optional[int] = None,
        max_candidates: Optional[int] = None,
    ) -> str:
        """
        构建提示词

        Args:
            topic: 选题信息
            outline: 大纲信息
            feedback: 重生反馈
            content: 正文信息（可选）
            min_candidates: 最小候选数量（可选）
            max_candidates: 最大候选数量（可选）

        Returns:
            完整的提示词
        """
        # 使用传入的参数或默认值
        min_c = min_candidates or settings.MIN_CANDIDATES
        max_c = max_candidates or settings.MAX_CANDIDATES
        afeng_style_library = _load_afeng_style_library()

        # 构建正文参考部分
        content_section = ""
        if content and content.get("final_text"):
            gold = content.get("gold_sentences") or []
            gold_text = "\n".join(f"  - {s}" for s in gold) if gold else "  无"
            # 正文截取前 2000 字 + 末尾 500 字，避免 prompt 过长
            full_text = content["final_text"]
            if len(full_text) > 2500:
                truncated = full_text[:2000] + "\n\n...（正文中间省略）...\n\n" + full_text[-500:]
            else:
                truncated = full_text
            content_section = f"""

最终正文（标题生成必须参考正文内容，确保标题与正文内容一致）:
{truncated}

正文金句:
{gold_text}
"""

        prompt = f"""【输入】
选题:
- 标题（草标题）: {topic.title}
- 方向: {topic.direction}
- 套路（选题套路）: {topic.method}
- 价值承诺: {topic.value_promise}

最终大纲:
- 各节小标题: {', '.join(outline.section_titles)}
- 关键信息点: {', '.join(outline.key_points)}
- 传播标签分布: {', '.join(outline.spread_tags) if outline.spread_tags else '无'}
{content_section}

【参考资产 - 阿枫科技标题风格】
{afeng_style_library}

【你的任务】
严格按照上面的【阿枫科技标题风格】产出 {min_c}-{max_c} 个标题候选。
method 字段只用于说明你采用的表达思路，可以自由概括，不要为了凑套路而牺牲标题自然度。

【硬约束】
1. 候选数量 {min_c}-{max_c} 个
2. 文字必须真实差异，不允许"换一个字"的伪候选
3. 不允许标题党词、敏感内容、虚假承诺
4. 不要写新闻稿式、论文式、产品公告式标题；不要写"一文看懂""深度解析""全面盘点"这类泛标题
5. 标题里禁止出现中英文冒号（`：` 或 `:`）。不要写"实测：..."、"某某工具：..."、"xxx: ..."这类结构；如果需要分隔，改成逗号或一句自然口语判断

【生成前必须先在内部完成的爆点提炼】
不要输出这部分，但必须用它指导标题：
1. 旧痛点：读者以前最烦什么？
2. 新变化：这次产品/事件到底新在哪里？
3. 反差：它打破了什么预期？
4. 作者态度：测完后最强烈的判断是什么？
5. 读者收益：读者点开能少走什么弯路？

【候选强度分布】
- 稳妥版：约 30%，准确但不能像公告
- 上头版：约 40%，更口语、更有态度、更像参考账号
- 狠一点版：约 30%，更有反差和传播冲动，但必须被正文兑现
- 每个候选的 explanation 里注明强度档位，并说明命中的情绪核

【自检清单】
□ 候选数量是否在 {min_c}-{max_c}？
□ 是否避免了一票否决词？
□ 每个候选是否真实差异？
□ 是否像真实博主刚测完后的判断，而不是产品公告？
□ 标题里是否完全没有中英文冒号？"""
        
        # 添加重生反馈
        if feedback:
            prompt += f"""

【第二次调用，前次失败原因】
{feedback}

【请针对性改进】
针对上述问题重新生成 {min_c}-{max_c} 个候选，优先修正不够阿枫科技、不够口语、不够有感染力的问题。"""
        
        prompt += """

【输出格式】
请严格按照以下JSON格式输出:
{
  "candidates": [
    {
      "title": "标题内容",
      "word_count": 18,
      "method": "套路名称",
      "modifiers": ["修饰元素1", "修饰元素2"],
      "explanation": "为什么这样写"
    },
    ...
  ]
}"""

        return prompt

    def _validate_candidates(
        self,
        candidates: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """
        验证和后处理候选标题
        
        Args:
            candidates: 原始候选列表
            
        Returns:
            验证后的候选列表
        """
        validated = []

        for candidate in candidates:
            title = candidate.get("title", "")

            # 记录字数（不限制）
            word_count = len(title)

            # 检查一票否决词
            if self._contains_anti_pattern(title):
                logger.warning(f"标题包含一票否决词: {title}")
                continue

            if self._contains_colon_list_pattern(title):
                logger.warning(f"标题包含冒号结构: {title}")
                continue

            # 更新字数
            candidate["word_count"] = word_count
            candidate["method"] = (candidate.get("method") or "阿枫科技风格").strip()

            # 验证修饰元素
            modifiers = candidate.get("modifiers", [])
            if not isinstance(modifiers, list):
                modifiers = []
            candidate["modifiers"] = modifiers[:settings.MAX_MODIFIERS_PER_TITLE]

            validated.append(candidate)

        return validated
    
    def _contains_anti_pattern(self, title: str) -> bool:
        """
        检查标题是否包含一票否决词
        
        Args:
            title: 标题内容
            
        Returns:
            是否包含一票否决词
        """
        for pattern in ANTI_PATTERNS:
            if pattern in title:
                return True
        
        return False

    def _contains_colon_list_pattern(self, title: str) -> bool:
        """
        用户明确不喜欢标题中的冒号结构，因此中英文冒号都直接过滤。
        """
        return bool(COLON_PATTERN.search(title or ""))


# 导出
__all__ = ["TitleCreatorAgent", "ANTI_PATTERNS"]
