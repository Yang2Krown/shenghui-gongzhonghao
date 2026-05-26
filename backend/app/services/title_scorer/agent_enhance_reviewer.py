"""
增强评审 - 芒格版标题评分 Step 2

职责：芒格倾向评分（三条各0-5）+ 增强机会识别
"""

from typing import Dict, Any
import logging
import re

from app.services.title_generation.base import BaseAgent

logger = logging.getLogger(__name__)


class EnhanceReviewerAgent(BaseAgent):
    """增强评审 - 芒格倾向评分"""

    def __init__(self):
        super().__init__()
        self.agent_name = "增强评审"
        self.agent_role = "芒格倾向评估专家"

    async def execute(self, **kwargs) -> Dict[str, Any]:
        analysis = kwargs.get("analysis", {})
        title = kwargs.get("title", "")
        return await self.score_enhancement(analysis, title)

    async def score_enhancement(self, analysis: Dict[str, Any], title: str) -> Dict[str, Any]:
        """评分芒格倾向"""
        analysis_text = analysis.get("raw", str(analysis))
        word_count = self._extract_word_count(analysis_text, title)

        prompt = f"""【A 联想光环】0-5分
0分：无任何高势能名字
1-2分：有名字但势能不够或与话题关联弱
3-4分：有高势能名字且自然融入
5分：大名字+小语气，完美平衡

【B 对比结构】0-5分
0分：无对比
1-2分：有对比但两端落差不够或超出想象力射程
3-4分：有效对比，两端都在读者代入范围
5分：方向相反的极端对比（小的赢了大的）

【C 因果承诺】0-5分
0分：无因果结构
1-2分：暗示了原因但不明确
3-4分：明确的因果承诺（为什么/原因是/问题出在）
5分：因果承诺+挑战了读者原有的因果模型

同时识别增强机会：
- 如果某项为 0-2 分，判断能否通过微调补上
- 给出具体的增强方向（不写完整标题，留给改写 Agent）

输入：
拆解报告：{analysis_text}
原始标题：{title}

输出格式：
<scores>
联想光环：X/5（原因）
对比结构：X/5（原因）
因果承诺：X/5（原因）
</scores>
<opportunities>
可增强项：联想/对比/因果
增强方向：……
</opportunities>"""

        response = await self.call_ai_model(
            prompt=prompt,
            system_prompt=self._get_system_prompt(),
            temperature=0.3,
        )

        scores = self._parse_scores(response)
        opportunities = self._parse_xml(response, "opportunities")

        # 兜底规则：标题≥18字，标注字数余量不足
        if word_count >= 18:
            opportunities += "\n字数余量不足，慎加"

        logger.info(f"增强评分: {scores}")
        return {"scores": scores, "opportunities": opportunities, "raw_response": response}

    def _get_system_prompt(self) -> str:
        return """你是标题评审专家，负责评估三条芒格心理倾向的利用程度。

【A 联想光环】0-5分
【B 对比结构】0-5分
【C 因果承诺】0-5分

同时识别增强机会：如果某项为0-2分，判断能否通过微调补上，给出具体增强方向。"""

    def _parse_scores(self, response: str) -> Dict[str, float]:
        scores = {}
        patterns = {
            "联想光环": r"联想光环[：:]\s*([\d.]+)/5",
            "对比结构": r"对比结构[：:]\s*([\d.]+)/5",
            "因果承诺": r"因果承诺[：:]\s*([\d.]+)/5",
        }
        for key, pattern in patterns.items():
            match = re.search(pattern, response)
            if match:
                scores[key] = min(max(float(match.group(1)), 0), 5)
            else:
                scores[key] = 0
        return scores

    def _parse_xml(self, response: str, tag: str) -> str:
        pattern = f"<{tag}>(.*?)</{tag}>"
        match = re.search(pattern, response, re.DOTALL)
        return match.group(1).strip() if match else ""

    def _extract_word_count(self, analysis: str, title: str) -> int:
        pattern = r"字数[：:]\s*(\d+)"
        match = re.search(pattern, analysis)
        if match:
            return int(match.group(1))
        return len(title)
