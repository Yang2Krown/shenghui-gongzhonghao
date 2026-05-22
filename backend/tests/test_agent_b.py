"""
Agent B - 标题评审员 单元测试

测试覆盖:
1. 一票否决扫描
2. 6维度评分权重验证
3. 加权总分计算
4. Top 5筛选逻辑
"""

import pytest
from typing import Dict, Any, List

from app.agents.agent_b import TitleReviewerAgent, SCORE_WEIGHTS, VETO_CONDITIONS
from app.core.config import settings
from tests.conftest import make_candidate, make_candidates


class TestScoreWeights:
    """测试6维度评分权重配置"""

    def test_weight_sum_equals_1(self):
        """权重总和应等于1.0"""
        total = sum(SCORE_WEIGHTS.values())
        assert abs(total - 1.0) < 0.001, f"权重总和{total}不等于1.0"

    def test_weight_values_match_design(self):
        """权重值应与设计文档一致"""
        assert SCORE_WEIGHTS["three_eyes"] == 0.25
        assert SCORE_WEIGHTS["emotion_trigger"] == 0.20
        assert SCORE_WEIGHTS["specificity"] == 0.15
        assert SCORE_WEIGHTS["length_compliance"] == 0.10
        assert SCORE_WEIGHTS["method_maturity"] == 0.15
        assert SCORE_WEIGHTS["outline_consistency"] == 0.15

    def test_6_dimensions_defined(self):
        """应定义6个评分维度"""
        assert len(SCORE_WEIGHTS) == 6


class TestVetoConditions:
    """测试一票否决条件"""

    def test_5_veto_conditions(self):
        """应定义5个一票否决条件"""
        assert len(VETO_CONDITIONS) == 5

    def test_conditions_match_design(self):
        """条件应与设计文档一致"""
        conditions_text = " ".join(VETO_CONDITIONS)
        assert "标题党词" in conditions_text
        assert "政治" in conditions_text
        assert "人身攻击" in conditions_text
        assert "虚假承诺" in conditions_text
        assert "字数" in conditions_text


class TestCheckVetoWords:
    """测试一票否决词检测"""

    def setup_method(self):
        self.agent = TitleReviewerAgent.__new__(TitleReviewerAgent)

    def test_clickbait_zhenjing(self):
        """应检测到标题党词'震惊'"""
        result = self.agent._check_veto_words("震惊！这个工具太厉害了")
        assert "标题党词" in result
        assert "震惊" in result

    def test_clickbait_sukan(self):
        """应检测到标题党词'速看'"""
        result = self.agent._check_veto_words("速看！最新消息")
        assert "标题党词" in result

    def test_clickbait_bikan(self):
        """应检测到标题党词'必看'"""
        result = self.agent._check_veto_words("必看！AI最新动态")
        assert "标题党词" in result

    def test_false_promise_100(self):
        """应检测到虚假承诺'保证100%'"""
        result = self.agent._check_veto_words("保证100%有效的方法")
        assert "虚假承诺" in result

    def test_false_promise_baokuo(self):
        """应检测到虚假承诺'包过'"""
        result = self.agent._check_veto_words("包过！考试必过秘诀")
        assert "虚假承诺" in result

    def test_political_word(self):
        """应检测到政治敏感词"""
        result = self.agent._check_veto_words("关于政府政策的AI应用")
        assert "政治敏感" in result

    def test_clean_title_returns_empty(self):
        """正常标题应返回空字符串"""
        result = self.agent._check_veto_words("用了一周Claude Goal的体验")
        assert result == ""

    def test_empty_title_returns_empty(self):
        """空标题应返回空字符串"""
        result = self.agent._check_veto_words("")
        assert result == ""


