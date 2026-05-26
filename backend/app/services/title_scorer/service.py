"""
芒格版标题评分 - 编排服务

实现 7 Agent 协作流程：
Step 0: 拆解 Agent - 结构化解读
Step 1: 缺口/锚点/冲突 并行 - 三维度评分
Step 2: 增强评审 - 芒格倾向评分
Step 3: 红线 Agent - 合规审查
Step 4: 改写 Agent - 综合诊断 + 改写建议
"""

import logging
from typing import Dict, Any, Optional, Callable
from datetime import datetime

from app.services.title_scorer.agent_analyzer import AnalyzerAgent
from app.services.title_scorer.agent_gap_reviewer import GapReviewerAgent
from app.services.title_scorer.agent_anchor_reviewer import AnchorReviewerAgent
from app.services.title_scorer.agent_conflict_reviewer import ConflictReviewerAgent
from app.services.title_scorer.agent_enhance_reviewer import EnhanceReviewerAgent
from app.services.title_scorer.agent_redline import RedlineAgent
from app.services.title_scorer.agent_rewriter import RewriterAgent

logger = logging.getLogger(__name__)


class TitleScorerService:
    """
    芒格版标题评分编排服务

    流程:
    Step 0: 拆解 Agent - 结构化解读
    Step 1: 缺口/锚点/冲突 并行评分
    Step 2: 增强评审 - 芒格倾向评分
    Step 3: 红线 Agent - 合规审查 + 字数
    Step 4: 改写 Agent - 综合诊断 + 改写建议
    """

    def __init__(self, progress_callback: Optional[Callable] = None):
        self.progress_callback = progress_callback
        self.analyzer = AnalyzerAgent()
        self.gap_reviewer = GapReviewerAgent()
        self.anchor_reviewer = AnchorReviewerAgent()
        self.conflict_reviewer = ConflictReviewerAgent()
        self.enhance_reviewer = EnhanceReviewerAgent()
        self.redline = RedlineAgent()
        self.rewriter = RewriterAgent()

    async def score(self, title: str, summary: Optional[str] = None) -> Dict[str, Any]:
        """
        执行完整的标题评分流程

        Args:
            title: 标题内容
            summary: 文章摘要（可选）

        Returns:
            评分结果
        """
        start_time = datetime.now()

        await self._notify({"event": "step_start", "data": {
            "step": 1, "agent": "拆解 Agent", "action": "正在结构化解读标题...",
        }})

        # Step 0: 拆解 Agent
        analysis_result = await self.analyzer.analyze(title, summary)
        if "error" in analysis_result:
            await self._notify({"event": "error", "data": {"message": analysis_result["error"]}})
            return {
                "success": False,
                "error": analysis_result["error"],
            }

        analysis = analysis_result.get("analysis", {})
        await self._notify({"event": "step_done", "data": {"step": 1, "agent": "拆解 Agent"}})

        # Step 2: 三维度并行评分
        await self._notify({"event": "step_start", "data": {
            "step": 2, "agent": "缺口评审", "action": "正在评分信息缺口...",
        }})
        gap_result = await self.gap_reviewer.score_gap(analysis, title)
        await self._notify({"event": "step_done", "data": {"step": 2, "agent": "缺口评审"}})

        await self._notify({"event": "step_start", "data": {
            "step": 2, "agent": "锚点评审", "action": "正在评分社会位置...",
        }})
        anchor_result = await self.anchor_reviewer.score_anchor(analysis, title)
        await self._notify({"event": "step_done", "data": {"step": 2, "agent": "锚点评审"}})

        await self._notify({"event": "step_start", "data": {
            "step": 2, "agent": "冲突评审", "action": "正在评分认知冲突...",
        }})
        conflict_result = await self.conflict_reviewer.score_conflict(analysis, title)
        await self._notify({"event": "step_done", "data": {"step": 2, "agent": "冲突评审"}})

        # Step 3: 增强评审
        await self._notify({"event": "step_start", "data": {
            "step": 3, "agent": "增强评审", "action": "正在评估芒格倾向...",
        }})
        enhance_result = await self.enhance_reviewer.score_enhancement(analysis, title)
        await self._notify({"event": "step_done", "data": {"step": 3, "agent": "增强评审"}})

        # Step 4: 红线审查
        await self._notify({"event": "step_start", "data": {
            "step": 4, "agent": "红线 Agent", "action": "正在合规审查...",
        }})
        redline_result = await self.redline.check_redlines(analysis, title)
        await self._notify({"event": "step_done", "data": {"step": 4, "agent": "红线 Agent"}})

        # Step 5: 改写 Agent（综合诊断）
        await self._notify({"event": "step_start", "data": {
            "step": 5, "agent": "改写 Agent", "action": "正在综合诊断并生成改写建议...",
        }})
        rewrite_result = await self.rewriter.comprehensive_diagnosis(
            title=title,
            analysis=analysis,
            gap_result=gap_result,
            anchor_result=anchor_result,
            conflict_result=conflict_result,
            enhance_result=enhance_result,
            redline_result=redline_result,
        )
        await self._notify({"event": "step_done", "data": {"step": 5, "agent": "改写 Agent"}})

        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()

        await self._notify({"event": "complete", "data": {"step": 5, "agent": "改写 Agent"}})

        return {
            "success": True,
            "title": title,
            "analysis": analysis,
            "scores": {
                "gap": {"score": gap_result.get("score", 0), "diagnosis": gap_result.get("diagnosis", "")},
                "anchor": {"score": anchor_result.get("score", 0), "diagnosis": anchor_result.get("diagnosis", "")},
                "conflict": {"score": conflict_result.get("score", 0), "diagnosis": conflict_result.get("diagnosis", "")},
                "enhancement": enhance_result.get("scores", {}),
                "enhance_opportunities": enhance_result.get("opportunities", ""),
            },
            "redlines": {
                "r1": redline_result.get("passed_r1", False),
                "r2": redline_result.get("passed_r2", False),
                "r3": redline_result.get("passed_r3", False),
                "r4_named_state": redline_result.get("named_state", False),
                "usable": redline_result.get("usable", False),
                "high_risk_r2": redline_result.get("high_risk_r2", False),
                "char_count": redline_result.get("char_count", 0),
                "char_ok": redline_result.get("char_ok", True),
                "raw_redlines": redline_result.get("redlines", ""),
            },
            "total_score": rewrite_result.get("total_score", 0),
            "grade": rewrite_result.get("grade", "D"),
            "grade_label": rewrite_result.get("grade_label", ""),
            "diagnosis": rewrite_result.get("diagnosis", {}),
            "rewrites": rewrite_result.get("rewrites", []),
            "duration_seconds": duration,
        }

    async def _notify(self, event: dict):
        """推送进度事件"""
        if self.progress_callback:
            await self.progress_callback(event)
