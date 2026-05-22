"""
Agent A - 标题创作员 单元测试

测试覆盖:
1. 套路覆盖：12种套路数据完整性
2. 字数约束：MIN_TITLE_LENGTH=10, MAX_TITLE_LENGTH=22
3. 候选数量：10-15
4. 一票否决词检测
5. 候选验证逻辑
6. 优先套路选择
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from app.services.title_generation.agent_a_creator import TitleCreatorAgent, TITLE_METHODS, MODIFIERS, ANTI_PATTERNS
from app.core.config import settings


class TestTitleMethodsData:
    """测试标题套路库数据完整性"""

    def test_12_methods_defined(self):
        """应定义12种标题套路"""
        assert len(TITLE_METHODS) == 12

    def test_method_names_match_design(self):
        """套路名称应与设计文档一致"""
        expected_methods = [
            "痛点直击型", "数字冲击型", "第一人称故事型", "反差反转型",
            "反共识型", "焦虑制造型", "实用清单型", "对比测评型",
            "悬念钩子型", "时间紧迫型", "身份代入型", "反向推荐型",
        ]
        for method in expected_methods:
            assert method in TITLE_METHODS, f"缺少套路: {method}"

    def test_each_method_has_required_fields(self):
        """每个套路应有description、templates、applicable_directions"""
        for name, info in TITLE_METHODS.items():
            assert "description" in info, f"{name}缺少description"
            assert "templates" in info, f"{name}缺少templates"
            assert "applicable_directions" in info, f"{name}缺少applicable_directions"
            assert len(info["templates"]) >= 1, f"{name}模板数量不足"
            assert len(info["applicable_directions"]) >= 1, f"{name}适用方向为空"

    def test_each_method_has_valid_directions(self):
        """每个套路的适用方向应在合法范围内（Bug2已修复: 移除了'实用清单型'错误方向）"""
        valid_directions = {"实践型", "解决问题型", "教程型", "观点型", "整活型", "资讯型"}
        for name, info in TITLE_METHODS.items():
            for direction in info["applicable_directions"]:
                assert direction in valid_directions, f"{name}包含无效方向: {direction}"


class TestModifiersData:
    """测试修饰元素数据完整性"""

    def test_6_modifiers_defined(self):
        """应定义6类修饰元素"""
        assert len(MODIFIERS) == 6

    def test_modifier_keys(self):
        """修饰元素应包含标准键名"""
        expected_keys = ["数字", "身份代入词", "反差/反预期词", "紧迫/时效词", "情绪词", "反常识词"]
        for key in expected_keys:
            assert key in MODIFIERS, f"缺少修饰元素: {key}"


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

    def test_short_title_filtered(self):
        """过短标题应被过滤（< 10字）"""
        candidates = [{"title": "AI助手", "method": "痛点直击型", "modifiers": []}]
        result = self.agent._validate_candidates(candidates)
        assert len(result) == 0

    def test_long_title_filtered(self):
        """过长标题应被过滤（> 22字）"""
        long_title = "这是一个非常非常非常非常非常非常非常非常长的标题用来测试"  # 26字
        candidates = [{"title": long_title, "method": "痛点直击型", "modifiers": []}]
        result = self.agent._validate_candidates(candidates)
        assert len(result) == 0

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

    def test_invalid_method_gets_fuzzy_matched(self):
        """无效套路名应被模糊匹配或设为默认值"""
        candidates = [{"title": "用了一周Claude Goal的体验", "method": "痛点", "modifiers": []}]
        result = self.agent._validate_candidates(candidates)
        assert len(result) == 1
        assert result[0]["method"] == "痛点直击型"

    def test_unknown_method_defaults(self):
        """完全未知的套路名应设为默认第一个套路"""
        candidates = [{"title": "用了一周Claude Goal的体验", "method": "完全未知套路", "modifiers": []}]
        result = self.agent._validate_candidates(candidates)
        assert len(result) == 1
        assert result[0]["method"] == list(TITLE_METHODS.keys())[0]

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
        """混合验证：合法+短标题+反模式"""
        candidates = [
            {"title": "用了一周Claude Goal的体验", "method": "痛点直击型", "modifiers": []},
            {"title": "太短", "method": "痛点直击型", "modifiers": []},
            {"title": "震惊！AI工具大变天了啊哈哈", "method": "痛点直击型", "modifiers": []},
        ]
        result = self.agent._validate_candidates(candidates)
        assert len(result) == 1


class TestGetPriorityMethods:
    """测试优先套路选择逻辑"""

    def setup_method(self):
        self.agent = TitleCreatorAgent.__new__(TitleCreatorAgent)

    def test_practice_direction(self):
        """实践型方向应返回正确的优先套路"""
        methods = self.agent._get_priority_methods("实践型")
        assert "数字冲击型" in methods
        assert "第一人称故事型" in methods
        assert "反差反转型" in methods

    def test_opinion_direction(self):
        """观点型方向应返回正确的优先套路"""
        methods = self.agent._get_priority_methods("观点型")
        assert "反共识型" in methods
        assert "反差反转型" in methods

    def test_invalid_direction_fallback(self):
        """无效方向应返回默认6个套路"""
        methods = self.agent._get_priority_methods("不存在的方向")
        assert len(methods) == 6

    def test_tutorial_direction(self):
        """教程型方向应返回正确的优先套路"""
        methods = self.agent._get_priority_methods("教程型")
        assert "实用清单型" in methods
        assert "身份代入型" in methods


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
        """最小字数应为10"""
        assert settings.MIN_TITLE_LENGTH == 10

    def test_max_title_length(self):
        """最大字数应为22"""
        assert settings.MAX_TITLE_LENGTH == 22

    def test_optimal_range(self):
        """最佳字数范围应为14-20"""
        assert settings.OPTIMAL_MIN_LENGTH == 14
        assert settings.OPTIMAL_MAX_LENGTH == 20

    def test_max_modifiers_per_title(self):
        """每个标题最多修饰元素应为3"""
        assert settings.MAX_MODIFIERS_PER_TITLE == 3

    def test_pass_threshold(self):
        """通过门槛应为7.0"""
        assert settings.PASS_THRESHOLD == 7.0

    def test_max_regenerations(self):
        """最大重生次数应为1"""
        assert settings.MAX_REGENERATIONS == 1