class TestVetoScan:
    """测试一票否决扫描流程"""

    def setup_method(self):
        self.agent = TitleReviewerAgent.__new__(TitleReviewerAgent)

    def test_normal_candidates_survive(self):
        """正常候选应存活"""
        candidates = [
            make_candidate("c1", "用了一周Claude Goal的体验", 14),
            make_candidate("c2", "Claude的7个隐藏用法", 11),
        ]
        eliminated, survived = self.agent._veto_scan(candidates)
        assert len(survived) == 2
        assert len(eliminated) == 0

    def test_short_title_eliminated(self):
        """过短标题应被淘汰"""
        candidates = [
            make_candidate("c1", "AI助手", 3),  # < 10字
            make_candidate("c2", "用了一周Claude Goal的体验", 14),
        ]
        eliminated, survived = self.agent._veto_scan(candidates)
        assert len(eliminated) == 1
        assert len(survived) == 1
        assert "字数" in eliminated[0]["elimination_reason"]

    def test_long_title_eliminated(self):
        """过长标题应被淘汰"""
        candidates = [
            make_candidate("c1", "这是一个非常非常非常非常非常非常非常非常长的标题用来测试字数限制", 30),  # > 22字
        ]
        eliminated, survived = self.agent._veto_scan(candidates)
        assert len(eliminated) == 1
        assert len(survived) == 0

    def test_clickbait_eliminated(self):
        """标题党词应被淘汰"""
        candidates = [
            make_candidate("c1", "震惊！这个AI工具太厉害了啊", 15),
            make_candidate("c2", "用了一周Claude Goal的体验", 14),
        ]
        eliminated, survived = self.agent._veto_scan(candidates)
        assert len(eliminated) == 1
        assert "标题党词" in eliminated[0]["elimination_reason"]

    def test_mixed_candidates(self):
        """混合候选：合法+短标题+标题党"""
        candidates = [
            make_candidate("c1", "用了一周Claude Goal的体验", 14),
            make_candidate("c2", "太短", 2),
            make_candidate("c3", "震惊！AI大变天了啊哈哈", 12),
            make_candidate("c4", "Claude的7个隐藏用法", 11),
        ]
        eliminated, survived = self.agent._veto_scan(candidates)
        assert len(eliminated) == 2
        assert len(survived) == 2

    def test_all_eliminated(self):
        """所有候选被否决时应返回空存活列表"""
        candidates = [
            make_candidate("c1", "震惊！太厉害", 7),
            make_candidate("c2", "速看！最新消息来了啊", 11),
        ]
        eliminated, survived = self.agent._veto_scan(candidates)
        assert len(survived) == 0
        assert len(eliminated) == 2

    def test_boundary_length_10_survives(self):
        """恰好10字的标题应存活"""
        candidates = [
            make_candidate("c1", "一二三四五六七八九十", 10),
        ]
        eliminated, survived = self.agent._veto_scan(candidates)
        assert len(survived) == 1

    def test_boundary_length_22_survives(self):
        """恰好22字的标题应存活"""
        title_22 = "一二三四五六七八九十一二三四五六七八九十一二"  # 22字
        candidates = [
            make_candidate("c1", title_22, 22),
        ]
        eliminated, survived = self.agent._veto_scan(candidates)
        assert len(survived) == 1

    def test_boundary_length_9_eliminated(self):
        """9字标题应被淘汰"""
        candidates = [
            make_candidate("c1", "一二三四五六七八九", 9),
        ]
        eliminated, survived = self.agent._veto_scan(candidates)
        assert len(eliminated) == 1

    def test_boundary_length_23_eliminated(self):
        """23字标题应被淘汰"""
        title_23 = "一二三四五六七八九十一二三四五六七八九十一二三"  # 23字
        candidates = [
            make_candidate("c1", title_23, 23),
        ]
        eliminated, survived = self.agent._veto_scan(candidates)
        assert len(eliminated) == 1


