"""
Agent A - 标题创作员

角色定位: 百万粉 AI 公众号博主
核心任务: 基于选题和大纲生成10-15个标题候选，覆盖至少6种套路
"""

from typing import Dict, Any, List, Optional
import logging
from pathlib import Path

from app.services.title_generation.base import BaseAgent
from app.schemas.title_generation import TopicInfo, OutlineInfo
from app.core.config import settings

logger = logging.getLogger(__name__)

# 获取当前文件所在目录
CURRENT_DIR = Path(__file__).parent


def _load_title_methods_library() -> str:
    """从文件加载完整的标题套路库"""
    library_file = CURRENT_DIR / "assets" / "标题套路库.md"
    if library_file.exists():
        return library_file.read_text(encoding="utf-8")
    # 回退到简化版（如果文件不存在）
    return """# 标题套路库（简化版）

## 12 种标题套路

1. 痛点直击型：精准戳中读者一个真实的痛，然后承诺解决方案
2. 数字冲击型：用具体数字制造可信度和冲击感
3. 第一人称故事型：用'我'作为主语，把内容包装成一个故事
4. 反差反转型：制造预期和现实的落差，激发好奇心
5. 反共识型：唱反调，激发读者'独立思考'的认同感
6. 焦虑制造型：触发读者对职业/行业的担忧
7. 实用清单型：明确告诉读者'这里有 N 个实用的东西可以收藏'
8. 对比测评型：A vs B，替读者做决策
9. 悬念钩子型：留白，说一半藏一半，激发读者点开揭秘的欲望
10. 时间紧迫型：用时间制造稀缺感、新鲜感
11. 身份代入型：明确点名特定身份，让目标读者觉得'这就是给我看的'
12. 反向推荐型：'劝退'现有选项，推荐新选项

## 6 类修饰元素

1. 数字：具体的数字（3、5、7等奇数更佳）
2. 身份代入词：'我'、'我们'、'产品经理'等身份词
3. 反差/反预期词：'居然'、'竟然'、'没想到'、'意外'等
4. 紧迫/时效词：'刚刚'、'今天'、'昨晚'等时间词
5. 情绪词：'崩溃'、'心疼'、'离谱'、'神技'等
6. 反常识词：'其实'、'真相'、'真正的'等

## 反模式（一票否决项）

- 含"震惊""速看""所有人都不知道"等标题党词
- 涉及政治/监管敏感表达
- 攻击具体个人/团队的人身攻击性表达
- 含明显误导性的虚假承诺（"包过""保证100%"）
"""


