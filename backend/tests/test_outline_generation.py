"""测试大纲生成 Agent A + Agent B + Agent C + Agent D。

用法：cd backend && python -m tests.test_outline_generation
"""

import asyncio
import sys
import os

# 添加项目根目录到 path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.outline_generation.schemas import (
    OutlineInput,
    AgentBInput,
    AgentCInput,
    AgentDInput,
)
from app.services.outline_generation.agent_a_creator import create_outline_candidates
from app.services.outline_generation.agent_b_reviewer import review_outline
from app.services.outline_generation.agent_c_critic import criticize_outline
from app.services.outline_generation.agent_d_inspector import inspect_outline


# 模拟数据：一条选题
MOCK_OUTLINE_INPUT = OutlineInput(
    candidate_id=999,
    title="Claude 发布全新 Agent 模式，可自主完成复杂任务",
    direction="资讯型",
    routine="1.1.1 深度解读型",
    value_promise="深度解读 Claude Agent 模式的技术突破和行业影响",
    angle_note="从技术架构和应用场景两个维度分析",
    info_cluster_id=999,
    core_title="Claude 发布全新 Agent 模式，可自主完成复杂任务",
    summary="Anthropic 今日宣布 Claude 推出 Agent 模式，能够自主规划并执行多步骤任务，包括代码编写、文件处理、网页浏览等。该模式已在 Claude Pro 订阅中开放。",
)


