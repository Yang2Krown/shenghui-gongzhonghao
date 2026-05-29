"""
独立标题生成端点

基于文章内容直接生成标题，复用创作工作流中的 4 Agent 标题生成流水线。
"""

import asyncio
import logging
from typing import Optional
from pydantic import BaseModel, Field

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse

from app.core.progress import progress_store
from app.core.security import get_current_user
from app.models.user import User
from app.services.generation_tracker import track_start, track_complete, track_fail

logger = logging.getLogger(__name__)

router = APIRouter()


class StandaloneTitleRequest(BaseModel):
    """独立标题生成请求"""
    content: str = Field(..., min_length=10, description="文章全文或内容摘要")


class StandaloneTitleResponse(BaseModel):
    """独立标题生成响应"""
    run_id: str = Field(..., description="进度流 ID")
    message: str = Field(default="标题生成任务已创建")


async def _extract_topic_outline_from_content(content: str) -> dict:
    """
    从文章内容中提取选题信息和大纲信息，
    构造 TitleGenerationRequest 所需的 topic + outline。
    """
    from app.services.llm import get_llm_client
    from app.services.llm.llm_client import ChatMessage, parse_json_loose
    import json

    prompt = f"""请分析以下文章内容，提取结构化信息。

【文章内容】
{content[:8000]}

【任务】
请严格按照以下 JSON 格式输出：
{{
  "topic": {{
    "title": "文章的核心主题（一句话概括）",
    "direction": "内容方向，必须是以下之一：实践型、解决问题型、教程型、观点型、整活型、资讯型",
    "method": "该文章最适合的标题套路，如痛点直击型、数字冲击型等",
    "value_promise": "文章能给读者带来的核心价值"
  }},
  "outline": {{
    "section_titles": ["第一部分标题", "第二部分标题", "..."],
    "key_points": ["关键信息点1", "关键信息点2", "..."],
    "spread_tags": ["传播标签1", "传播标签2"]
  }}
}}

注意：
- direction 必须从给定的 6 个选项中选择
- section_titles 和 key_points 至少各 1 项
- 如果文章内容较短，可以根据内容合理推断"""

    client = get_llm_client()
    messages = [
        ChatMessage(role="system", content="你是一位资深的公众号内容分析师，擅长从文章中提取结构化信息。请严格按照 JSON 格式输出。"),
        ChatMessage(role="user", content=prompt),
    ]
    result = await client.chat(messages=messages, temperature=0.3, json_mode=True)
    response = result.text or ""

    parsed = parse_json_loose(response)
    if parsed is not None:
        return parsed
    try:
        return json.loads(response)
    except (json.JSONDecodeError, TypeError):
        logger.warning(f"内容分析 JSON 解析失败: {response[:500]}")
        return {}


