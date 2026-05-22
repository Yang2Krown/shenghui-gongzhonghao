"""
Agent C - 读者点击预测员 单元测试

测试覆盖:
1. 目标读者画像配置
2. 点击预测结果格式化
3. 平均点击意愿计算
4. 缺失预测的补全逻辑
"""

import pytest

from app.agents.agent_c import ClickPredictorAgent, READER_PROFILE
from tests.conftest import make_candidate


class TestReaderProfile:
    """测试目标读者画像配置"""

    def test_reader_age(self):
        """目标读者应为28岁"""
        assert READER_PROFILE["age"] == 28

    def test_reader_gender(self):
        """目标读者应为男性"""
        assert READER_PROFILE["gender"] == "男"

    def test_reader_occupation(self):
        """目标读者应为互联网产品经理"""
        assert READER_PROFILE["occupation"] == "互联网产品经理"

    def test_reader_work_years(self):
        """目标读者应有5年工作经验"""
        assert READER_PROFILE["work_years"] == 5

    def test_ai_tools_defined(self):
        """应定义AI工具列表"""
        assert "Claude" in READER_PROFILE["ai_tools"]
        assert "ChatGPT" in READER_PROFILE["ai_tools"]
        assert "Cursor" in READER_PROFILE["ai_tools"]

    def test_subscriptions_defined(self):
        """应定义订阅列表"""
        assert "路人甲TM" in READER_PROFILE["subscriptions"]


class TestFormatPredictions:
    """测试预测结果格式化"""

    def setup_method(self):
        self.agent = ClickPredictorAgent.__new__(ClickPredictorAgent)

    def test_basic_formatting(self):
        """基本格式化应正确"""
        top5 = [
            {"id": "c1", "title": "标题1", "method": "痛点直击型"},
            {"id": "c2", "title": "标题2", "method": "数字冲击型"},
        ]
        predictions = [
            {"candidate_id": "c1", "click_willingness": 8, "click_reason": "吸引人", "no_click_reason": "", "improvement_suggestion": ""},
            {"candidate_id": "c2", "click_willingness": 5, "click_reason": "", "no_click_reason": "无感", "improvement_suggestion": "改进"},
        ]

        result = self.agent._format_predictions(predictions, top5)

        assert len(result) == 2
        assert result[0]["candidate_id"] == "c1"
        assert result[0]["title"] == "标题1"
        assert result[0]["click_willingness"] == 8
        assert result[1]["candidate_id"] == "c2"
        assert result[1]["click_willingness"] == 5

    def test_missing_prediction_filled(self):
        """缺失的预测应被补全为默认值"""
        top5 = [
            {"id": "c1", "title": "标题1", "method": "痛点直击型"},
            {"id": "c2", "title": "标题2", "method": "数字冲击型"},
        ]
        predictions = [
            {"candidate_id": "c1", "click_willingness": 8, "click_reason": "", "no_click_reason": "", "improvement_suggestion": ""},
            # c2 缺失
        ]

        result = self.agent._format_predictions(predictions, top5)

        assert len(result) == 2
        # c2应被补全
        c2_pred = next(p for p in result if p["candidate_id"] == "c2")
        assert c2_pred["click_willingness"] == 5  # 默认值
        assert "未进行预测" in c2_pred["no_click_reason"]

    def test_all_predictions_present(self):
        """所有预测都存在时不应补全"""
        top5 = [
            {"id": "c1", "title": "标题1"},
            {"id": "c2", "title": "标题2"},
        ]
        predictions = [
            {"candidate_id": "c1", "click_willingness": 9, "click_reason": "好", "no_click_reason": "", "improvement_suggestion": ""},
            {"candidate_id": "c2", "click_willingness": 7, "click_reason": "可以", "no_click_reason": "", "improvement_suggestion": ""},
        ]

        result = self.agent._format_predictions(predictions, top5)
        assert len(result) == 2
        assert all("未进行预测" not in p.get("no_click_reason", "") for p in result)

    def test_empty_predictions(self):
        """空预测列表应为所有top5补全"""
        top5 = [
            {"id": "c1", "title": "标题1"},
            {"id": "c2", "title": "标题2"},
        ]
        predictions = []

        result = self.agent._format_predictions(predictions, top5)
        assert len(result) == 2
        assert all(p["click_willingness"] == 5 for p in result)


class TestCalculateAverageClick:
    """测试平均点击意愿计算"""

    def setup_method(self):
        self.agent = ClickPredictorAgent.__new__(ClickPredictorAgent)

    def test_basic_average(self):
        """基本平均计算"""
        predictions = [
            {"click_willingness": 8},
            {"click_willingness": 6},
            {"click_willingness": 10},
        ]
        result = self.agent._calculate_average_click(predictions)
        assert abs(result - 8.0) < 0.01

    def test_empty_predictions(self):
        """空预测列表应返回0"""
        result = self.agent._calculate_average_click([])
        assert result == 0.0

    def test_single_prediction(self):
        """单个预测应返回该值"""
        predictions = [{"click_willingness": 7}]
        result = self.agent._calculate_average_click(predictions)
        assert result == 7.0

    def test_all_zeros(self):
        """全0分应返回0"""
        predictions = [
            {"click_willingness": 0},
            {"click_willingness": 0},
        ]
        result = self.agent._calculate_average_click(predictions)
        assert result == 0.0

    def test_rounding(self):
        """应正确四舍五入到2位小数"""
        predictions = [
            {"click_willingness": 7},
            {"click_willingness": 8},
        ]
        result = self.agent._calculate_average_click(predictions)
        assert result == 7.5
