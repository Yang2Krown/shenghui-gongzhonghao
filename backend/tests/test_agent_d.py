"""
Agent D - 最终判定员 单元测试

测试覆盖:
1. 综合评分计算公式: 0.6 × B评分 + 0.4 × C点击预测
2. 自检机制: Top 3综合分 ≥ 7.0
3. 重生反馈生成
4. 推荐理由生成
"""

import pytest
from typing import Dict, Any, List

from app.agents.agent_d import FinalJudgeAgent
from app.core.config import settings
from tests.conftest import make_candidate_with_score, make_b_result, make_c_result, VALID_TOPIC, VALID_OUTLINE


class TestFinalScoreFormula:
    """测试综合评分公式"""

    def setup_method(self):
        self.agent = FinalJudgeAgent.__new__(FinalJudgeAgent)

    def test_formula_weights(self):
        """配置权重应为B=0.6, C=0.4"""
        assert settings.B_SCORE_WEIGHT == 0.6
        assert settings.C_SCORE_WEIGHT == 0.4

    def test_formula_sum_equals_1(self):
        """B和C权重之和应为1.0"""
        assert abs(settings.B_SCORE_WEIGHT + settings.C_SCORE_WEIGHT - 1.0) < 0.001

    def test_pass_threshold(self):
        """通过门槛应为7.0"""
        assert settings.PASS_THRESHOLD == 7.0


class TestGenerateSingleReason:
    """测试单个候选推荐理由生成"""

    def setup_method(self):
        self.agent = FinalJudgeAgent.__new__(FinalJudgeAgent)

    def test_high_score_strong_recommend(self):
        """高分(>=9)应生成强烈推荐"""
        candidate = {
            "title": "测试标题",
            "method": "痛点直击型",
            "b_score": 9.0,
            "c_click_willingness": 9,
            "final_score": 9.0,
            "b_score_details": {
                "three_eyes": 9,
                "emotion_trigger": 9,
                "specificity": 9,
                "outline_consistency": 9,
            },
            "c_click_reason": "反差感强",
        }
        reason = self.agent._generate_single_reason(candidate, 1, VALID_TOPIC, VALID_OUTLINE)
        assert "强烈推荐" in reason
        assert "痛点直击型" in reason

    def test_medium_score_recommend(self):
        """中等分数(>=8)应生成推荐"""
        candidate = {
            "title": "测试标题",
            "method": "数字冲击型",
            "b_score": 8.0,
            "c_click_willingness": 8,
            "final_score": 8.0,
            "b_score_details": {
                "three_eyes": 7,
                "emotion_trigger": 7,
                "specificity": 7,
                "outline_consistency": 7,
            },
            "c_click_reason": "",
        }
        reason = self.agent._generate_single_reason(candidate, 2, VALID_TOPIC, VALID_OUTLINE)
        assert "推荐" in reason

    def test_low_score_optional(self):
        """低分(<8)应生成可选"""
        candidate = {
            "title": "测试标题",
            "method": "反共识型",
            "b_score": 6.0,
            "c_click_willingness": 6,
            "final_score": 6.0,
            "b_score_details": {
                "three_eyes": 5,
                "emotion_trigger": 5,
                "specificity": 5,
                "outline_consistency": 5,
            },
            "c_click_reason": "",
        }
        reason = self.agent._generate_single_reason(candidate, 3, VALID_TOPIC, VALID_OUTLINE)
        assert "可选" in reason

    def test_strengths_included(self):
        """高分维度应被包含在优势描述中"""
        candidate = {
            "title": "测试标题",
            "method": "痛点直击型",
            "b_score": 9.0,
            "c_click_willingness": 9,
            "final_score": 9.0,
            "b_score_details": {
                "three_eyes": 9,
                "emotion_trigger": 9,
                "specificity": 9,
                "outline_consistency": 9,
            },
            "c_click_reason": "反差感强+数字冲击",
        }
        reason = self.agent._generate_single_reason(candidate, 1, VALID_TOPIC, VALID_OUTLINE)
        assert "三个一眼达标度高" in reason
        assert "情绪触发力度强" in reason
        assert "具体元素丰富" in reason

    def test_reader_feedback_included(self):
        """读者反馈应被包含在理由中"""
        candidate = {
            "title": "测试标题",
            "method": "痛点直击型",
            "b_score": 8.0,
            "c_click_willingness": 8,
            "final_score": 8.0,
            "b_score_details": {},
            "c_click_reason": "反差感很强，想点开看",
        }
        reason = self.agent._generate_single_reason(candidate, 1, VALID_TOPIC, VALID_OUTLINE)
        assert "读者反馈" in reason


