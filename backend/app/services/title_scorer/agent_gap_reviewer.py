"""
缺口评审 - 芒格版标题评分 Step 1.1

职责：信息缺口维度评分（0-10）+ 诊断
"""

from typing import Dict, Any
import logging
import re

from app.services.title_generation.base import BaseAgent

logger = logging.getLogger(__name__)


class GapReviewerAgent(BaseAgent):
    """缺口评审 - 信息缺口评分"""

    def __init__(self):
        super().__init__()
        self.agent_name = "缺口评审"
        self.agent_role = "信息缺口评审专家"

    async def execute(self, **kwargs) -> Dict[str, Any]:
        analysis = kwargs.get("analysis", {})
        title = kwargs.get("title", "")
        return await self.score_gap(analysis, title)

    async def score_gap(self, analysis: Dict[str, Any], title: str) -> Dict[str, Any]:
        """评分信息缺口"""
        analysis_text = analysis.get("raw", str(analysis))

        prompt = f"""评分标准（0-10分）：

0-2分 · 缺口为零
标题已经把结论说完，读者没有理由点进去。
例："AI Agent落地难是因为数据流转没打通"（答案已给出）

3-4分 · 方向模糊
读者既不知道话题是什么，也不知道为什么要关注。
例："一些关于AI的思考"

5-6分 · 有方向无缺口
读者知道话题但缺乏点击冲动，答案暗示太明显。
例："AI Agent的三个常见问题"

7-8分 · 方向清晰+缺口精确
具体名词给了方向，否定句或悬置句藏住了答案。
例："AI Agent项目大面积失败，原因不是你以为的那个"

9-10分 · 不可抗缺口
方向极度具体，缺口精确到让目标读者无法忽略。
例："这家公司砍掉了整个AI Agent团队，只留了一个人"

输入：
拆解报告：{analysis_text}
原始标题：{title}

输出格式：
<score>X</score>
<diagnosis>
方向感：强/中/弱（原因）
缺口程度：零/弱/中/强/不可抗（原因）
关键问题：……
</diagnosis>"""

        response = await self.call_ai_model(
            prompt=prompt,
            system_prompt=self._get_system_prompt(),
            temperature=0.3,
        )

        score = self._parse_score(response)
        diagnosis = self._parse_xml(response, "diagnosis")

        # 兜底规则：信息完整度为"完整" → 上限3分
        completeness = analysis.get("completeness", "")
        if "完整" in completeness and not "缺口" in completeness:
            score = min(score, 3)

        logger.info(f"缺口评分: {score}/10")
        return {"score": score, "diagnosis": diagnosis, "raw_response": response}

    def _get_system_prompt(self) -> str:
        return """你是标题评审专家，只负责"信息缺口"这一个维度。

评分标准（0-10分）：
0-2分 · 缺口为零
3-4分 · 方向模糊
5-6分 · 有方向无缺口
7-8分 · 方向清晰+缺口精确
9-10分 · 不可抗缺口"""

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
