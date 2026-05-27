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
from app.services.generation_tracker import track_start, track_complete, track_fail

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

    await track_start(
        user_id=current_user.id,
        type="content_generate",
        run_id=run_id,
        input_snapshot={"candidate_id": req.candidate_id, "outline_id": req.outline_id},
        display_title=f"正文生成 · 选题#{req.candidate_id}",
        candidate_id=req.candidate_id,
        resume_context={
            "route": "/creation/new",
            "query": {"candidate_id": req.candidate_id},
        },
    )

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
                await track_complete(run_id, {"final_word_count": output.final_word_count, "rewrite_count": output.agent_c_rewrite_count, "diagnosis_score": diag.total_score})
            except Exception as e:
                await progress_store.push(run_id, {
                    "event": "error",
                    "data": {"message": str(e)},
                })
                await track_fail(run_id, str(e))

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
    """重新评估正文（只跑 Agent D 诊断，与生成流水线完全解耦）。

    接收当前编辑后的正文文本，运行 Agent D 诊断评分。
    返回 run_id，前端通过 SSE 获取实时进度。
    """
    from app.services.llm import get_llm_client
    from app.services.llm.llm_client import ChatMessage, parse_json_loose

    run_id = progress_store.create_run()

    await track_start(
        user_id=current_user.id,
        type="content_reevaluate",
        run_id=run_id,
        input_snapshot={"title": req.title, "text_length": len(req.text)},
        display_title=f"正文重评 · {req.title[:30]}",
        resume_context={
            "route": "/creation/new",
            "query": {},
        },
    )

    async def _run():
        try:
            async def _progress_cb(event):
                await progress_store.push(run_id, event)

            await _progress_cb({"event": "step_start", "data": {"step": 1, "agent": "Agent D", "action": "正在重新诊断评分..."}})

            # 构建大纲文本
            sections_text = "\n".join(
                f"第{s.section_number}节: {s.subtitle}（字数预估: {s.word_estimate}）"
                for s in req.sections
            ) if req.sections else "无大纲"

            # 构建金句文本
            gold_text = "\n".join(
                f"- [{g.get('sentence_type', '金句')}] \"{g.get('content', '')}\""
                for g in (req.gold_sentences or [])
            ) if req.gold_sentences else "无"

            system_prompt = """\
你是正文诊断员，负责对文章做 8 维度评分并输出诊断报告。

【8 维度评分】
| 维度 | 权重 | 评分依据 |
|------|------|---------|
| 标题承诺兑现度 | 20% | 标题说的事正文里都给到了吗 |
| 大纲结构对应度 | 15% | 每节是否按大纲展开 |
| 字数合规 | 10% | 总字数 + 单节字数是否合规 |
| 风格统一性 | 15% | 全文语气是否一致 |
| 去 AI 味彻底度 | 15% | 是否还有残留的 AI 味 |
| 金句完整度 | 10% | 金句是否到位、分布是否合理 |
| 开头质量 | 10% | 前 200 字是否抓人 |
| 结尾升华度 | 5% | 是否避免烂尾 |

评分锚点：
- 9-10：优秀，无明显问题
- 7-8：良好，有小瑕疵
- 4-6：一般，有明显问题
- 1-3：差，严重问题

请严格按以下 JSON 格式输出（不加 markdown 包裹）：
{
  "dimensions": {
    "title_fulfillment": { "score": 0, "weight": 0.20, "evaluation": "", "suggestions": [] },
    "outline_alignment": { "score": 0, "weight": 0.15, "evaluation": "", "suggestions": [] },
    "word_compliance": { "score": 0, "weight": 0.10, "evaluation": "", "suggestions": [] },
    "style_consistency": { "score": 0, "weight": 0.15, "evaluation": "", "suggestions": [] },
    "deai_thoroughness": { "score": 0, "weight": 0.15, "evaluation": "", "suggestions": [] },
    "gold_sentence_completeness": { "score": 0, "weight": 0.10, "evaluation": "", "suggestions": [] },
    "opening_quality": { "score": 0, "weight": 0.10, "evaluation": "", "suggestions": [] },
    "ending_quality": { "score": 0, "weight": 0.05, "evaluation": "", "suggestions": [] }
  },
  "high_priority": [],
  "medium_priority": [],
  "low_priority": [],
  "recommended_action": "接受发布"
}"""

            user_prompt = f"""【标题】{req.title}

【大纲】
{sections_text}

【风格锚点】{req.style_anchor or '中性叙述'}

【金句清单】
{gold_text}

【正文】
{req.text}

请对以上正文做 8 维度诊断评分，严格按 JSON 格式输出。"""

            client = get_llm_client()
            messages = [
                ChatMessage(role="system", content=system_prompt),
                ChatMessage(role="user", content=user_prompt),
            ]

            result = await client.chat(
                messages=messages,
                temperature=0.3,
                max_tokens=4000,
                json_mode=True,
            )

            parsed = parse_json_loose(result.text)
            if not parsed or "dimensions" not in parsed:
                raise ValueError(f"诊断输出解析失败: {result.text[:300]}")

            dims = parsed["dimensions"]
            total_score = 0.0
            weights = {
                "title_fulfillment": 0.20,
                "outline_alignment": 0.15,
                "word_compliance": 0.10,
                "style_consistency": 0.15,
                "deai_thoroughness": 0.15,
                "gold_sentence_completeness": 0.10,
                "opening_quality": 0.10,
                "ending_quality": 0.05,
            }
            for key, weight in weights.items():
                d = dims.get(key, {})
                total_score += (d.get("score", 0) or 0) * weight
            total_score = round(total_score, 1)

            result_data = {
                "total_score": total_score,
                "recommended_action": parsed.get("recommended_action", "局部手改"),
                "high_priority": parsed.get("high_priority", []),
                "medium_priority": parsed.get("medium_priority", []),
                "low_priority": parsed.get("low_priority", []),
                "dimensions": {
                    key: {
                        "score": dims.get(key, {}).get("score", 0),
                        "weight": weights[key],
                        "evaluation": dims.get(key, {}).get("evaluation", ""),
                        "suggestions": dims.get(key, {}).get("suggestions", []),
                    }
                    for key in weights
                },
            }

            await progress_store.push(run_id, {
                "event": "result",
                "data": result_data,
            })
            await _progress_cb({"event": "step_done", "data": {"step": 1, "agent": "Agent D"}})
            await _progress_cb({"event": "complete", "data": {"step": 1, "agent": "Agent D"}})
            await track_complete(run_id, result_data)

        except Exception as e:
            import logging
            logging.getLogger(__name__).error(f"正文重新评估失败: {e}", exc_info=True)
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
