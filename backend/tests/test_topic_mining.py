"""测试选题挖掘 Agent A + Agent B。

用法：cd backend && python -m tests.test_topic_mining
"""

import asyncio
import sys
import os

# 添加项目根目录到 path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.topic_mining.schemas import InfoClusterInput, AgentBInput
from app.services.topic_mining.agent_a_deriver import derive_candidates
from app.services.topic_mining.agent_b_scorer import score_candidates


# 模拟数据：一条资讯型信息
MOCK_INFO = InfoClusterInput(
    cluster_id=999,
    core_title="Claude 发布全新 Agent 模式，可自主完成复杂任务",
    summary="Anthropic 今日宣布 Claude 推出 Agent 模式，能够自主规划并执行多步骤任务，包括代码编写、文件处理、网页浏览等。该模式已在 Claude Pro 订阅中开放。",
    info_type="资讯型",
    direction="大模型",
    elements={
        "主体": "Anthropic / Claude",
        "动作": "发布 Agent 模式",
        "对象": "Claude Pro 用户",
        "亮点": "自主规划多步骤任务、代码编写、文件处理、网页浏览",
        "争议": "安全性、是否取代人类工作",
        "数据": "Claude Pro 订阅价格 $20/月",
    },
    freshness="24h",
    heat_score=8.5,
    low_fan_hit=False,
    source_urls=["https://example.com/claude-agent"],
)


async def test_agent_a():
    """测试 Agent A：衍生候选选题。"""
    print("=" * 60)
    print("测试 Agent A - 选题衍生员")
    print("=" * 60)
    print(f"输入: {MOCK_INFO.core_title}")
    print(f"信息类型: {MOCK_INFO.info_type}")
    print()

    try:
        candidates = await derive_candidates(MOCK_INFO)
        print(f"衍生结果: {len(candidates)} 个候选选题")
        print("-" * 60)

        for c in candidates:
            flag = " ⚠️" if c.persona_divergence_flag else ""
            print(f"[{c.candidate_id}] {c.title}")
            print(f"  方向: {c.direction} | 套路: {c.routine}")
            print(f"  价值承诺: {c.value_promise}")
            print(f"  维度组合: {', '.join(c.dimension_combo) if c.dimension_combo else '无'}")
            print(f"  切入说明: {c.angle_note}")
            print(f"  Persona 分歧度: {c.persona_divergence}{flag}")
            for pr in c.persona_reviews:
                print(f"    {pr.persona}: {pr.score} - {pr.rationale}")
            print()

        return candidates
    except Exception as e:
        print(f"Agent A 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return None


async def test_agent_b(candidates):
    """测试 Agent B：评分候选选题。"""
    print("=" * 60)
    print("测试 Agent B - 选题评分员")
    print("=" * 60)
    print(f"输入: {len(candidates)} 个候选选题")
    print()

    b_input = AgentBInput(
        cluster_id=MOCK_INFO.cluster_id,
        core_title=MOCK_INFO.core_title,
        info_type=MOCK_INFO.info_type,
        freshness=MOCK_INFO.freshness,
        candidates=candidates,
    )

    try:
        result = await score_candidates(b_input)
        print(f"评分结果:")
        print(f"  总候选: {result.stats.get('total', 0)}")
        print(f"  入选: {result.stats.get('selected', 0)}")
        print(f"  备选: {result.stats.get('backup', 0)}")
        print(f"  淘汰: {result.stats.get('rejected', 0)}")
        print(f"  否决: {result.stats.get('vetoed', 0)}")
        print("-" * 60)

        for c in result.candidates:
            verdict_icon = {"selected": "✅", "backup": "⏳", "rejected": "❌", "vetoed": "🚫"}.get(c.verdict, "?")
            print(f"[{c.candidate_id}] {c.title}")
            print(f"  判定: {verdict_icon} {c.verdict} | 总分: {c.weighted_score}")
            print(f"  一票否决: {'通过' if c.veto_passed else '未通过'}")
            if c.veto_reasons:
                print(f"  否决原因: {', '.join(c.veto_reasons)}")
            print(f"  评分明细:")
            print(f"    痛点直击度({c.pain_point.score}): {c.pain_point.evidence}")
            print(f"    价值密度({c.value_density.score}): {c.value_density.evidence}")
            print(f"    传播触发器({c.propagation.score}): {c.propagation.evidence}")
            print(f"    差异化({c.differentiation.score}): {c.differentiation.evidence}")
            print(f"    新鲜度({c.freshness.score}): {c.freshness.evidence}")
            print(f"    受众适配度({c.audience_fit.score}): {c.audience_fit.evidence}")
            print()

        return result
    except Exception as e:
        print(f"Agent B 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return None


async def main():
    print("选题挖掘 Agent 测试")
    print("=" * 60)
    print()

    # 测试 Agent A
    candidates = await test_agent_a()
    if not candidates:
        print("Agent A 测试失败，跳过 Agent B")
        return

    # 测试 Agent B
    await test_agent_b(candidates)

    print("=" * 60)
    print("测试完成")


if __name__ == "__main__":
    asyncio.run(main())
