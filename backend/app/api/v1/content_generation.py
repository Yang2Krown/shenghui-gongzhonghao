"""正文生成 API 端点。

提供正文生成的 RESTful 接口，支持同步预览和异步任务两种模式。
与选题挖掘 API（topic_candidates.py）完全独立。
"""

import asyncio
from typing import Any, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_current_user
from app.core.progress import progress_store
from app.db.session import get_db
from app.models.user import User

router = APIRouter()


# ──────────────────────────────────────────────
# 请求/响应 Schema
# ──────────────────────────────────────────────

class SectionBriefRequest(BaseModel):
    """大纲单节请求。"""
    section_number: int
    subtitle: str
    core_points: list[str] = Field(default_factory=list)
    spread_role: Optional[str] = None
    word_estimate: int = 500
    notes: Optional[str] = None


class StyleParamsRequest(BaseModel):
    """风格参数请求。"""
    tone: Optional[str] = None
    banned_words: list[str] = Field(default_factory=list)
    preferred_words: list[str] = Field(default_factory=list)
    sample_articles: list[str] = Field(default_factory=list)


class ContentGenerationRequest(BaseModel):
    """正文生成请求。"""
    candidate_id: int = Field(description="选题候选 ID")
    outline_id: int = Field(description="大纲 ID")
    style_params: Optional[StyleParamsRequest] = None


class ContentGenerationSyncRequest(BaseModel):
    """正文生成同步请求（直接传入数据，不查库）。"""
    topic_title: str
    topic_direction: Optional[str] = None
    topic_routine: Optional[str] = None
    value_promise: Optional[str] = None
    sections: list[SectionBriefRequest]
    style_params: Optional[StyleParamsRequest] = None


class GoldSentenceResponse(BaseModel):
    """金句响应。"""
    sentence_id: int
    sentence_type: str
    location: str
    content: str
    word_count: int


class DiagnosisResponse(BaseModel):
    """诊断报告响应。"""
    total_score: float
    recommended_action: str
    high_priority: list[str]
    medium_priority: list[str]
    low_priority: list[str]
    dimensions: dict


class ContentGenerationResponse(BaseModel):
    """正文生成响应。"""
    final_text: str
    final_word_count: int
    section_count: int
    gold_sentences: list[GoldSentenceResponse]
    diagnosis: DiagnosisResponse
    rewrite_count: int
    style_anchor: str


# ──────────────────────────────────────────────
# API 端点
# ──────────────────────────────────────────────

