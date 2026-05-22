"""
测试配置和共享fixtures

为所有测试模块提供通用的测试数据和fixtures。
"""

import pytest
import asyncio
from typing import Dict, Any, List
from unittest.mock import AsyncMock, MagicMock, patch

from app.schemas.title_generation import TopicInfo, OutlineInfo


# ============================================================
# 测试数据常量
# ============================================================

# 标准选题信息
VALID_TOPIC = TopicInfo(
    title="Claude Goal 深度体验：AI助手的新范式",
    direction="实践型",
    method="第一人称故事型",
    value_promise="用30天真实体验告诉你Claude Goal的优缺点",
)

# 标准大纲信息
VALID_OUTLINE = OutlineInfo(
    section_titles=[
        "什么是Claude Goal",
        "我为什么开始用Claude Goal",
        "Claude Goal的5个核心功能",
        "实际使用30天的体验",
        "Claude Goal vs 其他AI工具",
        "总结和建议",
    ],
    key_points=[
        "Claude Goal是Anthropic推出的新功能",
        "可以记住用户偏好和工作上下文",
        "适合长期项目管理",
        "与ChatGPT的记忆功能有本质区别",
        "目前还在beta阶段",
    ],
    spread_tags=["AI工具", "效率提升", "Claude"],
)

# 生成合法的候选标题列表
def make_candidate(
    candidate_id: str = "test-001",
    title: str = "用了一周Claude Goal，告诉你哪些钱该花哪些不该",
    word_count: int = 19,
    method: str = "痛点直击型",
    modifiers: List[str] = None,
    explanation: str = "切AI订阅费值不值的真实纠结",
) -> Dict[str, Any]:
    """创建标准候选标题"""
    return {
        "id": candidate_id,
        "title": title,
        "word_count": word_count,
        "method": method,
        "modifiers": modifiers or ["第一人称", "工具名"],
        "explanation": explanation,
    }


def make_candidates(count: int = 12) -> List[Dict[str, Any]]:
    """创建多个候选标题"""
    methods = [
        "痛点直击型", "数字冲击型", "第一人称故事型", "反差反转型",
        "反共识型", "焦虑制造型", "实用清单型", "对比测评型",
        "悬念钩子型", "时间紧迫型", "身份代入型", "反向推荐型",
    ]
    titles = [
        "用了一周Claude Goal，告诉你哪些钱该花哪些不该",       # 19字
        "Claude的7个隐藏用法，第3个最实用",                    # 15字
        "我用Claude Goal做了一个让自己都意外的决定",           # 19字
        "我以为Claude Goal是噱头，结果它替代了我5个订阅",      # 22字
        "所有人都在吹AI编程，但我说它没那么神",                # 17字
        "再不学Claude Goal，你就要被同事甩开了",               # 18字
        "产品经理必看的5个Claude提示词模板",                   # 16字
        "Claude vs ChatGPT，10个真实任务测试结果",             # 20字
        "Claude Goal，可能会改变你对AI工具的所有看法",         # 21字
        "刚刚，Anthropic悄悄更新了一个重要功能",               # 17字
        "作为一线运营，我必须说说Claude Goal的真实体验",       # 21字
        "别再花钱买ChatGPT Plus了，这个免费方案更好用",       # 21字
    ]

    candidates = []
    for i in range(min(count, 12)):
        candidates.append(make_candidate(
            candidate_id=f"test-{i+1:03d}",
            title=titles[i],
            word_count=len(titles[i]),
            method=methods[i],
        ))

    return candidates


def make_candidate_with_score(
    candidate_id: str = "test-001",
    b_score: float = 8.5,
    b_score_details: Dict[str, float] = None,
) -> Dict[str, Any]:
    """创建带评分的候选标题"""
    candidate = make_candidate(candidate_id=candidate_id)
    candidate["b_score"] = b_score
    candidate["b_score_details"] = b_score_details or {
        "three_eyes": 9,
        "emotion_trigger": 8,
        "specificity": 9,
        "length_compliance": 10,
        "method_maturity": 8,
        "outline_consistency": 9,
    }
    return candidate


def make_b_result(top5_count: int = 5) -> Dict[str, Any]:
    """创建Agent B的评审结果"""
    top5 = [make_candidate_with_score(f"test-{i+1:03d}", b_score=9.0 - i * 0.3) for i in range(top5_count)]
    return {
        "eliminated": [],
        "scores": top5,
        "top5": top5,
        "top5_ids": [c["id"] for c in top5],
        "covered_methods": 8,
        "eliminated_count": 1,
    }


def make_c_result(top5_count: int = 5) -> Dict[str, Any]:
    """创建Agent C的点击预测结果"""
    predictions = []
    for i in range(top5_count):
        predictions.append({
            "candidate_id": f"test-{i+1:03d}",
            "title": f"测试标题{i+1}",
            "click_willingness": 9 - i,
            "click_reason": "反差感强",
            "no_click_reason": "",
            "improvement_suggestion": "",
        })
    return {
        "predictions": predictions,
        "reader_profile": {"age": 28, "gender": "男"},
        "raw_response": "",
    }


# ============================================================
# Fixtures
# ============================================================

@pytest.fixture
def topic():
    """标准选题信息fixture"""
    return VALID_TOPIC


@pytest.fixture
def outline():
    """标准大纲信息fixture"""
    return VALID_OUTLINE


@pytest.fixture
def candidates():
    """标准候选列表fixture"""
    return make_candidates(12)


@pytest.fixture
def b_result():
    """Agent B评审结果fixture"""
    return make_b_result()


@pytest.fixture
def c_result():
    """Agent C点击预测结果fixture"""
    return make_c_result()


@pytest.fixture
def mock_ai_response():
    """Mock AI模型响应"""
    return AsyncMock()
