"""
红线 Agent - 芒格版标题评分 Step 3

职责：合规审查 + 字数校验
"""

from typing import Dict, Any
import logging
import re

from app.services.title_generation.base import BaseAgent

logger = logging.getLogger(__name__)


class RedlineAgent(BaseAgent):
    """红线 Agent - 合规审查"""

    def __init__(self):
        super().__init__()
        self.agent_name = "红线 Agent"
        self.agent_role = "标题合规审查官"

    async def execute(self, **kwargs) -> Dict[str, Any]:
        analysis = kwargs.get("analysis", {})
        title = kwargs.get("title", "")
        return await self.check_redlines(analysis, title)

    async def check_redlines(self, analysis: Dict[str, Any], title: str) -> Dict[str, Any]:
        """执行红线审查"""
        analysis_text = analysis.get("raw", str(analysis))

        prompt = f"""【红线 1 · 焦虑贩卖】
检测标志：制造恐慌而非提供认知增量
"你的同龄人正在抛弃你""再不学就晚了""X岁还不会Y"
判定：通过 / 未通过

【红线 2 · 承诺兑现风险】
评估标题的承诺强度，判断是否有"标题党"风险。
极端承诺（"所有""永远""唯一""从不"）天然高风险。
判定：通过 / 高风险 / 未通过

【红线 3 · 操控词】
检测词库："震惊""必看""颠覆""重磅""突发""刚刚"
"不转不是中国人""99%的人不知道"
判定：通过 / 未通过

【红线 4 · 命名未被命名的状态】（加分项）
标题是否给了读者"有感觉但说不出来"的某种处境一个精准的名字？
这是最高级的标题技巧——如果命中，额外加分。
判定：未命中 / 命中（+说明）

【字数校验】
精确计算汉字+标点总数，判定是否 ≤ 25。

输入：
拆解报告：{analysis_text}
原始标题：{title}

输出格式：
<redlines>
红线1 焦虑贩卖：通过/未通过（原因）
红线2 承诺兑现：通过/高风险/未通过（原因）
红线3 操控词：通过/未通过（检出词：……）
红线4 命名状态：未命中/命中（说明）
</redlines>
<char_count>X字 → ✓ 通过 / ✗ 超限</char_count>"""

        response = await self.call_ai_model(
            prompt=prompt,
            system_prompt=self._get_system_prompt(),
            temperature=0.3,
        )

        redlines = self._parse_xml(response, "redlines")
        char_count = self._parse_xml(response, "char_count")

        # Parse individual checks
        passed_r1 = "未通过" not in (self._extract_check(redlines, "红线1") or "")
        passed_r2 = "未通过" not in (self._extract_check(redlines, "红线2") or "")
        passed_r3 = "未通过" not in (self._extract_check(redlines, "红线3") or "")
        named_state = "命中" in (self._extract_check(redlines, "红线4") or "")

        char_ok = "✓" in char_count or "通过" in char_count
        char_number = self._extract_char_count(char_count)

        any_redline_failed = not (passed_r1 and passed_r3)
        high_risk_r2 = "高风险" in (self._extract_check(redlines, "红线2") or "")

        usable = not any_redline_failed

        logger.info(f"红线审查完成，可用: {usable}")
        return {
            "redlines": redlines,
            "char_count_text": char_count,
            "char_count": char_number,
            "char_ok": char_ok,
            "passed_r1": passed_r1,
            "passed_r2": passed_r2,
            "passed_r3": passed_r3,
            "named_state": named_state,
            "high_risk_r2": high_risk_r2,
            "usable": usable,
            "raw_response": response,
        }

    def _get_system_prompt(self) -> str:
        return """你是标题合规审查官，对科技/AI行业读者群体执行四条红线检查和字数校验。

【红线 1 · 焦虑贩卖】判定：通过 / 未通过
【红线 2 · 承诺兑现风险】判定：通过 / 高风险 / 未通过
【红线 3 · 操控词】判定：通过 / 未通过
【红线 4 · 命名未被命名的状态】（加分项）判定：未命中 / 命中
【字数校验】精确计算汉字+标点总数，判定是否 ≤ 25。"""

    def _parse_xml(self, response: str, tag: str) -> str:
        pattern = f"<{tag}>(.*?)</{tag}>"
        match = re.search(pattern, response, re.DOTALL)
        return match.group(1).strip() if match else ""

    def _extract_check(self, text: str, line_start: str) -> str:
        for line in text.split("\n"):
            if line.strip().startswith(line_start):
                return line.strip()
        return ""

    def _extract_char_count(self, text: str) -> int:
        match = re.search(r"(\d+)字", text)
        return int(match.group(1)) if match else 0