@router.post("/generate", response_model=dict)
async def generate_content_async(
    req: ContentGenerationRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    """正文生成（SSE 实时进度）。

    返回 run_id，前端可通过 GET /content-generation/stream/{run_id} 获取实时进度。
    正文数据通过 SSE 的 result 事件返回（在 complete 之后）。
    """
    run_id = progress_store.create_run()

    async def _run():
        from sqlalchemy import select
        from app.db.session import AsyncSessionLocal
        from app.services.content_generation.orchestrator import generate_content as cg_generate
        from app.services.content_generation.schemas import ContentGenerationInput, StyleParams, SectionBrief
        from app.models.topic_candidate import TopicCandidate
        from app.models.outline import Outline

        async with AsyncSessionLocal() as bg_db:
            try:
                # 查询选题和大纲
                candidate_result = await bg_db.execute(
                    select(TopicCandidate).where(TopicCandidate.id == req.candidate_id)
                )
                candidate = candidate_result.scalar_one_or_none()
                if not candidate:
                    raise ValueError(f"选题候选 {req.candidate_id} 不存在")

                outline_result = await bg_db.execute(
                    select(Outline).where(Outline.id == req.outline_id)
                )
                outline = outline_result.scalar_one_or_none()
                if not outline:
                    raise ValueError(f"大纲 {req.outline_id} 不存在")

                style_params = None
                if req.style_params:
                    style_params = StyleParams(
                        tone=req.style_params.tone,
                        banned_words=req.style_params.banned_words,
                        preferred_words=req.style_params.preferred_words,
                        sample_articles=req.style_params.sample_articles,
                    )

                # 构建 sections
                from app.services.content_generation.schemas import SectionBrief
                sections = []
                for s in (outline.sections or []):
                    sections.append(SectionBrief(
                        section_number=s.get("section_number", 0),
                        subtitle=s.get("title", ""),
                        core_points=s.get("core_points", []),
                        spread_role=s.get("spread_role"),
                        word_estimate=s.get("word_count", 500),
                        notes=s.get("notes"),
                    ))

                inp = ContentGenerationInput(
                    topic_title=candidate.title,
                    topic_direction=candidate.direction,
                    topic_routine=candidate.routine,
                    value_promise=candidate.value_promise,
                    sections=sections,
                    style_params=style_params,
                    user_id=current_user.id,
                )

                async def _progress_cb(event):
                    await progress_store.push(run_id, event)

                output = await cg_generate(inp, progress_callback=_progress_cb)

                # 发送结果数据
                def _dim(d):
                    return {
                        "score": d.score,
                        "weight": d.weight,
                        "evaluation": d.evaluation,
                        "suggestions": d.suggestions,
                    }

                diag = output.diagnosis
                await progress_store.push(run_id, {
                    "event": "result",
                    "data": {
                        "final_text": output.final_text,
                        "final_word_count": output.final_word_count,
                        "section_count": output.section_count,
                        "section_word_counts": output.section_word_counts,
                        "rewrite_count": output.agent_c_rewrite_count,
                        "style_anchor": output.style_anchor,
                        "gold_sentences": [
                            {
                                "sentence_id": s.sentence_id,
                                "sentence_type": s.sentence_type,
                                "location": s.location,
                                "section_number": s.section_number,
                                "insert_method": s.insert_method,
                                "content": s.content,
                                "word_count": s.word_count,
                            }
                            for s in output.gold_sentences
                        ],
                        "rewrite_table": [
                            {
                                "location": it.location,
                                "ai_taste_type": it.ai_taste_type,
                                "ai_taste_subtype": it.ai_taste_subtype,
                                "priority": it.priority,
                                "original_text": it.original_text,
                                "rewritten_text": it.rewritten_text,
                                "reason": it.reason,
                            }
                            for it in (output.rewrite_table or [])
                        ],
                        "diagnosis": {
                            "total_score": diag.total_score,
                            "recommended_action": diag.recommended_action,
                            "high_priority": diag.high_priority,
                            "medium_priority": diag.medium_priority,
                            "low_priority": diag.low_priority,
                            "dimensions": {
                                "title_fulfillment": _dim(diag.title_fulfillment),
                                "outline_alignment": _dim(diag.outline_alignment),
                                "word_compliance": _dim(diag.word_compliance),
                                "style_consistency": _dim(diag.style_consistency),
                                "deai_thoroughness": _dim(diag.deai_thoroughness),
                                "gold_sentence_completeness": _dim(diag.gold_sentence_completeness),
                                "opening_quality": _dim(diag.opening_quality),
                                "ending_quality": _dim(diag.ending_quality),
                            },
                        },
                    },
                })
            except Exception as e:
                await progress_store.push(run_id, {
                    "event": "error",
                    "data": {"message": str(e)},
                })

    asyncio.create_task(_run())

    return {
        "code": 200,
        "message": "正文生成任务已提交",
        "data": {"run_id": run_id},
    }


@router.get("/stream/{run_id}")
async def stream_content_progress(
    run_id: str,
    token: str = Query(None, description="认证 token（EventSource 不支持 header）"),
) -> StreamingResponse:
    """SSE 端点：实时推送正文生成进度。"""
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


@router.post("/generate/sync", response_model=dict)
async def generate_content_sync(
    req: ContentGenerationSyncRequest,
    current_user: User = Depends(get_current_user),
) -> Any:
    """同步正文生成（直接传入数据，不查库，适合预览/调试）。

    直接调用 4 Agent 流程，返回完整结果。
    耗时约 30-60 秒。
    """
    import asyncio
    from app.services.content_generation.orchestrator import generate_content
    from app.services.content_generation.schemas import (
        ContentGenerationInput,
        SectionBrief,
        StyleParams,
    )

    # 构建输入
    sections = [
        SectionBrief(
            section_number=s.section_number,
            subtitle=s.subtitle,
            core_points=s.core_points,
            spread_role=s.spread_role,
            word_estimate=s.word_estimate,
            notes=s.notes,
        )
        for s in req.sections
    ]

    style_params = None
    if req.style_params:
        style_params = StyleParams(
            tone=req.style_params.tone,
            banned_words=req.style_params.banned_words,
            preferred_words=req.style_params.preferred_words,
            sample_articles=req.style_params.sample_articles,
        )

    inp = ContentGenerationInput(
        topic_title=req.topic_title,
        topic_direction=req.topic_direction,
        topic_routine=req.topic_routine,
        value_promise=req.value_promise,
        sections=sections,
        style_params=style_params,
        user_id=current_user.id,
    )

    try:
        output = await generate_content(inp)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"正文生成失败: {str(e)}",
        )

    return {
        "code": 200,
        "message": "正文生成完成",
        "data": ContentGenerationResponse(
            final_text=output.final_text,
            final_word_count=output.final_word_count,
            section_count=output.section_count,
            gold_sentences=[
                GoldSentenceResponse(
                    sentence_id=s.sentence_id,
                    sentence_type=s.sentence_type,
                    location=s.location,
                    content=s.content,
                    word_count=s.word_count,
                )
                for s in output.gold_sentences
            ],
            diagnosis=DiagnosisResponse(
                total_score=output.diagnosis.total_score,
                recommended_action=output.diagnosis.recommended_action,
                high_priority=output.diagnosis.high_priority,
                medium_priority=output.diagnosis.medium_priority,
                low_priority=output.diagnosis.low_priority,
                dimensions={
                    "title_fulfillment": output.diagnosis.title_fulfillment.dict(),
                    "outline_alignment": output.diagnosis.outline_alignment.dict(),
                    "word_compliance": output.diagnosis.word_compliance.dict(),
                    "style_consistency": output.diagnosis.style_consistency.dict(),
                    "deai_thoroughness": output.diagnosis.deai_thoroughness.dict(),
                    "gold_sentence_completeness": output.diagnosis.gold_sentence_completeness.dict(),
                    "opening_quality": output.diagnosis.opening_quality.dict(),
                    "ending_quality": output.diagnosis.ending_quality.dict(),
                },
            ),
            rewrite_count=output.agent_c_rewrite_count,
            style_anchor=output.style_anchor,
        ).dict(),
    }


