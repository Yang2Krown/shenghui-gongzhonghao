"""
冲突评审 - 芒格版标题评分 Step 1.3

职责：认知冲突维度评分（0-10）+ 诊断
"""

from typing import Dict, Any
import logging
import re

from app.services.title_generation.base import BaseAgent

logger = logging.getLogger(__name__)


class ConflictReviewerAgent(BaseAgent):
    """冲突评审 - 认知冲突评分"""

    def __init__(self):
        super().__init__()
        self.agent_name = "冲突评审"
        self.agent_role = "认知冲突评审专家"

    async def execute(self, **kwargs) -> Dict[str, Any]:
        analysis = kwargs.get("analysis", {})
        title = kwargs.get("title", "")
        return await self.score_conflict(analysis, title)

    async def score_conflict(self, analysis: Dict[str, Any], title: str) -> Dict[str, Any]:
        """评分认知冲突"""
        analysis_text = analysis.get("raw", str(analysis))

        prompt = f"""评分标准（0-10分）：

0-2分 · 零冲突
标题陈述了一个读者已经知道或认同的事实，无意外感。
例："AI Agent的落地正在推进"

3-4分 · 弱冲突
有一点新意但不足以让读者停下来重新思考。
例："AI Agent的落地比想象中慢"

5-6分 · 中等冲突
挑战了一个次要假设，引发轻度好奇。
例："AI Agent最大的瓶颈不在技术层"

7-8分 · 强冲突
直接否定了目标读者对该话题最主流的假设。
例："为什么模型越强，AI应用留存率反而在下降"

9-10分 · 认知地震
提出了一个与行业共识完全相反、但有数据/事实支撑的判断。
例："大模型能力过剩正在杀死AI创业公司"

分析步骤：
1. 先推断目标读者对该话题的默认假设是什么
2. 判断标题是否挑战了这个假设
3. 评估挑战的力度

输入：
拆解报告：{analysis_text}
原始标题：{title}

输出格式：
<score>X</score>
<diagnosis>
读者默认假设：……
标题是否挑战：是/否
挑战力度：零/弱/中/强/地震级
关键问题：……
</diagnosis>"""

        response = await self.call_ai_model(
            prompt=prompt,
            system_prompt=self._get_system_prompt(),
            temperature=0.3,
        )

        score = self._parse_score(response)
        diagnosis = self._parse_xml(response, "diagnosis")

        logger.info(f"冲突评分: {score}/10")
        return {"score": score, "diagnosis": diagnosis, "raw_response": response}

    def _get_system_prompt(self) -> str:
        return """你是标题评审专家，只负责"认知冲突"这一个维度。

评分标准（0-10分）：
0-2分 · 零冲突
3-4分 · 弱冲突
5-6分 · 中等冲突
7-8分 · 强冲突
9-10分 · 认知地震"""

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
