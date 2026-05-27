"""大纲生成 API。

提供大纲生成、查询、编辑、重新评估等接口。
"""

import asyncio
import logging
import uuid
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, selectinload

from app.core.security import get_current_user
from app.core.progress import progress_store
from app.db.session import get_db
from app.models.user import User
from app.models.outline import (
    Outline,
    OutlineCandidate,
    OutlineReview,
    OutlineCriticism,
    OutlineInspection,
)
from app.models.topic_candidate import TopicCandidate
from app.services.angle_inspection import inspect_creation_angle
from app.services.outline_generation.outline_service import generate_outline

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/inspect-angle", response_model=dict)
async def trigger_angle_inspection(
    body: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    """触发创作角度体检任务。"""

    candidate_id = body.get("candidate_id")
    if not candidate_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="缺少 candidate_id 参数",
        )

    model = body.get("model")
    run_id = progress_store.create_run()

    async def _run():
        from app.db.session import AsyncSessionLocal
        async with AsyncSessionLocal() as bg_db:
            try:
                result = await bg_db.execute(
                    select(TopicCandidate)
                    .options(selectinload(TopicCandidate.score))
                    .where(TopicCandidate.id == int(candidate_id))
                )
                candidate = result.scalar_one_or_none()
                if not candidate:
                    raise ValueError(f"选题候选 {candidate_id} 不存在")

                async def _progress_cb(event):
                    await progress_store.push(run_id, event)

                report = await inspect_creation_angle(
                    candidate,
                    model=model,
                    progress_callback=_progress_cb,
                )
                await progress_store.push(run_id, {
                    "event": "complete",
                    "data": {"step": 3, "agent": "创作角度体检"},
                })
                await progress_store.push(run_id, {
                    "event": "result",
                    "data": report.model_dump(),
                })
            except Exception as e:
                await progress_store.push(run_id, {
                    "event": "error",
                    "data": {"message": str(e)},
                })

    asyncio.create_task(_run())

    return {
        "code": 200,
        "message": "创作角度体检任务已提交",
        "data": {"run_id": run_id},
    }


@router.post("/generate", response_model=dict)
async def trigger_outline_generation(
    body: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    """触发大纲生成任务。

    返回 run_id，前端可通过 GET /outlines/stream/{run_id} 获取实时进度。
    大纲数据通过 SSE 的 result 事件返回（在 complete 之后）。

    body 格式：
    {
        "candidate_id": 123,  # 选题候选ID
        "model": "claude-3-sonnet"  # 可选，指定模型
    }
    """
    candidate_id = body.get("candidate_id")
    if not candidate_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="缺少 candidate_id 参数"
        )

    model = body.get("model")
    angle_report = body.get("angle_report")
    run_id = progress_store.create_run()

    async def _run():
        from app.db.session import AsyncSessionLocal
        async with AsyncSessionLocal() as bg_db:
            try:
                async def _progress_cb(event):
                    await progress_store.push(run_id, event)

                result = await generate_outline(
                    bg_db,
                    candidate_id=int(candidate_id),
                    model=model,
                    angle_report_data=angle_report,
                    progress_callback=_progress_cb,
                )
                # result 事件触发前端关闭 SSE 流（必须在 complete 之后推送）
                await progress_store.push(run_id, {
                    "event": "result",
                    "data": result.model_dump(),
                })
            except Exception as e:
                await progress_store.push(run_id, {
                    "event": "error",
                    "data": {"message": str(e)},
                })

    asyncio.create_task(_run())

    return {
        "code": 200,
        "message": "大纲生成任务已提交",
        "data": {"run_id": run_id},
    }


