"""
Agent B - 标题评审员 单元测试

测试覆盖:
1. 一票否决扫描
2. 8维度评分权重验证
3. 加权总分计算
4. Top 5筛选逻辑
"""

import pytest
from typing import Dict, Any, List

from app.services.title_generation.agent_b_reviewer import TitleReviewerAgent, SCORE_WEIGHTS, VETO_CONDITIONS
from app.core.config import settings
from tests.conftest import make_candidate, make_candidates


class TestScoreWeights:
    """测试8维度评分权重配置"""

    def test_weight_sum_equals_1(self):
        """权重总和应等于1.0"""
        total = sum(SCORE_WEIGHTS.values())
        assert abs(total - 1.0) < 0.001, f"权重总和{total}不等于1.0"

    def test_weight_values_match_design(self):
        """权重值应与设计文档一致"""
        assert SCORE_WEIGHTS["three_eyes"] == 0.17
        assert SCORE_WEIGHTS["emotion_trigger"] == 0.18
        assert SCORE_WEIGHTS["infectiousness"] == 0.16
        assert SCORE_WEIGHTS["afeng_style_fit"] == 0.14
        assert SCORE_WEIGHTS["specificity"] == 0.12
        assert SCORE_WEIGHTS["outline_consistency"] == 0.13
        assert SCORE_WEIGHTS["method_maturity"] == 0.06
        assert SCORE_WEIGHTS["length_compliance"] == 0.04

    def test_8_dimensions_defined(self):
        """应定义8个评分维度"""
        assert len(SCORE_WEIGHTS) == 8


class TestVetoConditions:
    """测试一票否决条件"""

    def test_5_veto_conditions(self):
        """应定义5个一票否决条件，长度交给评分维度处理"""
        assert len(VETO_CONDITIONS) == 5

    def test_conditions_match_design(self):
        """条件应与设计文档一致"""
        conditions_text = " ".join(VETO_CONDITIONS)
        assert "标题党词" in conditions_text
        assert "政治" in conditions_text
        assert "人身攻击" in conditions_text
        assert "虚假承诺" in conditions_text
        assert "冒号" in conditions_text


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

    def test_colon_feature_list_rejected(self):
        """冒号后堆功能点结构应被否决"""
        result = self.agent._check_veto_words("腾讯Marvis实测：OS操控、本地隐私、远程控制")
        assert "冒号" in result

    def test_single_colon_without_list_rejected(self):
        """单个冒号也应否决"""
        result = self.agent._check_veto_words("真实病例测评4款AI：搜索不等于临床思维")
        assert "冒号" in result

    def test_user_reported_colon_title_rejected(self):
        """用户反馈的实测冒号结构应否决"""
        result = self.agent._check_veto_words("QoderWork终于来了，实测：它居然会自己检查自己改")
        assert "冒号" in result

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

    def test_short_title_survives_veto_scan(self):
        """过短标题不做一票否决，交给长度合规评分降权"""
        candidates = [
            make_candidate("c1", "AI助手", 3),  # < 10字
            make_candidate("c2", "用了一周Claude Goal的体验", 14),
        ]
        eliminated, survived = self.agent._veto_scan(candidates)
        assert len(eliminated) == 0
        assert len(survived) == 2

    def test_long_title_survives_veto_scan(self):
        """过长标题不做一票否决，交给长度合规评分降权"""
        candidates = [
            make_candidate("c1", "这是一个非常非常非常非常非常非常非常非常长的标题用来测试字数限制", 30),  # > 22字
        ]
        eliminated, survived = self.agent._veto_scan(candidates)
        assert len(eliminated) == 0
        assert len(survived) == 1

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
        """混合候选：合法+短标题+标题党，只有标题党被一票否决"""
        candidates = [
            make_candidate("c1", "用了一周Claude Goal的体验", 14),
            make_candidate("c2", "太短", 2),
            make_candidate("c3", "震惊！AI大变天了啊哈哈", 12),
            make_candidate("c4", "Claude的7个隐藏用法", 11),
        ]
        eliminated, survived = self.agent._veto_scan(candidates)
        assert len(eliminated) == 1
        assert len(survived) == 3

    def test_all_eliminated(self):
        """所有候选被否决时应返回空存活列表"""
        candidates = [
            make_candidate("c1", "震惊！太厉害", 7),
            make_candidate("c2", "速看！最新消息来了啊", 11),
        ]
        eliminated, survived = self.agent._veto_scan(candidates)
        assert len(survived) == 0
        assert len(eliminated) == 2

    def test_colon_feature_list_eliminated(self):
        """冒号后堆多个功能点的标题应被淘汰"""
        candidates = [
            make_candidate("c1", "腾讯Marvis实测：OS操控、本地隐私、远程控制", 24),
            make_candidate("c2", "腾讯Marvis实测，终于有点贾维斯那味了", 21),
        ]
        eliminated, survived = self.agent._veto_scan(candidates)
        assert len(eliminated) == 1
        assert len(survived) == 1
        assert "冒号" in eliminated[0]["elimination_reason"]

    def test_single_colon_eliminated(self):
        """单个冒号结构也应被淘汰"""
        candidates = [
            make_candidate("c1", "QoderWork终于来了，实测：它居然会自己检查自己改", 28),
            make_candidate("c2", "QoderWork终于来了，它居然会自己检查自己改", 25),
        ]
        eliminated, survived = self.agent._veto_scan(candidates)
        assert len(eliminated) == 1
        assert len(survived) == 1
        assert "冒号" in eliminated[0]["elimination_reason"]

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

    def test_boundary_length_9_survives_veto_scan(self):
        """9字标题不做一票否决"""
        candidates = [
            make_candidate("c1", "一二三四五六七八九", 9),
        ]
        eliminated, survived = self.agent._veto_scan(candidates)
        assert len(eliminated) == 0
        assert len(survived) == 1

    def test_boundary_length_23_survives_veto_scan(self):
        """23字标题处于参考账号常见区间，不做一票否决"""
        title_23 = "一二三四五六七八九十一二三四五六七八九十一二三"  # 23字
        candidates = [
            make_candidate("c1", title_23, 23),
        ]
        eliminated, survived = self.agent._veto_scan(candidates)
        assert len(eliminated) == 0
        assert len(survived) == 1