class TestCalculateWeightedScore:
    """测试加权总分计算"""

    def setup_method(self):
        self.agent = TitleReviewerAgent.__new__(TitleReviewerAgent)

    def test_perfect_score(self):
        """全10分应得到10分"""
        score_data = {
            "three_eyes": 10,
            "emotion_trigger": 10,
            "specificity": 10,
            "length_compliance": 10,
            "method_maturity": 10,
            "outline_consistency": 10,
        }
        result = self.agent._calculate_weighted_score(score_data)
        assert result == 10.0

    def test_zero_score(self):
        """全0分应得到0分"""
        score_data = {
            "three_eyes": 0,
            "emotion_trigger": 0,
            "specificity": 0,
            "length_compliance": 0,
            "method_maturity": 0,
            "outline_consistency": 0,
        }
        result = self.agent._calculate_weighted_score(score_data)
        assert result == 0.0

    def test_weighted_calculation(self):
        """验证加权计算公式正确"""
        score_data = {
            "three_eyes": 8,       # 8 * 0.25 = 2.0
            "emotion_trigger": 7,   # 7 * 0.20 = 1.4
            "specificity": 9,       # 9 * 0.15 = 1.35
            "length_compliance": 10, # 10 * 0.10 = 1.0
            "method_maturity": 8,   # 8 * 0.15 = 1.2
            "outline_consistency": 9, # 9 * 0.15 = 1.35
        }
        expected = 2.0 + 1.4 + 1.35 + 1.0 + 1.2 + 1.35  # = 8.3
        result = self.agent._calculate_weighted_score(score_data)
        assert abs(result - expected) < 0.01

    def test_missing_dimension_defaults_to_5(self):
        """缺失维度应默认为5分"""
        score_data = {
            "three_eyes": 10,
            # 缺失其他维度
        }
        result = self.agent._calculate_weighted_score(score_data)
        # 10*0.25 + 5*0.20 + 5*0.15 + 5*0.10 + 5*0.15 + 5*0.15
        expected = 2.5 + 1.0 + 0.75 + 0.5 + 0.75 + 0.75  # = 6.25
        assert abs(result - expected) < 0.01

    def test_three_eyes_has_highest_weight(self):
        """三个一眼应有最高权重"""
        max_weight_key = max(SCORE_WEIGHTS, key=SCORE_WEIGHTS.get)
        assert max_weight_key == "three_eyes"


class TestSelectTop5:
    """测试Top 5筛选逻辑"""

    def setup_method(self):
        self.agent = TitleReviewerAgent.__new__(TitleReviewerAgent)

    def test_selects_top_5_from_10(self):
        """从10个候选中选出Top 5"""
        candidates = [
            {"id": f"c{i}", "b_score": float(i)} for i in range(10)
        ]
        top5 = self.agent._select_top5(candidates)
        assert len(top5) == 5
        # 应该是分数最高的5个
        assert top5[0]["b_score"] == 9.0
        assert top5[4]["b_score"] == 5.0

    def test_sorted_descending(self):
        """结果应按分数降序排列"""
        candidates = [
            {"id": "c1", "b_score": 5.0},
            {"id": "c2", "b_score": 9.0},
            {"id": "c3", "b_score": 7.0},
            {"id": "c4", "b_score": 8.0},
            {"id": "c5", "b_score": 6.0},
        ]
        top5 = self.agent._select_top5(candidates)
        scores = [c["b_score"] for c in top5]
        assert scores == sorted(scores, reverse=True)

    def test_fewer_than_5_returns_all(self):
        """少于5个候选时返回全部"""
        candidates = [
            {"id": f"c{i}", "b_score": float(i)} for i in range(3)
        ]
        top5 = self.agent._select_top5(candidates)
        assert len(top5) == 3

    def test_empty_list(self):
        """空列表应返回空结果"""
        top5 = self.agent._select_top5([])
        assert len(top5) == 0

    def test_exactly_5_returns_all(self):
        """恰好5个候选时返回全部"""
        candidates = [
            {"id": f"c{i}", "b_score": float(i)} for i in range(5)
        ]
        top5 = self.agent._select_top5(candidates)
        assert len(top5) == 5
