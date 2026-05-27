"""
标题生成端点

提供标题生成任务的创建、执行、结果查询、编辑和重新评估功能。
"""

import asyncio
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
import uuid
import logging

from app.db.session import get_db, AsyncSessionLocal
from app.core.progress import progress_store
from app.core.security import get_current_user
from app.models.user import User
from app.models.task import Task, TaskStatus
from app.models.title import TitleGenerationResult, TitleCandidate, FinalRecommendation
from app.schemas.title_generation import (
    TitleGenerationRequest,
    TitleGenerationResponse,
    TitleGenerationResultResponse,
    TitleCandidateResponse,
    FinalRecommendationResponse,
)
from app.services.generation_tracker import track_start, track_complete, track_fail

logger = logging.getLogger(__name__)

router = APIRouter()


async def _run_title_generation_background(task_id: str, request_data: dict, run_id: str = None, user_id: int = None):
    """
    后台执行标题生成任务的独立函数

    在独立的数据库会话中创建TitleGenerationService实例并执行，
    避免在请求处理阶段就实例化Agent（需要API密钥）。

    Args:
        task_id: 任务ID
        request_data: 请求数据（已序列化为dict）
        run_id: 进度流 ID（可选）
    """
    # 延迟导入，避免在请求处理阶段加载Agent模块
    from app.services.title_generation_service import TitleGenerationService
    from app.schemas.title_generation import TitleGenerationRequest

    async def _progress_cb(event):
        if run_id:
            await progress_store.push(run_id, event)

    # 在后台任务中创建独立的数据库会话
    async with AsyncSessionLocal() as db:
        try:
            # 反序列化请求数据
            request = TitleGenerationRequest(**request_data)

            # 在后台任务中实例化Service（此时才加载Agent，需要API密钥）
            service = TitleGenerationService(db, progress_callback=_progress_cb)
            await service.execute_title_generation(
                task_id=task_id,
                request=request,
            )

            # 推送结果事件（触发前端关闭 SSE 连接）
            if run_id:
                from sqlalchemy import select, desc
                from app.models.title import (
                    TitleGenerationResult,
                    FinalRecommendation,
                    TitleCandidate,
                )

                recommendations_payload = []
                candidates_payload = []
                result_meta = None

                result_row = (
                    await db.execute(
                        select(TitleGenerationResult).where(TitleGenerationResult.task_id == task_id)
                    )
                ).scalar_one_or_none()
                if result_row:
                    result_meta = {
                        "result_id": result_row.id,
                        "total_candidates": result_row.total_candidates,
                        "covered_methods": result_row.covered_methods,
                        "eliminated_count": result_row.eliminated_count,
                        "regeneration_count": result_row.regeneration_count,
                        "self_check_passed": result_row.self_check_passed,
                        "duration_seconds": result_row.duration_seconds,
                    }

                    rec_rows = (
                        await db.execute(
                            select(FinalRecommendation)
                            .where(FinalRecommendation.result_id == result_row.id)
                            .order_by(FinalRecommendation.rank)
                        )
                    ).scalars().all()
                    recommendations_payload = [
                        {
                            "rank": r.rank,
                            "title": r.title,
                            "word_count": r.word_count,
                            "method": r.method,
                            "modifiers": r.modifiers or [],
                            "b_score": r.b_score,
                            "c_click_willingness": r.c_click_willingness,
                            "score": r.final_score,
                            "final_score": r.final_score,
                            "reason": r.recommendation_reason,
                        }
                        for r in rec_rows
                    ]

                    # 所有评估过的候选（保留 Top5 + 被淘汰的，方便前端展示 Agent A/B/C 全貌）
                    cand_rows = (
                        await db.execute(
                            select(TitleCandidate)
                            .where(TitleCandidate.result_id == result_row.id)
                            .order_by(desc(TitleCandidate.final_score))
                        )
                    ).scalars().all()
                    candidates_payload = [
                        {
                            "id": c.id,
                            "sequence": c.sequence,
                            "title": c.title,
                            "word_count": c.word_count,
                            "method": c.method,
                            "modifiers": c.modifiers or [],
                            "explanation": c.explanation,
                            "b_score": c.b_score,
                            "b_score_details": c.b_score_details or {},
                            "c_click_willingness": c.c_click_willingness,
                            "c_click_reason": c.c_click_reason,
                            "c_no_click_reason": c.c_no_click_reason,
                            "c_improvement_suggestion": c.c_improvement_suggestion,
                            "final_score": c.final_score,
                            "is_eliminated": c.is_eliminated == "1",
                            "elimination_reason": c.elimination_reason,
                            "is_top5": c.is_top5 == "1",
                            "is_top3": c.is_top3 == "1",
                        }
                        for c in cand_rows
                    ]

                result_data = {
                    "task_id": task_id,
                    "status": "completed",
                    "recommendations": recommendations_payload,
                    "candidates": candidates_payload,
                    "meta": result_meta,
                }
                await progress_store.push(run_id, {
                    "event": "result",
                    "data": result_data,
                })
                top_title = recommendations_payload[0]["title"] if recommendations_payload else None
                await track_complete(run_id, result_data, display_title=f"标题生成 · {top_title[:30]}" if top_title else None)
        except Exception as e:
            logger.error(f"后台标题生成任务 {task_id} 失败: {str(e)}", exc_info=True)
            from sqlalchemy import update
            from datetime import datetime
            await db.execute(
                update(Task).where(Task.id == task_id).values(
                    status=TaskStatus.FAILED,
                    error_message=str(e),
                    completed_at=datetime.now(),
                )
            )
            await db.commit()
            if run_id:
                await progress_store.push(run_id, {
                    "event": "error",
                    "data": {"message": str(e)},
                })
                await track_fail(run_id, str(e))


