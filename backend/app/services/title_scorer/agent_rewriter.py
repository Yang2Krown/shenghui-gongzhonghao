"""
改写 Agent - 芒格版标题评分 Step 4

职责：综合诊断 + 输出改写建议
输入：全部上游输出
输出：总分 + 诊断结论 + 2-3条改写建议
"""

from typing import Dict, Any, List, Optional
import logging
import re

from app.services.title_generation.base import BaseAgent

logger = logging.getLogger(__name__)


class RewriterAgent(BaseAgent):
    """改写 Agent - 综合诊断"""

    def __init__(self):
        super().__init__()
        self.agent_name = "改写 Agent"
        self.agent_role = "标题优化总监"

    async def execute(self, **kwargs) -> Dict[str, Any]:
        return await self.comprehensive_diagnosis(**kwargs)

    async def comprehensive_diagnosis(
        self,
        title: str,
        analysis: Dict[str, Any],
        gap_result: Dict[str, Any],
        anchor_result: Dict[str, Any],
        conflict_result: Dict[str, Any],
        enhance_result: Dict[str, Any],
        redline_result: Dict[str, Any],
    ) -> Dict[str, Any]:
        """综合诊断并输出改写建议"""
        analysis_text = analysis.get("raw", str(analysis))
        gap_score = gap_result.get("score", 5)
        gap_diag = gap_result.get("diagnosis", "")
        anchor_score = anchor_result.get("score", 5)
        anchor_diag = anchor_result.get("diagnosis", "")
        conflict_score = conflict_result.get("score", 5)
        conflict_diag = conflict_result.get("diagnosis", "")
        enhance_scores = enhance_result.get("scores", {})
        opportunities = enhance_result.get("opportunities", "")
        redline_text = redline_result.get("redlines", "")
        char_count_text = redline_result.get("char_count_text", "")
        char_ok = redline_result.get("char_ok", True)
        usable = redline_result.get("usable", True)
        named_state = redline_result.get("named_state", False)
        high_risk_r2 = redline_result.get("high_risk_r2", False)
        char_count = redline_result.get("char_count", len(title))

        # 计算总分
        total = self._calculate_total_score(
            gap_score, anchor_score, conflict_score,
            enhance_scores, usable, high_risk_r2, named_state, char_ok
        )

        # 等级
        grade, grade_label = self._get_grade(total)

        # 如果在 S 级，不强行改写
        if grade == "S":
            return {
                "total_score": total,
                "grade": grade,
                "grade_label": grade_label,
                "diagnosis": {"suggestion": "建议保留原标题，无需改写"},
                "rewrites": [],
                "raw_response": "",
            }

        # 调用 LLM 生成综合诊断和改写建议
        prompt = f"""【计分规则】
总分 = 三维度得分加权 + 增强得分加权 + 红线修正 + 命名加分

三维度（满分60分）：
  信息缺口 × 2 = {gap_score * 2}/20分
  社会位置 × 2 = {anchor_score * 2}/20分
  认知冲突 × 2 = {conflict_score * 2}/20分

增强项（满分30分）：
  联想光环 × 2 = {enhance_scores.get('联想光环', 0) * 2}/10分
  对比结构 × 2 = {enhance_scores.get('对比结构', 0) * 2}/10分
  因果承诺 × 2 = {enhance_scores.get('因果承诺', 0) * 2}/10分

红线修正：
  可用: {usable} | 高风险承诺: {high_risk_r2}
命名加分: {named_state}
字数合规: {char_ok} ({char_count}字)

当前总分: {total}/100  等级: {grade}

输入：
原始标题：{title}
拆解报告：{analysis_text}
缺口评审：{gap_diag}
锚点评审：{anchor_diag}
冲突评审：{conflict_diag}
增强机会：{opportunities}
红线结果：{redline_text}

【诊断输出】
根据各维度得分，识别：
1. 最强维度（得分最高的1-2个）
2. 最弱维度（得分最低的1-2个）
3. 最大改进机会（投入产出比最高的调整方向）

【改写建议】
基于诊断结果，输出 2-3 条改写后的标题，要求：
- 每条 ≤ 20个汉字
- 每条标注针对性修复了哪个弱项
- 保留原标题的强项不破坏
- 不得使用禁用词

输出格式：
<diagnosis>
最强维度：……
最弱维度：……
最大改进机会：……
一句话诊断：……
</diagnosis>
<rewrites>
1. 改写标题（X字）→ 修复：…… | 保留：……
2. 改写标题（X字）→ 修复：…… | 保留：……
3. 改写标题（X字）→ 修复：…… | 保留：……
</rewrites>"""

        response = await self.call_ai_model(
            prompt=prompt,
            system_prompt=self._get_system_prompt(),
            temperature=0.5,
        )

        diagnosis = self._parse_xml(response, "diagnosis")
        rewrites_text = self._parse_xml(response, "rewrites")
        rewrites = self._parse_rewrites(rewrites_text)

        logger.info(f"改写 Agent 完成，总分: {total}, 等级: {grade}")

        return {
            "total_score": total,
            "grade": grade,
            "grade_label": grade_label,
            "diagnosis": diagnosis,
            "rewrites": rewrites,
            "raw_response": response,
        }

    def _calculate_total_score(
        self,
        gap_score: float,
        anchor_score: float,
        conflict_score: float,
        enhance_scores: Dict[str, float],
        usable: bool,
        high_risk_r2: bool,
        named_state: bool,
        char_ok: bool,
    ) -> float:
        """计算总分"""
        # 三维度 (×2)
        total = gap_score * 2 + anchor_score * 2 + conflict_score * 2

        # 增强项 (×2)
        total += enhance_scores.get("联想光环", 0) * 2
        total += enhance_scores.get("对比结构", 0) * 2
        total += enhance_scores.get("因果承诺", 0) * 2

        # 红线修正
        if not usable:
            total = min(total, 30)
        if high_risk_r2:
            total -= 10

        # 命名加分
        if named_state:
            total += 10

        # 字数修正
        if not char_ok:
            total -= 15

        return max(0, min(round(total, 1), 110))

    def _get_grade(self, total: float) -> tuple:
        """获取等级"""
        if total >= 90:
            return "S", "S（90+）：拇指杀手，直接发布"
        elif total >= 75:
            return "A", "A（75-89）：高质量，微调即可"
        elif total >= 60:
            return "B", "B（60-74）：中等，有明确改进空间"
        elif total >= 40:
            return "C", "C（40-59）：及格线以下，需要重写核心结构"
        else:
            return "D", "D（0-39）：不建议使用，建议全部重写"

    def _get_system_prompt(self) -> str:
        return """你是标题优化总监。汇总所有评审结果，输出最终评分、诊断和改写建议。

根据各维度得分，识别最强维度、最弱维度、最大改进机会。
基于诊断结果输出2-3条改写后的标题，每条≤20个汉字，标注修复了哪个弱项、保留了哪个强项。"""

    def _parse_xml(self, response: str, tag: str) -> str:
        pattern = f"<{tag}>(.*?)</{tag}>"
        match = re.search(pattern, response, re.DOTALL)
        return match.group(1).strip() if match else ""

    def _parse_rewrites(self, text: str) -> List[Dict[str, str]]:
        rewrites = []
        for line in text.strip().split("\n"):
            line = line.strip()
            if line and (line[0].isdigit() or line.startswith("-")):
                title_text = re.sub(r'^[\d\.\-\s]+', '', line)
                # Extract fix note
                fix_match = re.search(r'修复[：:]\s*(.*?)(?:\s*\|\s*|$)', title_text)
                fix = fix_match.group(1).strip() if fix_match else ""
                # Extract keep note
                keep_match = re.search(r'保留[：:]\s*(.*?)$', title_text)
                keep = keep_match.group(1).strip() if keep_match else ""
                # Clean title
                title_text = re.sub(r'\s*→\s*修复[：:].*$', '', title_text).strip()
                title_text = re.sub(r'\s*\|\s*保留[：:].*$', '', title_text).strip()
                title_text = re.sub(r'（\d+字）$', '', title_text).strip()

                if title_text:
                    rewrites.append({
                        "title": title_text,
                        "fix": fix,
                        "keep": keep,
                    })
        return rewrites