@router.get("/task/{task_id}", response_model=dict)
async def get_task_status(
    task_id: str,
    current_user: User = Depends(get_current_user),
) -> Any:
    """查询正文生成任务状态。"""
    from app.core.celery_app import celery_app

    result = celery_app.AsyncResult(task_id)

    response = {
        "code": 200,
        "data": {
            "task_id": task_id,
            "status": result.status,
            "result": result.result if result.ready() else None,
        },
    }

    if result.failed():
        response["data"]["error"] = str(result.result)

    return response


class ContentReevaluateRequest(BaseModel):
    """正文重新评估请求（只跑 Agent D）。"""
    text: str = Field(description="当前编辑后的正文文本")
    title: str = Field(description="文章标题")
    style_anchor: str = Field(default="", description="风格锚点")
    sections: list[SectionBriefRequest] = Field(default_factory=list, description="大纲各节")
    gold_sentences: list[dict] = Field(default_factory=list, description="金句列表")


@router.post("/reevaluate", response_model=dict)
async def reevaluate_content(
    req: ContentReevaluateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    """重新评估正文（只跑 Agent D 8 维度诊断）。

    接收当前编辑后的正文文本，运行 Agent D 诊断评分。
    返回 run_id，前端通过 SSE 获取实时进度。
    """
    run_id = progress_store.create_run()

    async def _run():
        from app.services.content_generation.schemas import (
            ContentGenerationInput, SectionBrief, AgentAOutput, AgentBOutput,
            AgentCOutput, GoldSentence, SectionContent, GoldSentenceSeed,
        )
        from app.services.content_generation.agent_d_inspector import integrate_and_inspect

        try:
            async def _progress_cb(event):
                await progress_store.push(run_id, event)

            await _progress_cb({"event": "step_start", "data": {"step": 1, "agent": "Agent D", "action": "正在重新诊断评分..."}})

            # 构建输入
            sections = [
                SectionBrief(
                    section_number=s.section_number,
                    subtitle=s.subtitle,
                    core_points=s.core_points,
                    spread_role=s.spread_role,
                    word_estimate=s.word_estimate,
                    notes=s.notes,
                )
                for s in req.sections
            ] if req.sections else [SectionBrief(section_number=1, subtitle="", core_points=[])]

            inp = ContentGenerationInput(
                topic_title=req.title,
                sections=sections,
                user_id=current_user.id,
            )

            # 构造最小化的 Agent A 输出
            agent_a = AgentAOutput(
                style_anchor=req.style_anchor or "中性叙述",
                full_text=req.text,
                total_word_count=len(req.text),
                section_count=len(sections),
                sections=[
                    SectionContent(
                        section_number=s.section_number,
                        subtitle=s.subtitle,
                        content="",
                        word_count=0,
                    )
                    for s in sections
                ],
                gold_seeds=[],
            )

            # 构造最小化的 Agent B 输出
            gold = req.gold_sentences or []
            agent_b = AgentBOutput(
                sentences=[
                    GoldSentence(
                        sentence_id=i + 1,
                        sentence_type=g.get("sentence_type", "金句"),
                        location=g.get("location", ""),
                        section_number=g.get("section_number", 1),
                        insert_method="新增",
                        content=g.get("content", ""),
                        word_count=len(g.get("content", "")),
                    )
                    for i, g in enumerate(gold)
                ] if gold else [
                    GoldSentence(
                        sentence_id=1, sentence_type="默认", location="全文",
                        section_number=1, insert_method="新增", content="无", word_count=2,
                    )
                ],
            )

            # 构造最小化的 Agent C 输出
            agent_c = AgentCOutput(
                rewritten_text=req.text,
                rewritten_word_count=len(req.text),
                original_word_count=len(req.text),
                word_change_pct=0.0,
                rewrite_table=[],
            )

            # 调用 Agent D
            diagnosis = await integrate_and_inspect(inp, agent_a, agent_b, agent_c)

            await _progress_cb({"event": "step_done", "data": {"step": 1, "agent": "Agent D"}})

            def _dim(d):
                return {
                    "score": d.score,
                    "weight": d.weight,
                    "evaluation": d.evaluation,
                    "suggestions": d.suggestions,
                }

            result_data = {
                "total_score": diagnosis.total_score,
                "recommended_action": diagnosis.recommended_action,
                "high_priority": diagnosis.high_priority,
                "medium_priority": diagnosis.medium_priority,
                "low_priority": diagnosis.low_priority,
                "dimensions": {
                    "title_fulfillment": _dim(diagnosis.title_fulfillment),
                    "outline_alignment": _dim(diagnosis.outline_alignment),
                    "word_compliance": _dim(diagnosis.word_compliance),
                    "style_consistency": _dim(diagnosis.style_consistency),
                    "deai_thoroughness": _dim(diagnosis.deai_thoroughness),
                    "gold_sentence_completeness": _dim(diagnosis.gold_sentence_completeness),
                    "opening_quality": _dim(diagnosis.opening_quality),
                    "ending_quality": _dim(diagnosis.ending_quality),
                },
            }

            await progress_store.push(run_id, {
                "event": "result",
                "data": result_data,
            })
            await _progress_cb({"event": "complete", "data": {"step": 1, "agent": "Agent D"}})

        except Exception as e:
            import logging
            logging.getLogger(__name__).error(f"正文重新评估失败: {e}", exc_info=True)
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
