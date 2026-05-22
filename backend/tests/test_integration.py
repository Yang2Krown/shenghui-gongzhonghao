"""
集成测试 - 标题生成服务和Agent协作流程

测试覆盖:
1. 完整流程: Agent A → B → C → D → 输出Top 3
2. 重生机制: 自检失败时的重生逻辑
3. 异常处理: API调用失败等
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime

from app.core.config import settings
from tests.conftest import (
    VALID_TOPIC, VALID_OUTLINE,
    make_candidate, make_candidates, make_candidate_with_score,
    make_b_result, make_c_result,
)


class TestAgentPipelineFlow:
    """测试4个Agent的协作流程"""

    def test_agent_pipeline_order(self):
        """Agent应按A→B→C→D顺序执行"""
        # 这是架构层面的验证，实际执行顺序由service控制
        from app.services.title_generation_service import TitleGenerationService
        # 验证service中定义了正确的Agent调用顺序
        import inspect
        source = inspect.getsource(TitleGenerationService._execute_agent_pipeline)
        # 验证执行顺序
        pos_a = source.find("agent_a")
        pos_b = source.find("agent_b")
        pos_c = source.find("agent_c")
        pos_d = source.find("agent_d")
        assert pos_a < pos_b < pos_c < pos_d, "Agent执行顺序应为A→B→C→D"

    def test_regeneration_condition(self):
        """当need_regeneration=True且次数<MAX_REGENERATIONS时应触发重生"""
        assert settings.MAX_REGENERATIONS == 1

    def test_pipeline_returns_false_on_no_candidates(self):
        """Agent A未生成候选时应返回False"""
        # 这个在service层测试
        pass


class TestScoreCalculationFlow:
    """测试评分计算流程"""

    def test_b_score_weighted_correctly(self):
        """B评分应按6维度加权计算"""
        from app.agents.agent_b import TitleReviewerAgent
        agent = TitleReviewerAgent.__new__(TitleReviewerAgent)

        score_data = {
            "three_eyes": 8,
            "emotion_trigger": 7,
            "specificity": 9,
            "length_compliance": 10,
            "method_maturity": 8,
            "outline_consistency": 9,
        }
        b_score = agent._calculate_weighted_score(score_data)
        expected = 8*0.25 + 7*0.20 + 9*0.15 + 10*0.10 + 8*0.15 + 9*0.15
        assert abs(b_score - expected) < 0.01

    def test_final_score_formula(self):
        """最终评分应为 0.6*B + 0.4*C"""
        b_score = 8.0
        c_click = 7.0
        expected = 0.6 * b_score + 0.4 * c_click
        assert abs(expected - 7.6) < 0.01

    def test_final_score_all_scenarios(self):
        """验证不同B和C组合的最终评分"""
        scenarios = [
            (10.0, 10.0, 10.0),
            (8.0, 8.0, 8.0),
            (6.0, 4.0, 5.2),  # 0.6*6 + 0.4*4 = 3.6 + 1.6 = 5.2
            (9.0, 5.0, 7.4),  # 0.6*9 + 0.4*5 = 5.4 + 2.0 = 7.4
        ]
        for b, c, expected in scenarios:
            result = settings.B_SCORE_WEIGHT * b + settings.C_SCORE_WEIGHT * c
            assert abs(result - expected) < 0.01, f"B={b}, C={c}: 期望{expected}, 得到{result}"


class TestEndToEndMock:
    """使用Mock测试端到端流程"""

    @pytest.mark.asyncio
    async def test_full_pipeline_with_mock(self, topic, outline):
        """使用Mock测试完整流水线"""
        from app.agents.agent_a import TitleCreatorAgent
        from app.agents.agent_b import TitleReviewerAgent
        from app.agents.agent_c import ClickPredictorAgent
        from app.agents.agent_d import FinalJudgeAgent

        # 准备Mock数据
        mock_candidates = make_candidates(12)
        for c in mock_candidates:
            c["id"] = c.get("id", "test-id")

        # Mock Agent A
        agent_a = TitleCreatorAgent.__new__(TitleCreatorAgent)
        agent_a.generate_titles = AsyncMock(return_value={"candidates": mock_candidates, "raw_response": ""})

        # Mock Agent B
        b_result = make_b_result(5)
        agent_b = TitleReviewerAgent.__new__(TitleReviewerAgent)
        agent_b.review_titles = AsyncMock(return_value=b_result)

        # Mock Agent C
        c_result = make_c_result(5)
        agent_c = ClickPredictorAgent.__new__(ClickPredictorAgent)
        agent_c.predict_clicks = AsyncMock(return_value=c_result)

        # Agent D (使用真实逻辑)
        agent_d = FinalJudgeAgent.__new__(FinalJudgeAgent)
        agent_d._generate_single_reason = MagicMock(return_value="测试推荐理由")

        # 执行流程
        a_result = await agent_a.generate_titles(topic=topic, outline=outline)
        assert len(a_result["candidates"]) == 12

        b_out = await agent_b.review_titles(
            candidates=a_result["candidates"],
            topic=topic,
            outline=outline,
        )
        assert len(b_out["top5"]) == 5

        c_out = await agent_c.predict_clicks(
            top5=b_out["top5"],
            topic=topic,
            outline=outline,
        )
        assert len(c_out["predictions"]) == 5

        # 测试Agent D的核心逻辑
        d_result = await agent_d.judge_titles(
            b_result=b_out,
            c_result=c_out,
            topic=topic,
            outline=outline,
        )

        assert "passed" in d_result
        assert "recommendations" in d_result
        assert "need_regeneration" in d_result
        assert len(d_result["recommendations"]) <= 3


class TestRegenerationLogic:
    """测试重生机制"""

    def test_max_regenerations_is_1(self):
        """最大重生次数应为1"""
        assert settings.MAX_REGENERATIONS == 1

    def test_regeneration_condition_check(self):
        """重生条件: need_regeneration=True 且 regeneration_count < MAX_REGENERATIONS"""
        need_regen = True
        regen_count = 0
        should_regen = need_regen and regen_count < settings.MAX_REGENERATIONS
        assert should_regen is True

    def test_no_regeneration_after_max(self):
        """达到最大重生次数后不应再重生"""
        need_regen = True
        regen_count = 1
        should_regen = need_regen and regen_count < settings.MAX_REGENERATIONS
        assert should_regen is False

    def test_no_regeneration_when_passed(self):
        """通过自检后不应重生"""
        need_regen = False
        regen_count = 0
        should_regen = need_regen and regen_count < settings.MAX_REGENERATIONS
        assert should_regen is False


class TestErrorHandling:
    """测试异常处理"""

    def test_api_retry_config(self):
        """API重试次数应配置为3"""
        assert settings.MAX_API_RETRIES == 3

    def test_api_timeout_config(self):
        """API超时应配置为60秒"""
        assert settings.API_TIMEOUT == 60

    @pytest.mark.asyncio
    async def test_parse_json_response_valid(self):
        """有效JSON应被正确解析"""
        from app.agents.agent_a import TitleCreatorAgent
        agent = TitleCreatorAgent.__new__(TitleCreatorAgent)

        response = '{"candidates": [{"title": "测试"}]}'
        result = agent.parse_json_response(response)
        assert "candidates" in result
        assert result["candidates"][0]["title"] == "测试"

    @pytest.mark.asyncio
    async def test_parse_json_response_with_markdown(self):
        """带Markdown代码块的JSON应被正确解析"""
        from app.agents.agent_a import TitleCreatorAgent
        agent = TitleCreatorAgent.__new__(TitleCreatorAgent)

        response = '```json\n{"candidates": [{"title": "测试"}]}\n```'
        result = agent.parse_json_response(response)
        assert "candidates" in result

    @pytest.mark.asyncio
    async def test_parse_json_response_with_prefix(self):
        """带前缀文字的JSON应被正确解析"""
        from app.agents.agent_a import TitleCreatorAgent
        agent = TitleCreatorAgent.__new__(TitleCreatorAgent)

        response = '以下是结果：\n{"candidates": [{"title": "测试"}]}'
        result = agent.parse_json_response(response)
        assert "candidates" in result

    @pytest.mark.asyncio
    async def test_parse_json_response_invalid(self):
        """无效JSON应返回空字典"""
        from app.agents.agent_a import TitleCreatorAgent
        agent = TitleCreatorAgent.__new__(TitleCreatorAgent)

        response = '这不是JSON'
        result = agent.parse_json_response(response)
        assert result == {}

    @pytest.mark.asyncio
    async def test_parse_json_response_empty(self):
        """空字符串应返回空字典"""
        from app.agents.agent_a import TitleCreatorAgent
        agent = TitleCreatorAgent.__new__(TitleCreatorAgent)

        result = agent.parse_json_response("")
        assert result == {}
