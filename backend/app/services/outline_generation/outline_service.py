"""大纲生成服务。

协调 4 个 Agent 完成大纲生成流程：
Agent A（大纲创作员）→ Agent B（大纲评审员）→ Agent C（读者挑刺员）→ Agent D（大纲自检员）
"""

import logging
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.outline import (
    Outline,
    OutlineCandidate,
    OutlineReview,
    OutlineCriticism,
    OutlineInspection,
)
from app.models.topic_candidate import TopicCandidate
from app.services.outline_generation.schemas import (
    OutlineInput,
    AgentBInput,
    AgentCInput,
    AgentDInput,
    FinalOutline,
    SectionWithTags,
)
from app.services.outline_generation.agent_a_creator import create_outline_candidates
from app.services.outline_generation.agent_b_reviewer import review_outline
from app.services.outline_generation.agent_c_critic import criticize_outline
from app.services.outline_generation.agent_d_inspector import inspect_outline

logger = logging.getLogger(__name__)

# 最大重试次数
MAX_RETRIES = 2


async def generate_outline(
    db: AsyncSession,
    candidate_id: int,
    *,
    llm_client=None,
    model: Optional[str] = None,
) -> FinalOutline:
    """大纲生成主入口。
    
    流程：
    1. 从数据库获取选题候选
    2. Agent A 生成 3 个候选大纲
    3. Agent B 评审并补全传播标签
    4. Agent C 挑刺并修订
    5. Agent D 自检评分
    6. 如果不通过，最多重试 2 次
    """
    # 1. 获取选题候选
    candidate = await db.get(TopicCandidate, candidate_id)
    if not candidate:
        raise ValueError(f"选题候选 {candidate_id} 不存在")
    
    # 构建输入
    outline_input = OutlineInput(
        candidate_id=candidate.id,
        title=candidate.title,
        direction=candidate.direction or "资讯型",
        routine=candidate.routine,
        value_promise=candidate.value_promise,
        angle_note=candidate.angle_note,
        info_cluster_id=candidate.info_cluster_id,
    )
    
    # 创建大纲记录
    outline = Outline(
        candidate_id=candidate.id,
        title=candidate.title,
        direction=candidate.direction,
        routine=candidate.routine,
    )
    db.add(outline)
    await db.flush()
    
    # 重试循环
    for attempt in range(MAX_RETRIES + 1):
        try:
            logger.info(f"大纲生成第 {attempt + 1} 次尝试: outline_id={outline.id}")
            
            # 2. Agent A 生成 3 个候选大纲
            candidates = await create_outline_candidates(
                outline_input,
                llm_client=llm_client,
                model=model,
            )
            
            # 保存候选大纲
            for cand in candidates:
                outline_candidate = OutlineCandidate(
                    outline_id=outline.id,
                    candidate_number=cand.candidate_number,
                    hook_type=cand.hook_type,
                    skeleton_feature=cand.skeleton_feature,
                    sections=[s.model_dump() for s in cand.sections],
                    total_words=cand.total_words,
                )
                db.add(outline_candidate)
            
            # 3. Agent B 评审
            b_input = AgentBInput(
                outline_id=outline.id,
                title=outline.title,
                direction=outline.direction,
                candidates=candidates,
            )
            review_result = await review_outline(b_input, llm_client=llm_client, model=model)
            
            # 保存评审结果
            review = OutlineReview(
                outline_id=outline.id,
                selected_candidate=review_result.selected_candidate,
                review_reason=review_result.review_reason,
                reviewed_sections=[s.model_dump() for s in review_result.sections],
            )
            db.add(review)
            
            # 4. Agent C 挑刺
            c_input = AgentCInput(
                outline_id=outline.id,
                title=outline.title,
                sections=review_result.sections,
            )
            criticism_result = await criticize_outline(c_input, llm_client=llm_client, model=model)
            
            # 保存挑刺结果
            criticism = OutlineCriticism(
                outline_id=outline.id,
                overall_feeling=criticism_result.overall_feeling,
                problem_sections=[p.model_dump() for p in criticism_result.problem_sections],
                revised_sections=[s.model_dump() for s in criticism_result.revised_sections],
            )
            db.add(criticism)
            
            # 5. Agent D 自检
            d_input = AgentDInput(
                outline_id=outline.id,
                title=outline.title,
                sections=criticism_result.revised_sections,
            )
            inspection_result = await inspect_outline(d_input, llm_client=llm_client, model=model)
            
            # 保存自检结果
            inspection = OutlineInspection(
                outline_id=outline.id,
                hook_score=inspection_result.hook_score.score,
                value_ladder_score=inspection_result.value_ladder_score.score,
                rhythm_score=inspection_result.rhythm_score.score,
                title_scan_score=inspection_result.title_scan_score.score,
                trigger_score=inspection_result.trigger_score.score,
                length_score=inspection_result.length_score.score,
                total_score=inspection_result.total_score,
                verdict=inspection_result.verdict,
                deduction_reasons=[d.model_dump() for d in inspection_result.deduction_reasons],
            )
            db.add(inspection)
            
            # 更新大纲记录
            outline.sections = [s.model_dump() for s in criticism_result.revised_sections]
            outline.total_words = sum(s.word_count for s in criticism_result.revised_sections)
            outline.section_count = len(criticism_result.revised_sections)
            outline.inspection_score = {
                "hook": inspection_result.hook_score.model_dump(),
                "value_ladder": inspection_result.value_ladder_score.model_dump(),
                "rhythm": inspection_result.rhythm_score.model_dump(),
                "title_scan": inspection_result.title_scan_score.model_dump(),
                "trigger": inspection_result.trigger_score.model_dump(),
                "length": inspection_result.length_score.model_dump(),
            }
            outline.total_score = inspection_result.total_score
            outline.passed = inspection_result.verdict
            
            # 记录生成过程
            outline.generation_process = {
                "attempts": attempt + 1,
                "selected_candidate": review_result.selected_candidate,
                "review_reason": review_result.review_reason,
                "criticism": criticism_result.overall_feeling,
                "problem_sections_count": len(criticism_result.problem_sections),
            }
            
            await db.commit()
            
            # 如果通过，返回最终大纲
            if inspection_result.verdict == "passed":
                logger.info(f"大纲生成成功: outline_id={outline.id}, 总分={inspection_result.total_score}")
                return FinalOutline(
                    outline_id=outline.id,
                    title=outline.title,
                    direction=outline.direction,
                    routine=outline.routine,
                    value_promise=candidate.value_promise,
                    sections=criticism_result.revised_sections,
                    total_words=outline.total_words,
                    section_count=outline.section_count,
                    generation_process=outline.generation_process,
                    inspection_score=outline.inspection_score,
                    total_score=outline.total_score,
                    passed=outline.passed,
                )
            
            # 如果不通过且还有重试次数，继续
            if attempt < MAX_RETRIES:
                logger.warning(f"大纲自检不通过，准备重试: 总分={inspection_result.total_score}")
                # 更新输入，加入扣分理由
                outline_input = OutlineInput(
                    candidate_id=candidate.id,
                    title=candidate.title,
                    direction=candidate.direction or "资讯型",
                    routine=candidate.routine,
                    value_promise=candidate.value_promise,
                    angle_note=f"{candidate.angle_note or ''}\n\n【前次失败原因】\n{'; '.join(d.reason for d in inspection_result.deduction_reasons)}",
                    info_cluster_id=candidate.info_cluster_id,
                )
                continue
            
            # 2 次仍不过，标记"难以成稿"
            logger.warning(f"大纲生成失败: outline_id={outline.id}, 2 次自检均不通过")
            outline.passed = "failed"
            await db.commit()
            
            return FinalOutline(
                outline_id=outline.id,
                title=outline.title,
                direction=outline.direction,
                routine=outline.routine,
                value_promise=candidate.value_promise,
                sections=criticism_result.revised_sections,
                total_words=outline.total_words,
                section_count=outline.section_count,
                generation_process=outline.generation_process,
                inspection_score=outline.inspection_score,
                total_score=outline.total_score,
                passed="failed",
            )
            
        except Exception as e:
            logger.error(f"大纲生成异常: {e}")
            if attempt < MAX_RETRIES:
                continue
            raise
    
    # 不应该到达这里
    raise RuntimeError("大纲生成流程异常")