async def test_agent_a():
    """测试 Agent A：大纲创作员。"""
    print("=" * 60)
    print("测试 Agent A - 大纲创作员")
    print("=" * 60)
    print(f"输入: {MOCK_OUTLINE_INPUT.title}")
    print(f"方向: {MOCK_OUTLINE_INPUT.direction}")
    print()

    try:
        candidates = await create_outline_candidates(MOCK_OUTLINE_INPUT)
        
        print(f"生成 {len(candidates)} 个候选大纲:")
        for i, cand in enumerate(candidates):
            print(f"\n候选 {cand.candidate_number}:")
            print(f"  开头钩子类型: {cand.hook_type}")
            print(f"  骨架特点: {cand.skeleton_feature}")
            print(f"  总字数: {cand.total_words}")
            print(f"  节数: {len(cand.sections)}")
            for section in cand.sections:
                print(f"    节{section.section_number}: {section.title} ({section.word_count}字)")
        
        return candidates
    except Exception as e:
        print(f"Agent A 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return None


async def test_agent_b(candidates):
    """测试 Agent B：大纲评审员。"""
    print("\n" + "=" * 60)
    print("测试 Agent B - 大纲评审员")
    print("=" * 60)
    
    b_input = AgentBInput(
        outline_id=999,
        title=MOCK_OUTLINE_INPUT.title,
        direction=MOCK_OUTLINE_INPUT.direction,
        candidates=candidates,
    )
    
    try:
        review_result = await review_outline(b_input)
        
        print(f"选中候选: {review_result.selected_candidate}")
        print(f"评审理由: {review_result.review_reason}")
        print(f"节数: {len(review_result.sections)}")
        
        # 检查传播标签
        all_tags = set()
        for section in review_result.sections:
            all_tags.update(section.propagation_tags)
            print(f"  节{section.section_number}: {section.title}")
            print(f"    传播标签: {', '.join(section.propagation_tags)}")
        
        required_tags = {"开头钩子", "价值密度", "转发理由", "收藏点"}
        missing_tags = required_tags - all_tags
        if missing_tags:
            print(f"\n⚠️ 缺少必备传播标签: {missing_tags}")
        else:
            print(f"\n✅ 传播标签完整")
        
        return review_result
    except Exception as e:
        print(f"Agent B 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return None


async def test_agent_c(review_result):
    """测试 Agent C：读者挑刺员。"""
    print("\n" + "=" * 60)
    print("测试 Agent C - 读者挑刺员")
    print("=" * 60)
    
    c_input = AgentCInput(
        outline_id=999,
        title=MOCK_OUTLINE_INPUT.title,
        sections=review_result.sections,
    )
    
    try:
        criticism_result = await criticize_outline(c_input)
        
        print(f"整体感受: {criticism_result.overall_feeling}")
        print(f"问题节数: {len(criticism_result.problem_sections)}")
        
        for problem in criticism_result.problem_sections:
            print(f"\n节{problem.section_number}:")
            print(f"  问题类型: {problem.problem_type}")
            print(f"  反馈: {problem.feedback}")
            print(f"  建议: {problem.suggestion}")
        
        return criticism_result
    except Exception as e:
        print(f"Agent C 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return None


async def test_agent_d(criticism_result):
    """测试 Agent D：大纲自检员。"""
    print("\n" + "=" * 60)
    print("测试 Agent D - 大纲自检员")
    print("=" * 60)
    
    d_input = AgentDInput(
        outline_id=999,
        title=MOCK_OUTLINE_INPUT.title,
        sections=criticism_result.revised_sections,
    )
    
    try:
        inspection_result = await inspect_outline(d_input)
        
        print(f"总分: {inspection_result.total_score}")
        print(f"判定: {inspection_result.verdict}")
        
        print(f"\n评分明细:")
        print(f"  开头钩子强度: {inspection_result.hook_score.score} - {inspection_result.hook_score.evidence}")
        print(f"  价值阶梯递进: {inspection_result.value_ladder_score.score} - {inspection_result.value_ladder_score.evidence}")
        print(f"  节奏感: {inspection_result.rhythm_score.score} - {inspection_result.rhythm_score.evidence}")
        print(f"  小标题扫读友好度: {inspection_result.title_scan_score.score} - {inspection_result.title_scan_score.evidence}")
        print(f"  传播触发点完整度: {inspection_result.trigger_score.score} - {inspection_result.trigger_score.evidence}")
        print(f"  长度与节数匹配: {inspection_result.length_score.score} - {inspection_result.length_score.evidence}")
        
        if inspection_result.deduction_reasons:
            print(f"\n扣分理由:")
            for reason in inspection_result.deduction_reasons:
                print(f"  {reason.dimension}: 扣{reason.score_lost}分 - {reason.reason}")
                print(f"    建议: {reason.suggestion}")
        
        return inspection_result
    except Exception as e:
        print(f"Agent D 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return None


async def main():
    """运行完整的大纲生成流程测试。"""
    print("大纲生成流程测试")
    print("=" * 60)
    
    # 测试 Agent A
    candidates = await test_agent_a()
    if not candidates:
        print("\n❌ Agent A 测试失败，流程终止")
        return
    
    # 测试 Agent B
    review_result = await test_agent_b(candidates)
    if not review_result:
        print("\n❌ Agent B 测试失败，流程终止")
        return
    
    # 测试 Agent C
    criticism_result = await test_agent_c(review_result)
    if not criticism_result:
        print("\n❌ Agent C 测试失败，流程终止")
        return
    
    # 测试 Agent D
    inspection_result = await test_agent_d(criticism_result)
    if not inspection_result:
        print("\n❌ Agent D 测试失败，流程终止")
        return
    
    # 总结
    print("\n" + "=" * 60)
    print("测试总结")
    print("=" * 60)
    print(f"✅ Agent A: 生成 {len(candidates)} 个候选大纲")
    print(f"✅ Agent B: 选中候选 {review_result.selected_candidate}")
    print(f"✅ Agent C: 发现 {len(criticism_result.problem_sections)} 个问题节")
    print(f"✅ Agent D: 总分 {inspection_result.total_score}, 判定 {inspection_result.verdict}")
    
    if inspection_result.verdict == "passed":
        print("\n🎉 大纲生成流程测试通过！")
    else:
        print("\n⚠️ 大纲自检未通过，需要重试")


if __name__ == "__main__":
    asyncio.run(main())