async def _run_standalone_title_background(content: str, run_id: str, user_id: int = None):
    """后台执行标题生成任务"""
    from app.db.session import AsyncSessionLocal
    from app.services.title_generation_service import TitleGenerationService
    from app.schemas.title_generation import TitleGenerationRequest, TopicInfo, OutlineInfo
    from app.models.task import Task, TaskStatus
    from datetime import datetime
    import uuid

    try:
        # Step 0: 从文章内容中提取 topic + outline
        await progress_store.push(run_id, {
            "event": "step_start",
            "data": {
                "step": 0,
                "agent": "内容分析师",
                "action": "正在分析文章内容，提取选题和大纲...",
                "avatar": "/agents/title-a.png",
            },
        })

        extracted = await _extract_topic_outline_from_content(content)
        raw_topic = extracted.get("topic", {})
        raw_outline = extracted.get("outline", {})

        # 安全构造 TopicInfo
        valid_directions = ["实践型", "解决问题型", "教程型", "观点型", "整活型", "资讯型"]
        direction = raw_topic.get("direction", "实践型")
        if direction not in valid_directions:
            direction = "实践型"

        topic = TopicInfo(
            title=raw_topic.get("title", "未命名主题"),
            direction=direction,
            method=raw_topic.get("method", ""),
            value_promise=raw_topic.get("value_promise", ""),
        )

        section_titles = raw_outline.get("section_titles", [])
        key_points = raw_outline.get("key_points", [])
        if not section_titles:
            section_titles = [topic.title]
        if not key_points:
            key_points = [topic.value_promise or topic.title]

        outline = OutlineInfo(
            section_titles=section_titles,
            key_points=key_points,
            spread_tags=raw_outline.get("spread_tags", []),
        )

        await progress_store.push(run_id, {
            "event": "step_done",
            "data": {"step": 0, "agent": "内容分析师"},
        })

        request = TitleGenerationRequest(topic=topic, outline=outline)

        # Step 1-4: 复用原有的 4 Agent 标题生成流水线
        async with AsyncSessionLocal() as db:
            task = Task(
                id=str(uuid.uuid4()),
                title=f"独立标题生成 - {topic.title[:50]}",
                description="基于文章内容的独立标题生成",
                status=TaskStatus.PENDING,
                input_data={
                    "topic": topic.dict(),
                    "outline": outline.dict(),
                },
            )
            db.add(task)
            await db.commit()
            await db.refresh(task)

            async def _progress_cb(event):
                # 将 step 编号 +1（因为 step 0 已经被内容分析占用）
                data = event.get("data", {})
                if "step" in data:
                    data = {**data, "step": data["step"] + 1}
                    event = {**event, "data": data}
                await progress_store.push(run_id, event)

            service = TitleGenerationService(db, progress_callback=_progress_cb)
            await service.execute_title_generation(
                task_id=task.id,
                request=request,
            )

            # 查询结果并推送
            from sqlalchemy import select, desc
            from app.models.title import TitleGenerationResult, TitleCandidate, FinalRecommendation

            result_row = (
                await db.execute(
                    select(TitleGenerationResult).where(TitleGenerationResult.task_id == task.id)
                )
            ).scalar_one_or_none()

            recommendations_payload = []
            candidates_payload = []
            result_meta = None

            if result_row:
                result_meta = {
                    "result_id": result_row.id,
                    "total_candidates": result_row.total_candidates,
                    "covered_methods": result_row.covered_methods,
                    "eliminated_count": result_row.eliminated_count,
                    "regeneration_count": result_row.regeneration_count,
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

                cand_rows = (
                    await db.execute(
                        select(TitleCandidate)
                        .where(TitleCandidate.result_id == result_row.id)
                        .order_by(TitleCandidate.sequence)
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
                        "b_summary": c.b_summary,
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

            # 构造提取的选题信息，附在结果中方便前端展示
            result_data = {
                "task_id": task.id,
                "status": "completed",
                "extracted_topic": topic.dict(),
                "extracted_outline": outline.dict(),
                "recommendations": recommendations_payload,
                "candidates": candidates_payload,
                "meta": result_meta,
            }
            await progress_store.push(run_id, {
                "event": "result",
                "data": result_data,
            })
            top_title = recommendations_payload[0]["title"] if recommendations_payload else None
            await track_complete(
                run_id,
                result_data,
                display_title=f"标题生成 · {top_title[:30]}" if top_title else None,
            )

    except Exception as e:
        logger.error(f"独立标题生成失败: {str(e)}", exc_info=True)
        await progress_store.push(run_id, {
            "event": "error",
            "data": {"message": str(e)},
        })
        await track_fail(run_id, str(e))


@router.post("/generate", response_model=StandaloneTitleResponse)
async def standalone_title_generate(
    request: StandaloneTitleRequest,
    current_user: User = Depends(get_current_user),
):
    """
    独立标题生成

    输入文章全文或摘要，自动提取选题和大纲信息，
    然后复用标题生成流水线（A创作 5 个 → B生成简介 → C点击分析；不打分）。
    """
    run_id = progress_store.create_run()

    await track_start(
        user_id=current_user.id,
        type="standalone_title",
        run_id=run_id,
        input_snapshot={"content_length": len(request.content)},
        display_title=f"标题生成 · {request.content[:30]}...",
        resume_context={
            "route": "/standalone-title",
            "query": {},
        },
    )

    asyncio.create_task(
        _run_standalone_title_background(
            content=request.content,
            run_id=run_id,
            user_id=current_user.id,
        )
    )

    return StandaloneTitleResponse(run_id=run_id)


@router.get("/stream/{run_id}")
async def stream_standalone_title_progress(
    run_id: str,
    token: str = Query(None, description="认证 token"),
) -> StreamingResponse:
    """SSE 端点：实时推送标题生成进度。"""
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
