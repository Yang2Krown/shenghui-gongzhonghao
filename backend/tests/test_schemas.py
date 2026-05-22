"""
数据模式测试

测试覆盖:
1. TopicInfo验证
2. OutlineInfo验证
3. TitleGenerationRequest验证
4. 各种边界条件
"""

import pytest
from pydantic import ValidationError

from app.schemas.title_generation import (
    TopicInfo,
    OutlineInfo,
    TitleGenerationRequest,
    BScoreDetails,
    TitleCandidateResponse,
    FinalRecommendationResponse,
)


class TestTopicInfo:
    """测试选题信息模式"""

    def test_valid_topic(self):
        """有效选题应通过验证"""
        topic = TopicInfo(
            title="测试标题",
            direction="实践型",
            method="痛点直击型",
            value_promise="测试价值",
        )
        assert topic.title == "测试标题"
        assert topic.direction == "实践型"

    def test_all_valid_directions(self):
        """所有6种合法方向应被接受"""
        directions = ["实践型", "解决问题型", "教程型", "观点型", "整活型", "资讯型"]
        for direction in directions:
            topic = TopicInfo(
                title="测试",
                direction=direction,
                method="痛点直击型",
                value_promise="测试",
            )
            assert topic.direction == direction

    def test_invalid_direction_rejected(self):
        """无效方向应被拒绝"""
        with pytest.raises(ValidationError):
            TopicInfo(
                title="测试",
                direction="无效方向",
                method="痛点直击型",
                value_promise="测试",
            )

    def test_empty_title_rejected(self):
        """空标题应被拒绝（Bug1已修复: title字段已有min_length=1）"""
        with pytest.raises(ValidationError):
            TopicInfo(
                title="",
                direction="实践型",
                method="痛点直击型",
                value_promise="测试",
            )

    def test_missing_required_fields(self):
        """缺少必填字段应被拒绝"""
        with pytest.raises(ValidationError):
            TopicInfo(title="测试")  # 缺少direction, method, value_promise


class TestOutlineInfo:
    """测试大纲信息模式"""

    def test_valid_outline(self):
        """有效大纲应通过验证"""
        outline = OutlineInfo(
            section_titles=["第一章", "第二章"],
            key_points=["要点1", "要点2"],
        )
        assert len(outline.section_titles) == 2
        assert len(outline.key_points) == 2

    def test_spread_tags_optional(self):
        """传播标签应为可选字段"""
        outline = OutlineInfo(
            section_titles=["第一章"],
            key_points=["要点1"],
        )
        assert outline.spread_tags == []

    def test_empty_section_titles_rejected(self):
        """空的小标题列表应被拒绝"""
        with pytest.raises(ValidationError):
            OutlineInfo(
                section_titles=[],
                key_points=["要点1"],
            )

    def test_empty_key_points_rejected(self):
        """空的关键信息点列表应被拒绝"""
        with pytest.raises(ValidationError):
            OutlineInfo(
                section_titles=["第一章"],
                key_points=[],
            )


class TestBScoreDetails:
    """测试评分详情模式"""

    def test_valid_scores(self):
        """有效评分应通过验证"""
        scores = BScoreDetails(
            three_eyes=8.0,
            emotion_trigger=7.0,
            specificity=9.0,
            length_compliance=10.0,
            method_maturity=8.0,
            outline_consistency=9.0,
        )
        assert scores.three_eyes == 8.0

    def test_score_boundary_zero(self):
        """0分应被接受"""
        scores = BScoreDetails(
            three_eyes=0,
            emotion_trigger=0,
            specificity=0,
            length_compliance=0,
            method_maturity=0,
            outline_consistency=0,
        )
        assert scores.three_eyes == 0

    def test_score_boundary_ten(self):
        """10分应被接受"""
        scores = BScoreDetails(
            three_eyes=10,
            emotion_trigger=10,
            specificity=10,
            length_compliance=10,
            method_maturity=10,
            outline_consistency=10,
        )
        assert scores.three_eyes == 10

    def test_score_above_ten_rejected(self):
        """超过10分应被拒绝"""
        with pytest.raises(ValidationError):
            BScoreDetails(
                three_eyes=11,
                emotion_trigger=7,
                specificity=9,
                length_compliance=10,
                method_maturity=8,
                outline_consistency=9,
            )

    def test_negative_score_rejected(self):
        """负分应被拒绝"""
        with pytest.raises(ValidationError):
            BScoreDetails(
                three_eyes=-1,
                emotion_trigger=7,
                specificity=9,
                length_compliance=10,
                method_maturity=8,
                outline_consistency=9,
            )


class TestFinalRecommendationResponse:
    """测试最终推荐响应模式"""

    def test_valid_recommendation(self):
        """有效推荐应通过验证"""
        rec = FinalRecommendationResponse(
            id="test-id",
            rank=1,
            title="测试标题",
            word_count=10,
            method="痛点直击型",
            b_score=8.5,
            c_click_willingness=8.0,
            final_score=8.3,
        )
        assert rec.rank == 1

    def test_rank_boundary(self):
        """排名应为1-3"""
        # rank=1 应通过
        rec = FinalRecommendationResponse(
            id="test-id", rank=1, title="测试", word_count=10,
            method="痛点直击型", b_score=8, c_click_willingness=8, final_score=8,
        )
        assert rec.rank == 1

    def test_rank_zero_rejected(self):
        """rank=0应被拒绝"""
        with pytest.raises(ValidationError):
            FinalRecommendationResponse(
                id="test-id", rank=0, title="测试", word_count=10,
                method="痛点直击型", b_score=8, c_click_willingness=8, final_score=8,
            )

    def test_rank_four_rejected(self):
        """rank=4应被拒绝"""
        with pytest.raises(ValidationError):
            FinalRecommendationResponse(
                id="test-id", rank=4, title="测试", word_count=10,
                method="痛点直击型", b_score=8, c_click_willingness=8, final_score=8,
            )
