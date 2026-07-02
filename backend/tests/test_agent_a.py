"""
Agent A - 标题创作员 单元测试

测试覆盖:
1. 候选数量：10-15
2. 一票否决词检测
3. 候选验证逻辑
4. 配置约束
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from app.services.title_generation.agent_a_creator import TitleCreatorAgent, ANTI_PATTERNS
from app.core.config import settings


class TestAntiPatterns:
    """测试一票否决词"""

    def test_anti_patterns_list_not_empty(self):
        """反模式列表不应为空"""
        assert len(ANTI_PATTERNS) > 0


class TestContainsAntiPattern:
    """测试一票否决词检测逻辑"""

    def setup_method(self):
        self.agent = TitleCreatorAgent.__new__(TitleCreatorAgent)

    def test_detects_zhenjing(self):
        """应检测到'震惊'"""
        assert self.agent._contains_anti_pattern("震惊！这个AI工具太厉害了") is True

    def test_detects_sukan(self):
        """应检测到'速看'"""
        assert self.agent._contains_anti_pattern("速看！最新AI功能发布") is True

    def test_detects_suoyouren(self):
        """应检测到'所有人都不知道'"""
        assert self.agent._contains_anti_pattern("所有人都不知道的秘密") is True

    def test_detects_baoguo(self):
        """应检测到'保证100%'"""
        assert self.agent._contains_anti_pattern("保证100%有效的方法") is True

    def test_detects_baokuo(self):
        """应检测到'包过'"""
        assert self.agent._contains_anti_pattern("包过！这个提示词必看") is True

    def test_clean_title_passes(self):
        """正常标题应通过检测"""
        assert self.agent._contains_anti_pattern("用了一周Claude Goal的体验") is False

    def test_empty_string_passes(self):
        """空字符串应通过检测"""
        assert self.agent._contains_anti_pattern("") is False


class TestValidateCandidates:
    """测试候选标题验证逻辑"""

    def setup_method(self):
        self.agent = TitleCreatorAgent.__new__(TitleCreatorAgent)

    def test_valid_candidates_pass(self):
        """合法候选应通过验证"""
        candidates = [
            {
                "title": "用了一周Claude Goal的体验",
                "method": "痛点直击型",
                "modifiers": ["第一人称", "工具名"],
            }
        ]
        result = self.agent._validate_candidates(candidates)
        assert len(result) == 1

    def test_short_title_kept_for_reviewer(self):
        """短标题保留给 Agent B 评分，不在 Agent A 硬过滤"""
        candidates = [{"title": "AI助手", "method": "痛点直击型", "modifiers": []}]
        result = self.agent._validate_candidates(candidates)
        assert len(result) == 1

    def test_long_title_kept_for_reviewer(self):
        """长标题保留给 Agent B 评分，不在 Agent A 硬过滤"""
        long_title = "这是一个非常非常非常非常非常非常非常非常长的标题用来测试"  # 26字
        candidates = [{"title": long_title, "method": "痛点直击型", "modifiers": []}]
        result = self.agent._validate_candidates(candidates)
        assert len(result) == 1

    def test_boundary_length_10_passes(self):
        """恰好10字的标题应通过"""
        candidates = [{"title": "一二三四五六七八九十", "method": "痛点直击型", "modifiers": []}]
        result = self.agent._validate_candidates(candidates)
        assert len(result) == 1

    def test_boundary_length_22_passes(self):
        """恰好22字的标题应通过"""
        title_22 = "一二三四五六七八九十一二三四五六七八九十一二"  # 22字
        candidates = [{"title": title_22, "method": "痛点直击型", "modifiers": []}]
        result = self.agent._validate_candidates(candidates)
        assert len(result) == 1

    def test_anti_pattern_filtered(self):
        """包含一票否决词的标题应被过滤"""
        candidates = [{"title": "震惊！这个AI工具太厉害了啊", "method": "痛点直击型", "modifiers": []}]
        result = self.agent._validate_candidates(candidates)
        assert len(result) == 0

    def test_colon_title_filtered(self):
        """任何中英文冒号标题都应过滤"""
        candidates = [{"title": "QoderWork终于来了，实测：它居然会自己检查自己改", "method": "实测", "modifiers": []}]
        result = self.agent._validate_candidates(candidates)
        assert len(result) == 0

    def test_method_kept_as_model_explanation(self):
        """method 只作为表达思路说明保留，不再归一到模板库"""
        candidates = [{"title": "用了一周Claude Goal的体验", "method": "实测", "modifiers": []}]
        result = self.agent._validate_candidates(candidates)
        assert len(result) == 1
        assert result[0]["method"] == "实测"

    def test_empty_method_defaults_to_afeng_style(self):
        """空 method 应给一个兼容后续链路的默认说明"""
        candidates = [{"title": "用了一周Claude Goal的体验", "method": "", "modifiers": []}]
        result = self.agent._validate_candidates(candidates)
        assert len(result) == 1
        assert result[0]["method"] == "阿枫科技风格"

    def test_modifiers_capped_at_max(self):
        """修饰元素应被截断到MAX_MODIFIERS_PER_TITLE"""
        candidates = [{
            "title": "用了一周Claude Goal的体验",
            "method": "痛点直击型",
            "modifiers": ["元素1", "元素2", "元素3", "元素4", "元素5"],
        }]
        result = self.agent._validate_candidates(candidates)
        assert len(result) == 1
        assert len(result[0]["modifiers"]) <= settings.MAX_MODIFIERS_PER_TITLE

    def test_non_list_modifiers_handled(self):
        """非列表类型的修饰元素应被处理为空列表"""
        candidates = [{
            "title": "用了一周Claude Goal的体验",
            "method": "痛点直击型",
            "modifiers": "不是列表",
        }]
        result = self.agent._validate_candidates(candidates)
        assert len(result) == 1
        assert isinstance(result[0]["modifiers"], list)

    def test_word_count_updated(self):
        """验证后应更新字数为实际字数"""
        candidates = [{
            "title": "用了一周Claude Goal的体验",
            "method": "痛点直击型",
            "modifiers": [],
            "word_count": 999,  # 故意错误的字数
        }]
        result = self.agent._validate_candidates(candidates)
        assert result[0]["word_count"] == len("用了一周Claude Goal的体验")

    def test_mixed_candidates(self):
        """混合验证：合法+短标题+反模式，只过滤一票否决"""
        candidates = [
            {"title": "用了一周Claude Goal的体验", "method": "痛点直击型", "modifiers": []},
            {"title": "太短", "method": "痛点直击型", "modifiers": []},
            {"title": "震惊！AI工具大变天了啊哈哈", "method": "痛点直击型", "modifiers": []},
        ]
        result = self.agent._validate_candidates(candidates)
        assert len(result) == 2


class TestSettingsConstraints:
    """测试配置约束值与设计文档一致"""

    def test_min_candidates(self):
        """最少候选数量应为10"""
        assert settings.MIN_CANDIDATES == 10

    def test_max_candidates(self):
        """最多候选数量应为15"""
        assert settings.MAX_CANDIDATES == 15

    def test_min_coverage_methods(self):
        """最少覆盖套路数应为6"""
        assert settings.MIN_COVERAGE_METHODS == 6

    def test_max_same_method(self):
        """同套路最大候选数应为3"""
        assert settings.MAX_SAME_METHOD == 3

    def test_min_title_length(self):
        """最小字数应为8"""
        assert settings.MIN_TITLE_LENGTH == 8

    def test_max_title_length(self):
        """最大字数应为30"""
        assert settings.MAX_TITLE_LENGTH == 30

    def test_optimal_range(self):
        """最佳字数范围应为14-25"""
        assert settings.OPTIMAL_MIN_LENGTH == 14
        assert settings.OPTIMAL_MAX_LENGTH == 25

    def test_max_modifiers_per_title(self):
        """每个标题最多修饰元素应为5"""
        assert settings.MAX_MODIFIERS_PER_TITLE == 5

    def test_pass_threshold(self):
        """通过门槛应为6.5"""
        assert settings.PASS_THRESHOLD == 6.5

    def test_max_regenerations(self):
        """最大重生次数应为1"""
        assert settings.MAX_REGENERATIONS == 1