@router.get("/stream/{run_id}")
async def stream_outline_progress(
    run_id: str,
    token: str = Query(None, description="认证 token（EventSource 不支持 header）"),
) -> StreamingResponse:
    """SSE 端点：实时推送大纲生成进度。

    EventSource 不支持自定义 header，所以 token 通过 query param 传递。
    """
    # 验证 token
    if token:
        from app.core.security import decode_token
        payload = decode_token(token)
        if not payload:
            raise HTTPException(status_code=401, detail="无效的 token")

    if not progress_store.exists(run_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"run {run_id} 不存在或已过期",
        )

    return StreamingResponse(
        progress_store.stream(run_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("", response_model=dict)
async def get_outlines(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    passed: Optional[str] = Query(None, description="筛选状态: passed/failed/pending"),
    direction: Optional[str] = Query(None, description="筛选方向"),
    min_score: Optional[float] = Query(None, ge=0, le=10, description="最低分数"),
    keyword: Optional[str] = Query(None, description="关键词搜索"),
    sort_by: str = Query("total_score", description="排序字段"),
    sort_order: str = Query("desc", description="排序方式"),
) -> Any:
    """获取大纲列表。"""
    skip = (page - 1) * page_size
    
    # 构建查询
    query = select(Outline).options(
        joinedload(Outline.candidate),
        joinedload(Outline.review),
        joinedload(Outline.inspection),
    )
    
    # 筛选
    if passed:
        query = query.where(Outline.passed == passed)
    if direction:
        query = query.where(Outline.direction == direction)
    if min_score is not None:
        query = query.where(Outline.total_score >= min_score)
    if keyword:
        query = query.where(Outline.title.ilike(f"%{keyword}%"))
    
    # 总数
    count_query = select(func.count(Outline.id))
    if passed:
        count_query = count_query.where(Outline.passed == passed)
    if direction:
        count_query = count_query.where(Outline.direction == direction)
    if min_score is not None:
        count_query = count_query.where(Outline.total_score >= min_score)
    if keyword:
        count_query = count_query.where(Outline.title.ilike(f"%{keyword}%"))
    total_result = await db.execute(count_query)
    total = total_result.scalar()
    
    # 排序
    order_col = getattr(Outline, sort_by, Outline.total_score)
    if sort_order == "desc":
        query = query.order_by(desc(order_col))
    else:
        query = query.order_by(order_col)
    
    query = query.offset(skip).limit(page_size)
    result = await db.execute(query)
    outlines = result.scalars().unique().all()
    
    return {
        "code": 200,
        "message": "获取大纲列表成功",
        "data": {
            "items": [_outline_to_dict(o) for o in outlines],
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": (total + page_size - 1) // page_size,
        },
    }


@router.get("/{outline_id}", response_model=dict)
async def get_outline(
    outline_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    """获取大纲详情。"""
    result = await db.execute(
        select(Outline)
        .options(
            joinedload(Outline.candidate),
            joinedload(Outline.candidates),
            joinedload(Outline.review),
            joinedload(Outline.criticism),
            joinedload(Outline.inspection),
        )
        .where(Outline.id == outline_id)
    )
    outline = result.unique().scalar_one_or_none()
    
    if not outline:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="大纲不存在"
        )
    
    data = _outline_to_dict(outline)
    
    # 添加详细信息
    if outline.candidates:
        data["candidates"] = [
            {
                "candidate_number": c.candidate_number,
                "hook_type": c.hook_type,
                "skeleton_feature": c.skeleton_feature,
                "sections": c.sections,
                "total_words": c.total_words,
            }
            for c in outline.candidates
        ]
    
    if outline.review:
        data["review"] = {
            "selected_candidate": outline.review.selected_candidate,
            "review_reason": outline.review.review_reason,
            "reviewed_sections": outline.review.reviewed_sections,
        }
    
    if outline.criticism:
        data["criticism"] = {
            "overall_feeling": outline.criticism.overall_feeling,
            "problem_sections": outline.criticism.problem_sections,
            "revised_sections": outline.criticism.revised_sections,
        }
    
    if outline.inspection:
        data["inspection"] = {
            "hook_score": outline.inspection.hook_score,
            "value_ladder_score": outline.inspection.value_ladder_score,
            "rhythm_score": outline.inspection.rhythm_score,
            "title_scan_score": outline.inspection.title_scan_score,
            "trigger_score": outline.inspection.trigger_score,
            "length_score": outline.inspection.length_score,
            "total_score": outline.inspection.total_score,
            "verdict": outline.inspection.verdict,
            "deduction_reasons": outline.inspection.deduction_reasons,
        }
    
    return {"code": 200, "message": "获取大纲详情成功", "data": data}


@router.patch("/{outline_id}", response_model=dict)
async def update_outline(
    outline_id: int,
    body: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    """保存编辑后的大纲。

    body 格式（所有字段均可选，只传需要修改的部分）：
    {
        "title": "新标题",
        "sections": [
            {
                "section_number": 1,
                "title": "小标题",
                "core_points": ["要点1", "要点2"],
                "word_count": 500,
                "notes": ""
            }
        ]
    }
    """
    result = await db.execute(
        select(Outline).where(Outline.id == outline_id)
    )
    outline = result.scalar_one_or_none()
    if not outline:
        raise HTTPException(status_code=404, detail="大纲不存在")

    if "title" in body and body["title"]:
        outline.title = body["title"]

    if "sections" in body and isinstance(body["sections"], list):
        outline.sections = body["sections"]
        outline.section_count = len(body["sections"])
        outline.total_words = sum(s.get("word_count", 0) for s in body["sections"])

    await db.commit()
    await db.refresh(outline)

    return {
        "code": 200,
        "message": "大纲已保存",
        "data": _outline_to_dict(outline),
    }


@router.post("/{outline_id}/reevaluate", response_model=dict)
async def reevaluate_outline(
    outline_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    """重新评估大纲（只跑 B→C→D，不重新生成）。

    使用当前已编辑的 sections 作为输入，跳过 Agent A，直接跑后置 Agent。
    返回 run_id，前端通过 SSE 获取实时进度。
    """
    result = await db.execute(
        select(Outline)
        .options(
            joinedload(Outline.candidate),
            joinedload(Outline.candidates),
        )
        .where(Outline.id == outline_id)
    )
    outline = result.unique().scalar_one_or_none()
    if not outline:
        raise HTTPException(status_code=404, detail="大纲不存在")

    if not outline.sections:
        raise HTTPException(status_code=400, detail="大纲内容为空，无法重新评估")

    run_id = progress_store.create_run()

    async def _run():
        from app.db.session import AsyncSessionLocal
        from app.services.outline_generation.schemas import (
            SectionWithTags, AgentBInput, OutlineCandidateItem, Section,
            AgentCInput, AgentDInput,
        )
        from app.services.outline_generation.agent_b_reviewer import review_outline
        from app.services.outline_generation.agent_c_critic import criticize_outline
        from app.services.outline_generation.agent_d_inspector import inspect_outline

        async with AsyncSessionLocal() as bg_db:
            try:
                async def _progress_cb(event):
                    await progress_store.push(run_id, event)

                # 将当前 sections 转为 SectionWithTags（B/C/D 的统一格式）
                current_sections = [
                    SectionWithTags(
                        section_number=s.get("section_number", i + 1),
                        title=s.get("title", ""),
                        core_points=s.get("core_points", []),
                        word_count=s.get("word_count", 0),
                        propagation_tags=s.get("propagation_tags", []),
                        notes=s.get("notes"),
                    )
                    for i, s in enumerate(outline.sections or [])
                ]

                # 构建一个虚拟的 OutlineCandidateItem 给 B
                virtual_candidate = OutlineCandidateItem(
                    candidate_number=1,
                    hook_type="re-evaluate",
                    skeleton_feature="用户编辑后重新评估",
                    sections=[
                        Section(
                            section_number=s.section_number,
                            title=s.title,
                            core_points=s.core_points,
                            word_count=s.word_count,
                            notes=s.notes,
                        )
                        for s in current_sections
                    ],
                    total_words=sum(s.word_count for s in current_sections),
                )

                # ── Agent B ──
                await _progress_cb({"event": "step_start", "data": {"step": 1, "agent": "Agent B", "action": "正在重新评审大纲..."}})
                b_input = AgentBInput(
                    outline_id=outline.id,
                    title=outline.title,
                    direction=outline.direction or "",
                    candidates=[virtual_candidate],
                )
                review_result = await review_outline(b_input)
                await _progress_cb({"event": "step_done", "data": {"step": 1, "agent": "Agent B"}})

                # ── Agent C ──
                await _progress_cb({"event": "step_start", "data": {"step": 2, "agent": "Agent C", "action": "正在模拟读者挑刺..."}})
                c_input = AgentCInput(
                    outline_id=outline.id,
                    title=outline.title,
                    sections=review_result.sections,
                )
                criticism_result = await criticize_outline(c_input)
                await _progress_cb({"event": "step_done", "data": {"step": 2, "agent": "Agent C"}})

                # ── Agent D ──
                await _progress_cb({"event": "step_start", "data": {"step": 3, "agent": "Agent D", "action": "正在自检评分..."}})
                d_input = AgentDInput(
                    outline_id=outline.id,
                    title=outline.title,
                    sections=criticism_result.revised_sections,
                )
                inspection_result = await inspect_outline(d_input)
                await _progress_cb({"event": "step_done", "data": {"step": 3, "agent": "Agent D"}})

                # 更新数据库
                # 删除旧的 review/criticism/inspection
                if outline.review:
                    await bg_db.delete(outline.review)
                if outline.criticism:
                    await bg_db.delete(outline.criticism)
                if outline.inspection:
                    await bg_db.delete(outline.inspection)

                # 写入新的
                new_review = OutlineReview(
                    outline_id=outline.id,
                    selected_candidate=review_result.selected_candidate,
                    review_reason=review_result.review_reason,
                    reviewed_sections=[s.model_dump() for s in review_result.sections],
                )
                bg_db.add(new_review)

                new_criticism = OutlineCriticism(
                    outline_id=outline.id,
                    overall_feeling=criticism_result.overall_feeling,
                    problem_sections=[p.model_dump() for p in criticism_result.problem_sections],
                    revised_sections=[s.model_dump() for s in criticism_result.revised_sections],
                )
                bg_db.add(new_criticism)

                new_inspection = OutlineInspection(
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
                bg_db.add(new_inspection)

                # 更新大纲主表
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

                await bg_db.commit()

                # 推送结果
                await progress_store.push(run_id, {
                    "event": "result",
                    "data": _outline_to_dict_full(outline),
                })
                await _progress_cb({"event": "complete", "data": {"step": 3, "agent": "Agent D"}})

            except Exception as e:
                logger.error(f"大纲重新评估失败: {e}", exc_info=True)
                await progress_store.push(run_id, {
                    "event": "error",
                    "data": {"message": str(e)},
                })

    asyncio.create_task(_run())

    return {
        "code": 200,
        "message": "重新评估任务已提交",
        "data": {"run_id": run_id},
    }


@router.get("/stats/overview", response_model=dict)
async def get_stats_overview(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    """获取大纲统计概览。"""
    total = (await db.execute(select(func.count(Outline.id)))).scalar()
    passed = (await db.execute(
        select(func.count(Outline.id)).where(Outline.passed == "passed")
    )).scalar()
    failed = (await db.execute(
        select(func.count(Outline.id)).where(Outline.passed == "failed")
    )).scalar()
    pending = (await db.execute(
        select(func.count(Outline.id)).where(Outline.passed == "pending")
    )).scalar()
    
    # 平均分数
    avg_score_result = (await db.execute(
        select(func.avg(Outline.total_score)).where(Outline.passed != "pending")
    )).scalar()
    avg_score = round(avg_score_result, 2) if avg_score_result else 0.0
    
    # 按方向统计
    direction_result = await db.execute(
        select(Outline.direction, func.count(Outline.id))
        .where(Outline.direction.is_not(None))
        .group_by(Outline.direction)
    )
    direction_stats = {d: c for d, c in direction_result.all()}
    
    return {
        "code": 200,
        "message": "获取统计成功",
        "data": {
            "total": total or 0,
            "passed": passed or 0,
            "failed": failed or 0,
            "pending": pending or 0,
            "average_score": avg_score,
            "by_direction": direction_stats,
        },
    }


def _outline_to_dict(outline: Outline) -> dict:
    """将大纲对象转换为字典。"""
    return {
        "id": outline.id,
        "candidate_id": outline.candidate_id,
        "title": outline.title,
        "direction": outline.direction,
        "routine": outline.routine,
        "sections": outline.sections,
        "total_words": outline.total_words,
        "section_count": outline.section_count,
        "generation_process": outline.generation_process,
        "inspection_score": outline.inspection_score,
        "total_score": outline.total_score,
        "passed": outline.passed,
        "created_at": outline.created_at.isoformat() if outline.created_at else None,
        "candidate": {
            "id": outline.candidate.id,
            "title": outline.candidate.title,
            "direction": outline.candidate.direction,
            "verdict": outline.candidate.verdict,
        } if outline.candidate else None,
    }


def _outline_to_dict_full(outline: Outline) -> dict:
    """将大纲对象（含关联数据）转换为完整字典，用于重新评估结果。"""
    data = _outline_to_dict(outline)
    if outline.review:
        data["review"] = {
            "selected_candidate": outline.review.selected_candidate,
            "review_reason": outline.review.review_reason,
            "reviewed_sections": outline.review.reviewed_sections,
        }
    if outline.criticism:
        data["criticism"] = {
            "overall_feeling": outline.criticism.overall_feeling,
            "problem_sections": outline.criticism.problem_sections,
            "revised_sections": outline.criticism.revised_sections,
        }
    if outline.inspection:
        data["inspection"] = {
            "hook_score": outline.inspection.hook_score,
            "value_ladder_score": outline.inspection.value_ladder_score,
            "rhythm_score": outline.inspection.rhythm_score,
            "title_scan_score": outline.inspection.title_scan_score,
            "trigger_score": outline.inspection.trigger_score,
            "length_score": outline.inspection.length_score,
            "total_score": outline.inspection.total_score,
            "verdict": outline.inspection.verdict,
            "deduction_reasons": outline.inspection.deduction_reasons,
        }
    return data
