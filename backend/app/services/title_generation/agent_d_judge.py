"""
Agent D - 最终判定员

角色定位: 综合决策者
核心任务: 综合Agent B评分 + Agent C点击预测，输出Top 3推荐标题
"""

from typing import Dict, Any, List
import logging

from app.services.title_generation.base import BaseAgent
from app.schemas.title_generation import TopicInfo, OutlineInfo
from app.core.config import settings

logger = logging.getLogger(__name__)


class FinalJudgeAgent(BaseAgent):
    """
    Agent D - 最终判定员
    
    角色: 综合决策者
    任务: 综合评分，输出Top 3推荐标题
    """
    
    def __init__(self):
        """初始化最终判定员"""
        super().__init__()
        self.agent_name = "最终判定员"
        self.agent_role = "综合决策者"
    
    async def execute(self, **kwargs) -> Dict[str, Any]:
        """
        执行最终判定任务
        
        Args:
            b_result: Agent B的评审结果
            c_result: Agent C的点击预测结果
            topic: 选题信息
            outline: 大纲信息
            
        Returns:
            最终判定结果
        """
        b_result = kwargs.get("b_result", {})
        c_result = kwargs.get("c_result", {})
        topic = kwargs.get("topic")
        outline = kwargs.get("outline")
        
        return await self.judge_titles(b_result, c_result, topic, outline)
    
    async def judge_titles(
        self,
        b_result: Dict[str, Any],
        c_result: Dict[str, Any],
        topic: TopicInfo,
        outline: OutlineInfo,
    ) -> Dict[str, Any]:
        """
        最终判定
        
        执行流程:
        1. 综合Agent B评分 + Agent C点击预测
        2. 计算综合评分: 0.6 × B评分 + 0.4 × C点击预测
        3. 输出Top 3推荐标题
        4. 自检: Top 3综合分 ≥ 7.0 ?
        
        Args:
            b_result: Agent B的评审结果
            c_result: Agent C的点击预测结果
            topic: 选题信息
            outline: 大纲信息
            
        Returns:
            最终判定结果
        """
        logger.info("Agent D 开始最终判定")
        
        # 获取Top 5候选
        top5 = b_result.get("top5", [])
        if not top5:
            logger.error("没有Top 5候选")
            return {
                "passed": False,
                "recommendations": [],
                "need_regeneration": True,
                "feedback": "没有Top 5候选，无法进行最终判定",
            }
        
        # 获取点击预测（多维度索引：candidate_id → title）
        predictions = c_result.get("predictions", [])
        predictions_by_id = {}
        predictions_by_title = {}
        for p in predictions:
            cid = p.get("candidate_id", "")
            if cid:
                predictions_by_id[str(cid)] = p
            t = (p.get("title") or p.get("original_title") or "").strip()
            if t:
                predictions_by_title[t] = p

        # 计算综合评分
        scored_candidates = []
        for candidate in top5:
            candidate_id = str(candidate.get("id", ""))
            title = (candidate.get("title") or "").strip()
            b_score = candidate.get("b_score", 0) or 0

            # 获取点击预测（优先 id，其次 title）
            prediction = (
                predictions_by_id.get(candidate_id)
                or predictions_by_title.get(title)
                or {}
            )
            c_click = prediction.get("click_willingness", 5)
            
            # 计算综合评分: 0.6 × B评分 + 0.4 × C点击预测
            final_score = (
                settings.B_SCORE_WEIGHT * b_score +
                settings.C_SCORE_WEIGHT * c_click
            )
            
            scored_candidates.append({
                **candidate,
                "c_click_willingness": c_click,
                "c_click_reason": prediction.get("click_reason", ""),
                "c_no_click_reason": prediction.get("no_click_reason", ""),
                "c_improvement_suggestion": prediction.get("improvement_suggestion", ""),
                "final_score": round(final_score, 2),
            })
        
        # 按综合评分降序排序
        sorted_candidates = sorted(
            scored_candidates,
            key=lambda x: x.get("final_score", 0),
            reverse=True,
        )
        
        # 取Top 3
        top3 = sorted_candidates[:3]
        
        # 生成推荐理由
        recommendations = self._generate_recommendations(top3, topic, outline)
        
        # 自检: Top 3综合分 ≥ 7.0 ?
        self_check_passed = all(
            rec.get("final_score", 0) >= settings.PASS_THRESHOLD
            for rec in recommendations
        )
        
        # 如果未通过，生成反馈
        need_regeneration = not self_check_passed
        feedback = ""
        if need_regeneration:
            feedback = self._generate_feedback(recommendations, topic, outline)
        
        logger.info(f"Agent D 判定完成，通过: {self_check_passed}")
        
        return {
            "passed": self_check_passed,
            "recommendations": recommendations,
            "need_regeneration": need_regeneration,
            "feedback": feedback,
            "self_check_details": {
                "threshold": settings.PASS_THRESHOLD,
                "top3_scores": [rec.get("final_score", 0) for rec in recommendations],
                "all_passed": self_check_passed,
            },
        }
    
    def _generate_recommendations(
        self,
        top3: List[Dict[str, Any]],
        topic: TopicInfo,
        outline: OutlineInfo,
    ) -> List[Dict[str, Any]]:
        """
        生成推荐理由
        
        Args:
            top3: Top 3候选列表
            topic: 选题信息
            outline: 大纲信息
            
        Returns:
            带推荐理由的Top 3列表
        """
        recommendations = []
        
        for i, candidate in enumerate(top3):
            # 生成推荐理由
            reason = self._generate_single_reason(candidate, i + 1, topic, outline)
            
            recommendations.append({
                **candidate,
                "recommendation_reason": reason,
            })
        
        return recommendations
    
    def _generate_single_reason(
        self,
        candidate: Dict[str, Any],
        rank: int,
        topic: TopicInfo,
        outline: OutlineInfo,
    ) -> str:
        """
        生成单个候选的推荐理由
        
        Args:
            candidate: 候选数据
            rank: 排名
            topic: 选题信息
            outline: 大纲信息
            
        Returns:
            推荐理由
        """
        title = candidate.get("title", "")
        method = candidate.get("method", "")
        b_score = candidate.get("b_score", 0)
        c_click = candidate.get("c_click_willingness", 0)
        final_score = candidate.get("final_score", 0)
        
        # 分析优势
        strengths = []
        
        b_details = candidate.get("b_score_details", {})
        if b_details.get("three_eyes", 0) >= 8:
            strengths.append("三个一眼达标度高")
        if b_details.get("emotion_trigger", 0) >= 8:
            strengths.append("情绪触发力度强")
        if b_details.get("specificity", 0) >= 8:
            strengths.append("具体元素丰富")
        if b_details.get("outline_consistency", 0) >= 8:
            strengths.append("与大纲承诺完美匹配")
        
        c_reason = candidate.get("c_click_reason", "")
        if c_reason:
            strengths.append(f"读者反馈: {c_reason[:50]}")
        
        # 构建推荐理由
        reason = f"排名{rank}: "
        
        if final_score >= 9:
            reason += "强烈推荐。"
        elif final_score >= 8:
            reason += "推荐。"
        else:
            reason += "可选。"
        
        if strengths:
            reason += f"优势: {'、'.join(strengths[:3])}。"
        
        reason += f"套路: {method}，综合评分: {final_score}。"
        
        return reason
    
    def _generate_feedback(
        self,
        recommendations: List[Dict[str, Any]],
        topic: TopicInfo,
        outline: OutlineInfo,
    ) -> str:
        """
        生成重生反馈
        
        Args:
            recommendations: 推荐列表（未通过）
            topic: 选题信息
            outline: 大纲信息
            
        Returns:
            反馈内容
        """
        feedback_parts = ["前次生成的Top 3标题综合评分未达到7.0门槛，具体问题:"]
        
        for i, rec in enumerate(recommendations):
            title = rec.get("title", "")
            final_score = rec.get("final_score", 0)
            
            feedback_parts.append(f"\n{i+1}. {title} (综合评分: {final_score})")
            
            # 分析扣分原因
            b_details = rec.get("b_score_details", {})
            if b_details.get("three_eyes", 0) < 7:
                feedback_parts.append("   - 三个一眼达标度不足，需要让读者更快理解内容价值")
            if b_details.get("emotion_trigger", 0) < 7:
                feedback_parts.append("   - 情绪触发力度弱，需要增加焦虑/好奇/共鸣/反差等情绪元素")
            if b_details.get("specificity", 0) < 7:
                feedback_parts.append("   - 具体性不足，需要增加数字、工具名、身份等具体元素")
            if b_details.get("outline_consistency", 0) < 7:
                feedback_parts.append("   - 与大纲一致性差，标题承诺无法被大纲兑现")
            
            c_click = rec.get("c_click_willingness", 0)
            if c_click < 7:
                c_no_click = rec.get("c_no_click_reason", "")
                feedback_parts.append(f"   - 读者点击意愿低({c_click}/10): {c_no_click}")
                c_suggestion = rec.get("c_improvement_suggestion", "")
                if c_suggestion:
                    feedback_parts.append(f"   - 改进建议: {c_suggestion}")
        
        feedback_parts.append("\n请针对上述问题重新生成标题，确保:")
        feedback_parts.append("1. 强化三个一眼，让读者1秒内理解价值")
        feedback_parts.append("2. 增加情绪触发元素（焦虑/好奇/共鸣/反差）")
        feedback_parts.append("3. 增加具体元素（数字/工具名/身份/场景）")
        feedback_parts.append("4. 确保标题承诺能被大纲兑现")
        
        return "\n".join(feedback_parts)


# 导出
__all__ = ["FinalJudgeAgent"]
