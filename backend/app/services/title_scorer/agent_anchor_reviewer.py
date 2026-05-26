"""
锚点评审 - 芒格版标题评分 Step 1.2

职责：社会位置维度评分（0-10）+ 诊断
"""

from typing import Dict, Any
import logging
import re

from app.services.title_generation.base import BaseAgent

logger = logging.getLogger(__name__)


class AnchorReviewerAgent(BaseAgent):
    """锚点评审 - 社会位置评分"""

    def __init__(self):
        super().__init__()
        self.agent_name = "锚点评审"
        self.agent_role = "社会位置评审专家"

    async def execute(self, **kwargs) -> Dict[str, Any]:
        analysis = kwargs.get("analysis", {})
        title = kwargs.get("title", "")
        return await self.score_anchor(analysis, title)

    async def score_anchor(self, analysis: Dict[str, Any], title: str) -> Dict[str, Any]:
        """评分社会位置锚点"""
        analysis_text = analysis.get("raw", str(analysis))

        prompt = f"""评分标准（0-10分）：

0-2分 · 无锚点
标题没有任何身份指向，任何人看了都觉得"跟我无关"。
例："AI的未来发展趋势"

3-4分 · 泛锚点
指向了人群但太宽泛，无法产生"被点名"的感觉。
例："每个人都该了解的AI趋势"

5-6分 · 隐性锚点
没有直接点名，但话题本身自然筛选了读者。
例："RAG的检索精度还能怎么提？"（隐性锚定AI工程师）

7-8分 · 精确锚点
明确点名了一个群体，窄到产生"说的就是我"的感觉，
又宽到让相邻群体也觉得相关。
例："做AI Agent的团队请注意"

9-10分 · 身份+处境双锚
不仅点名了群体，还精确描述了他们正在经历的处境。
例："刚上线Agent就被用户骂的团队，看看这个"

输入：
拆解报告：{analysis_text}
原始标题：{title}
目标读者：科技/AI行业从业者

输出格式：
<score>X</score>
<diagnosis>
锚点类型：无/职业/行为/处境/双锚
锚点精度：过窄/精确/过宽/无
目标人群识别：……
关键问题：……
</diagnosis>"""

        response = await self.call_ai_model(
            prompt=prompt,
            system_prompt=self._get_system_prompt(),
            temperature=0.3,
        )

        score = self._parse_score(response)
        diagnosis = self._parse_xml(response, "diagnosis")

        logger.info(f"锚点评分: {score}/10")
        return {"score": score, "diagnosis": diagnosis, "raw_response": response}

    def _get_system_prompt(self) -> str:
        return """你是标题评审专家，只负责"社会位置"这一个维度。

评分标准（0-10分）：
0-2分 · 无锚点
3-4分 · 泛锚点
5-6分 · 隐性锚点
7-8分 · 精确锚点
9-10分 · 身份+处境双锚"""

    def _parse_score(self, response: str) -> float:
        pattern = r"<score>\s*([\d.]+)\s*</score>"
        match = re.search(pattern, response)
        if match:
            return min(max(float(match.group(1)), 0), 10)
        return 5.0

    def _parse_xml(self, response: str, tag: str) -> str:
        pattern = f"<{tag}>(.*?)</{tag}>"
        match = re.search(pattern, response, re.DOTALL)
        return match.group(1).strip() if match else ""