class TestGenerateFeedback:
    """测试重生反馈生成"""

    def setup_method(self):
        self.agent = FinalJudgeAgent.__new__(FinalJudgeAgent)

    def test_feedback_contains_threshold(self):
        """反馈应包含门槛值信息"""
        recommendations = [{
            "title": "测试标题",
            "final_score": 5.0,
            "b_score_details": {
                "three_eyes": 5,
                "emotion_trigger": 5,
                "specificity": 5,
                "outline_consistency": 5,
            },
            "c_click_willingness": 5,
            "c_no_click_reason": "",
            "c_improvement_suggestion": "",
        }]
        feedback = self.agent._generate_feedback(recommendations, VALID_TOPIC, VALID_OUTLINE)
        assert "7.0" in feedback

    def test_feedback_for_low_three_eyes(self):
        """低三个一眼分数应有对应反馈"""
        recommendations = [{
            "title": "测试标题",
            "final_score": 5.0,
            "b_score_details": {
                "three_eyes": 5,
                "emotion_trigger": 8,
                "specificity": 8,
                "outline_consistency": 8,
            },
            "c_click_willingness": 8,
            "c_no_click_reason": "",
            "c_improvement_suggestion": "",
        }]
        feedback = self.agent._generate_feedback(recommendations, VALID_TOPIC, VALID_OUTLINE)
        assert "三个一眼" in feedback

    def test_feedback_for_low_emotion(self):
        """低情绪触发分数应有对应反馈"""
        recommendations = [{
            "title": "测试标题",
            "final_score": 5.0,
            "b_score_details": {
                "three_eyes": 8,
                "emotion_trigger": 5,
                "specificity": 8,
                "outline_consistency": 8,
            },
            "c_click_willingness": 8,
            "c_no_click_reason": "",
            "c_improvement_suggestion": "",
        }]
        feedback = self.agent._generate_feedback(recommendations, VALID_TOPIC, VALID_OUTLINE)
        assert "情绪触发" in feedback

    def test_feedback_for_low_click_willingness(self):
        """低点击意愿应有对应反馈"""
        recommendations = [{
            "title": "测试标题",
            "final_score": 5.0,
            "b_score_details": {
                "three_eyes": 8,
                "emotion_trigger": 8,
                "specificity": 8,
                "outline_consistency": 8,
            },
            "c_click_willingness": 4,
            "c_no_click_reason": "感觉无聊",
            "c_improvement_suggestion": "加点反差",
        }]
        feedback = self.agent._generate_feedback(recommendations, VALID_TOPIC, VALID_OUTLINE)
        assert "点击意愿" in feedback
        assert "感觉无聊" in feedback

    def test_feedback_contains_improvement_guidelines(self):
        """反馈应包含改进建议"""
        recommendations = [{
            "title": "测试标题",
            "final_score": 5.0,
            "b_score_details": {
                "three_eyes": 5,
                "emotion_trigger": 5,
                "specificity": 5,
                "outline_consistency": 5,
            },
            "c_click_willingness": 5,
            "c_no_click_reason": "",
            "c_improvement_suggestion": "",
        }]
        feedback = self.agent._generate_feedback(recommendations, VALID_TOPIC, VALID_OUTLINE)
        assert "情绪触发" in feedback
        assert "具体元素" in feedback


class TestSelfCheckMechanism:
    """测试自检机制"""

    def test_all_above_threshold_passes(self):
        """所有Top3分数>=7.0应通过"""
        scores = [7.0, 8.0, 9.0]
        passed = all(s >= settings.PASS_THRESHOLD for s in scores)
        assert passed is True

    def test_one_below_threshold_fails(self):
        """任一Top3分数<7.0应失败"""
        scores = [7.0, 6.5, 9.0]
        passed = all(s >= settings.PASS_THRESHOLD for s in scores)
        assert passed is False

    def test_exact_threshold_passes(self):
        """恰好7.0应通过"""
        scores = [7.0, 7.0, 7.0]
        passed = all(s >= settings.PASS_THRESHOLD for s in scores)
        assert passed is True

    def test_just_below_threshold_fails(self):
        """6.99应失败"""
        scores = [7.0, 6.99, 7.0]
        passed = all(s >= settings.PASS_THRESHOLD for s in scores)
        assert passed is False


class TestRecommendationGeneration:
    """测试推荐理由生成"""

    def setup_method(self):
        self.agent = FinalJudgeAgent.__new__(FinalJudgeAgent)

    def test_generates_3_recommendations(self):
        """应生成3条推荐"""
        top3 = [
            make_candidate_with_score("c1", 9.0),
            make_candidate_with_score("c2", 8.5),
            make_candidate_with_score("c3", 8.0),
        ]
        for c in top3:
            c["c_click_willingness"] = 8
            c["c_click_reason"] = "吸引人"
            c["final_score"] = c["b_score"] * 0.6 + 8 * 0.4

        result = self.agent._generate_recommendations(top3, VALID_TOPIC, VALID_OUTLINE)
        assert len(result) == 3

    def test_recommendation_has_reason(self):
        """每条推荐应有推荐理由"""
        top3 = [make_candidate_with_score("c1", 9.0)]
        top3[0]["c_click_willingness"] = 8
        top3[0]["c_click_reason"] = ""
        top3[0]["final_score"] = 8.6

        result = self.agent._generate_recommendations(top3, VALID_TOPIC, VALID_OUTLINE)
        assert "recommendation_reason" in result[0]
        assert len(result[0]["recommendation_reason"]) > 0