@router.post("/", response_model=TitleGenerationResponse)
async def create_title_generation(
    request: TitleGenerationRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    创建标题生成任务
    
    基于选题和大纲生成标题候选，经过4个Agent协作流程输出Top 3推荐标题。
    
    ## Agent流程
    1. **Agent A (标题创作员)**: 生成10-15个标题候选，覆盖至少6种套路
    2. **Agent B (标题评审员)**: 一票否决扫描 + 6维度评分 + 筛选Top 5
    3. **Agent C (读者点击预测员)**: 模拟读者场景，预测点击意愿
    4. **Agent D (最终判定员)**: 综合评分，输出Top 3推荐标题
    
    ## 重生机制
    - 如果Top 3综合分 < 7.0，将扣分理由喂给Agent A重新生成
    - 最多重生1次，失败则标记"难以成标题"丢回人工
    """
    # 创建任务记录
    task = Task(
        id=str(uuid.uuid4()),
        title=f"标题生成任务 - {request.topic.title if request.topic else '未命名'}",
        description="基于选题和大纲生成标题候选",
        status=TaskStatus.PENDING,
        input_data={
            "topic": request.topic.dict() if request.topic else None,
            "outline": request.outline.dict() if request.outline else None,
        },
    )

    db.add(task)
    await db.commit()
    await db.refresh(task)

    # 创建进度流
    run_id = progress_store.create_run()

    # 序列化请求数据，传给后台任务（避免传递ORM session）
    request_data = request.dict()

    topic_title = request.topic.title if request.topic else "未命名"
    await track_start(
        user_id=current_user.id,
        type="title_generate",
        run_id=run_id,
        input_snapshot=request_data,
        display_title=f"标题生成 · {topic_title[:30]}",
        resume_context={
            "route": "/creation/new",
            "query": {},
        },
    )

    # 启动后台任务（Service和Agent在后台任务中延迟实例化）
    background_tasks.add_task(
        _run_title_generation_background,
        task_id=task.id,
        request_data=request_data,
        run_id=run_id,
        user_id=current_user.id,
    )

    return TitleGenerationResponse(
        task_id=task.id,
        run_id=run_id,
        status=task.status,
        message="标题生成任务已创建，正在后台执行",
    )


@router.get("/stream/{run_id}")
async def stream_title_progress(
    run_id: str,
    token: str = Query(None, description="认证 token（EventSource 不支持 header）"),
) -> StreamingResponse:
    """SSE 端点：实时推送标题生成进度。"""
    # 验证 token
    if token:
        from app.core.security import decode_token
        payload = decode_token(token)
        if not payload:
            raise HTTPException(status_code=401, detail="无效的 token")

    if not progress_store.exists(run_id):
        raise HTTPException(status_code=404, detail=f"run {run_id} 不存在或已过期")

    return StreamingResponse(
        progress_store.stream(run_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/{task_id}", response_model=TitleGenerationResultResponse)
async def get_title_generation_result(
    task_id: str,
    db: AsyncSession = Depends(get_db),
):
    """
    获取标题生成结果
    
    获取指定任务的标题生成结果，包括所有候选标题、评分和最终推荐。
    
    Args:
        task_id: 任务ID
    
    Returns:
        标题生成结果，包括:
        - 候选标题列表
        - Top 5评分结果
        - 点击预测结果
        - Top 3最终推荐
        - 生成过程归档
    """
    # 查询任务
    from sqlalchemy import select
    result = await db.execute(select(Task).where(Task.id == task_id))
    task = result.scalar_one_or_none()
    
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    
    if task.status == TaskStatus.PENDING or task.status == TaskStatus.PROCESSING:
        return TitleGenerationResultResponse(
            task_id=task.id,
            status=task.status,
            message="任务正在处理中，请稍后查询",
        )
    
    if task.status == TaskStatus.FAILED:
        return TitleGenerationResultResponse(
            task_id=task.id,
            status=task.status,
            message=task.error_message or "任务处理失败",
        )
    
    # 查询结果
    result_query = await db.execute(
        select(TitleGenerationResult).where(TitleGenerationResult.task_id == task_id)
    )
    generation_result = result_query.scalar_one_or_none()
    
    if not generation_result:
        raise HTTPException(status_code=500, detail="结果数据不存在")
    
    return TitleGenerationResultResponse(
        task_id=task.id,
        status=task.status,
        message="标题生成完成",
        result=generation_result,
    )


@router.get("/{task_id}/candidates", response_model=List[TitleCandidateResponse])
async def get_candidates(
    task_id: str,
    db: AsyncSession = Depends(get_db),
):
    """
    获取候选标题列表
    
    获取指定任务的所有候选标题（Agent A输出）。
    
    Args:
        task_id: 任务ID
    
    Returns:
        候选标题列表
    """
    # 查询任务
    from sqlalchemy import select
    result = await db.execute(select(Task).where(Task.id == task_id))
    task = result.scalar_one_or_none()
    
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    
    # 查询结果
    result_query = await db.execute(
        select(TitleGenerationResult).where(TitleGenerationResult.task_id == task_id)
    )
    generation_result = result_query.scalar_one_or_none()
    
    if not generation_result:
        raise HTTPException(status_code=404, detail="结果数据不存在")

    # to_dict() 已将 "0"/"1" 转为 bool
    return [c.to_dict() for c in generation_result.candidates]


@router.get("/{task_id}/recommendations", response_model=List[FinalRecommendationResponse])
async def get_recommendations(
    task_id: str,
    db: AsyncSession = Depends(get_db),
):
    """
    获取最终推荐标题

    获取指定任务的Top 3推荐标题（Agent D输出）。

    Args:
        task_id: 任务ID

    Returns:
        Top 3推荐标题列表
    """
    # 查询任务
    result = await db.execute(select(Task).where(Task.id == task_id))
    task = result.scalar_one_or_none()

    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")

    # 查询结果
    result_query = await db.execute(
        select(TitleGenerationResult).where(TitleGenerationResult.task_id == task_id)
    )
    generation_result = result_query.scalar_one_or_none()

    if not generation_result:
        raise HTTPException(status_code=404, detail="结果数据不存在")

    return generation_result.final_recommendations


@router.patch("/candidates/{candidate_id}", response_model=dict)
async def update_title_candidate(
    candidate_id: str,
    body: dict,
    db: AsyncSession = Depends(get_db),
):
    """保存编辑后的标题文本。

    body 格式：
    {
        "title": "修改后的标题文本"
    }
    """
    result = await db.execute(
        select(TitleCandidate).where(TitleCandidate.id == candidate_id)
    )
    candidate = result.scalar_one_or_none()
    if not candidate:
        raise HTTPException(status_code=404, detail="标题候选不存在")

    if "title" in body and body["title"]:
        candidate.title = body["title"]
        candidate.word_count = len(body["title"])

    await db.commit()
    await db.refresh(candidate)

    return {
        "code": 200,
        "message": "标题已保存",
        "data": candidate.to_dict(),
    }


@router.patch("/recommendations/{recommendation_id}", response_model=dict)
async def update_recommendation(
    recommendation_id: str,
    body: dict,
    db: AsyncSession = Depends(get_db),
):
    """保存编辑后的推荐标题。

    body 格式：
    {
        "title": "修改后的标题文本"
    }
    """
    result = await db.execute(
        select(FinalRecommendation).where(FinalRecommendation.id == recommendation_id)
    )
    rec = result.scalar_one_or_none()
    if not rec:
        raise HTTPException(status_code=404, detail="推荐标题不存在")

    if "title" in body and body["title"]:
        rec.title = body["title"]
        rec.word_count = len(body["title"])

    await db.commit()
    await db.refresh(rec)

    return {
        "code": 200,
        "message": "标题已保存",
        "data": rec.to_dict(),
    }


@router.post("/candidates/{candidate_id}/reevaluate", response_model=dict)
async def reevaluate_title_candidate(
    candidate_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """重新评估单个标题候选（只跑 B 评分 + C 点击预测）。

    返回 run_id，前端通过 SSE 获取实时进度。
    """
    result = await db.execute(
        select(TitleCandidate).where(TitleCandidate.id == candidate_id)
    )
    candidate = result.scalar_one_or_none()
    if not candidate:
        raise HTTPException(status_code=404, detail="标题候选不存在")

    # 获取关联的 result 和 task 信息
    result_row = await db.execute(
        select(TitleGenerationResult).where(TitleGenerationResult.id == candidate.result_id)
    )
    gen_result = result_row.scalar_one_or_none()
    if not gen_result:
        raise HTTPException(status_code=404, detail="标题生成结果不存在")

    task_row = await db.execute(select(Task).where(Task.id == gen_result.task_id))
    task = task_row.scalar_one_or_none()

    run_id = progress_store.create_run()

    await track_start(
        user_id=current_user.id,
        type="title_reevaluate",
        run_id=run_id,
        input_snapshot={"candidate_id": candidate_id, "title": candidate.title},
        display_title=f"标题重评 · {candidate.title[:30]}",
        resume_context={
            "route": "/creation/new",
            "query": {},
        },
    )

    async def _run():
        from app.services.title_generation.agent_b_reviewer import TitleReviewerAgent
        from app.services.title_generation.agent_c_predictor import ClickPredictorAgent
        from app.schemas.title_generation import TopicInfo, OutlineInfo

        async with AsyncSessionLocal() as bg_db:
            try:
                async def _progress_cb(event):
                    await progress_store.push(run_id, event)

                # 从 task 的 input_data 重建 topic/outline 信息
                input_data = task.input_data or {}
                raw_topic = input_data.get("topic", {})
                raw_outline = input_data.get("outline", {})

                # 安全构造 TopicInfo（direction 可能不合法，用默认值兜底）
                try:
                    topic_info = TopicInfo(**raw_topic) if raw_topic else TopicInfo(
                        title=candidate.title, direction="实践型", method=candidate.method or "", value_promise=""
                    )
                except Exception:
                    topic_info = TopicInfo(
                        title=raw_topic.get("title", candidate.title),
                        direction="实践型",
                        method=raw_topic.get("method", candidate.method or ""),
                        value_promise=raw_topic.get("value_promise", ""),
                    )

                try:
                    outline_info = OutlineInfo(**raw_outline) if raw_outline else OutlineInfo(
                        section_titles=[], key_points=[]
                    )
                except Exception:
                    outline_info = OutlineInfo(
                        section_titles=raw_outline.get("section_titles", []),
                        key_points=raw_outline.get("key_points", []),
                    )

                # ── Agent B ──
                await _progress_cb({"event": "step_start", "data": {"step": 1, "agent": "Agent B", "action": "正在重新评分..."}})
                agent_b = TitleReviewerAgent()
                b_result = await agent_b.execute(
                    candidates=[{
                        "title": candidate.title,
                        "word_count": candidate.word_count,
                        "method": candidate.method,
                        "modifiers": candidate.modifiers or [],
                        "explanation": candidate.explanation or "",
                    }],
                    topic=topic_info,
                    outline=outline_info,
                )
                await _progress_cb({"event": "step_done", "data": {"step": 1, "agent": "Agent B"}})

                # ── Agent C ──
                await _progress_cb({"event": "step_start", "data": {"step": 2, "agent": "Agent C", "action": "正在预测点击意愿..."}})
                agent_c = ClickPredictorAgent()
                c_result = await agent_c.execute(
                    titles=[{
                        "title": candidate.title,
                        "word_count": candidate.word_count,
                        "method": candidate.method,
                    }],
                    topic=topic_info,
                    outline=outline_info,
                )
                await _progress_cb({"event": "step_done", "data": {"step": 2, "agent": "Agent C"}})

                # 更新候选评分
                # Agent B 返回格式: { "scores": [...], "top5": [...] }
                scored = b_result.get("scores") or b_result.get("top5") or []
                if scored:
                    s = scored[0]
                    candidate.b_score = s.get("b_score", candidate.b_score)
                    candidate.b_score_details = s.get("b_score_details", candidate.b_score_details)

                # Agent C 返回格式: { "predictions": [...] }，key 无 c_ 前缀
                c_data = c_result.get("predictions", [])
                if c_data:
                    c = c_data[0]
                    candidate.c_click_willingness = c.get("click_willingness", candidate.c_click_willingness)
                    candidate.c_click_reason = c.get("click_reason", candidate.c_click_reason)
                    candidate.c_no_click_reason = c.get("no_click_reason", candidate.c_no_click_reason)
                    candidate.c_improvement_suggestion = c.get("improvement_suggestion", candidate.c_improvement_suggestion)

                # 重新计算综合分
                if candidate.b_score is not None and candidate.c_click_willingness is not None:
                    candidate.final_score = round(candidate.b_score * 0.6 + candidate.c_click_willingness * 0.4, 2)

                await bg_db.commit()
                await bg_db.refresh(candidate)

                # 推送结果
                await progress_store.push(run_id, {
                    "event": "result",
                    "data": candidate.to_dict(),
                })
                await _progress_cb({"event": "complete", "data": {"step": 2, "agent": "Agent C"}})
                await track_complete(run_id, candidate.to_dict())

            except Exception as e:
                logger.error(f"标题重新评估失败: {e}", exc_info=True)
                await progress_store.push(run_id, {
                    "event": "error",
                    "data": {"message": str(e)},
                })
                await track_fail(run_id, str(e))

    asyncio.create_task(_run())

    return {
        "code": 200,
        "message": "重新评估任务已提交",
        "data": {"run_id": run_id},
    }