class TitleCreatorAgent(BaseAgent):
    """
    Agent A - 标题创作员
    
    角色: 百万粉 AI 公众号博主
    任务: 生成10-15个标题候选，覆盖至少6种套路
    """
    
    def __init__(self):
        """初始化标题创作员"""
        super().__init__()
        self.agent_name = "标题创作员"
        self.agent_role = "百万粉 AI 公众号博主"
    
    async def execute(self, **kwargs) -> Dict[str, Any]:
        """
        执行标题生成任务
        
        Args:
            topic: 选题信息
            outline: 大纲信息
            feedback: 重生反馈（可选）
            
        Returns:
            包含候选标题列表的字典
        """
        topic = kwargs.get("topic")
        outline = kwargs.get("outline")
        feedback = kwargs.get("feedback")
        
        return await self.generate_titles(topic, outline, feedback)
    
    async def generate_titles(
        self,
        topic: TopicInfo,
        outline: OutlineInfo,
        feedback: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        生成标题候选

        Schema 校验失败时自动重试，最多 3 次。

        Args:
            topic: 选题信息
            outline: 大纲信息
            feedback: 重生反馈（可选）

        Returns:
            包含候选标题列表的字典
        """
        MAX_RETRIES = 3
        logger.info(f"Agent A 开始生成标题，选题: {topic.title}")

        prompt = self._build_prompt(topic, outline, feedback)
        system_prompt = self._get_system_prompt()

        last_response = ""
        for attempt in range(1, MAX_RETRIES + 1):
            extra = ""
            if attempt > 1:
                extra = (
                    "\n\n【重要】上一次输出格式不符合要求。"
                    "请严格输出 JSON，必须包含 candidates 数组，每个元素含 title、word_count、"
                    "method、modifiers、explanation 字段。不要输出 markdown 或解释文字。"
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
1. 从一条选题+大纲里生成多角度、多套路的标题候选
2. 精通12种标题套路和6类修饰元素
3. 每个标题都必须让读者在1秒内完成"三个一眼"判断

你的工作原则：
- 打开率优先于正确性
- 多候选 + 多套路 > 单候选反复打磨
- 标题必须兑现承诺
- 避免一票否决词"""
    
    def _build_prompt(
        self,
        topic: TopicInfo,
        outline: OutlineInfo,
        feedback: Optional[str] = None,
    ) -> str:
        """
        构建提示词

        Args:
            topic: 选题信息
            outline: 大纲信息
            feedback: 重生反馈

        Returns:
            完整的提示词
        """
        # 加载完整的标题套路库
        title_library = _load_title_methods_library()

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

【参考资产 - 标题套路库】
{title_library}

【你的任务】
产出 {settings.MIN_CANDIDATES}-{settings.MAX_CANDIDATES} 个标题候选，每个候选必须标注使用的套路和修饰元素。

【硬约束】
1. 候选数量 {settings.MIN_CANDIDATES}-{settings.MAX_CANDIDATES} 个
2. 必须覆盖至少 {settings.MIN_COVERAGE_METHODS} 种不同套路
3. 单一套路不超过 {settings.MAX_SAME_METHOD} 个候选
4. 优先使用该方向的优先套路（占比 ≥ {settings.PRIORITY_METHOD_RATIO * 100}%）
5. 每个标题字数 {settings.OPTIMAL_MIN_LENGTH}-{settings.OPTIMAL_MAX_LENGTH} 为最佳（{settings.MIN_TITLE_LENGTH}-{settings.OPTIMAL_MIN_LENGTH - 1} 或 {settings.OPTIMAL_MAX_LENGTH + 1}-{settings.MAX_TITLE_LENGTH} 允许但减分）
6. 不允许标题党词、敏感内容、虚假承诺
7. 文字必须真实差异，不允许"换一个字"的伪候选

【自检清单】
□ 候选数量是否在 {settings.MIN_CANDIDATES}-{settings.MAX_CANDIDATES}？
□ 是否覆盖至少 {settings.MIN_COVERAGE_METHODS} 种套路？
□ 单套路是否未超过 {settings.MAX_SAME_METHOD} 个？
□ 优先套路占比是否 ≥ {settings.PRIORITY_METHOD_RATIO * 100}%？
□ 字数是否都在 {settings.MIN_TITLE_LENGTH}-{settings.MAX_TITLE_LENGTH}？
□ 是否避免了一票否决词？
□ 每个候选是否真实差异？"""
        
        # 添加重生反馈
        if feedback:
            prompt += f"""

【第二次调用，前次失败原因】
{feedback}

【请针对性改进】
针对上述问题重新生成 {settings.MIN_CANDIDATES}-{settings.MAX_CANDIDATES} 个候选，但仍要保持套路覆盖度。"""
        
        prompt += """

【输出格式】
请严格按照以下JSON格式输出:
{
  "candidates": [
    {
      "title": "标题内容",
      "word_count": 20,
      "method": "套路名称",
      "modifiers": ["修饰元素1", "修饰元素2"],
      "explanation": "为什么这样写"
    },
    ...
  ]
}"""

        return prompt

    def _get_priority_methods(self, direction: str) -> List[str]:
        """
        获取该方向的优先套路

        Args:
            direction: 内容方向

        Returns:
            优先套路列表
        """
        # 从标题套路库中提取该方向的优先套路
        title_library = _load_title_methods_library()

        # 简单的关键词匹配
        direction_keywords = {
            "实践型": ["实践型", "实践"],
            "解决问题型": ["解决问题型", "解决问题"],
            "教程型": ["教程型", "教程"],
            "观点型": ["观点型", "观点"],
            "资讯型": ["资讯型", "资讯"],
            "整活型": ["整活型", "整活"],
        }

        keywords = direction_keywords.get(direction, [direction])
        priority_methods = []

        # 从文件内容中提取匹配的套路
        lines = title_library.split('\n')
        current_method = None
        for line in lines:
            if line.startswith('### 套路'):
                current_method = line.split(' - ')[-1].strip() if ' - ' in line else None
            elif current_method and '适用方向' in line:
                for keyword in keywords:
                    if keyword in line:
                        priority_methods.append(current_method)
                        break

        # 如果没有匹配到，返回默认的前6个套路
        if not priority_methods:
            priority_methods = [
                "痛点直击型", "数字冲击型", "第一人称故事型",
                "反差反转型", "实用清单型", "对比测评型"
            ]

        return priority_methods

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

            # 检查字数
            word_count = len(title)
            if word_count < settings.MIN_TITLE_LENGTH or word_count > settings.MAX_TITLE_LENGTH:
                logger.warning(f"标题字数不符合要求: {title} ({word_count}字)")
                continue

            # 检查一票否决词
            if self._contains_anti_pattern(title):
                logger.warning(f"标题包含一票否决词: {title}")
                continue

            # 更新字数
            candidate["word_count"] = word_count

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
        anti_patterns = ["震惊", "速看", "所有人都不知道", "保证100%", "包过"]
        
        for pattern in anti_patterns:
            if pattern in title:
                return True
        
        return False


# 导出
__all__ = ["TitleCreatorAgent"]