class TestCalculateWeightedScore:
    """测试加权总分计算"""

    def setup_method(self):
        self.agent = TitleReviewerAgent.__new__(TitleReviewerAgent)

    def test_perfect_score(self):
        """全10分应得到10分"""
        score_data = {
            "three_eyes": 10,
            "emotion_trigger": 10,
            "infectiousness": 10,
            "afeng_style_fit": 10,
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
            "infectiousness": 0,
            "afeng_style_fit": 0,
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
            "three_eyes": 8,       # 8 * 0.17 = 1.36
            "emotion_trigger": 7,   # 7 * 0.18 = 1.26
            "infectiousness": 8,   # 8 * 0.16 = 1.28
            "afeng_style_fit": 8,   # 8 * 0.14 = 1.12
            "specificity": 9,       # 9 * 0.12 = 1.08
            "outline_consistency": 9, # 9 * 0.13 = 1.17
            "method_maturity": 8,   # 8 * 0.06 = 0.48
            "length_compliance": 10, # 10 * 0.04 = 0.4
        }
        expected = 1.36 + 1.26 + 1.28 + 1.12 + 1.08 + 1.17 + 0.48 + 0.4  # = 8.15
        result = self.agent._calculate_weighted_score(score_data)
        assert abs(result - expected) < 0.01

    def test_missing_dimension_defaults_to_5(self):
        """缺失维度应默认为5分"""
        score_data = {
            "three_eyes": 10,
            # 缺失其他维度
        }
        result = self.agent._calculate_weighted_score(score_data)
        # 10*0.17 + 5*0.18 + 5*0.16 + 5*0.14 + 5*0.12 + 5*0.13 + 5*0.06 + 5*0.04
        expected = 1.7 + 0.9 + 0.8 + 0.7 + 0.6 + 0.65 + 0.3 + 0.2  # = 5.85
        assert abs(result - expected) < 0.01

    def test_emotion_trigger_has_highest_weight(self):
        """情绪触发应有最高权重，避免标题过平"""
        max_weight_key = max(SCORE_WEIGHTS, key=SCORE_WEIGHTS.get)
        assert max_weight_key == "emotion_trigger"


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
