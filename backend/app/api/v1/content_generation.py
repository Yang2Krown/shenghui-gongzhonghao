"""正文生成 API 端点。

提供正文生成的 RESTful 接口，支持同步预览和异步任务两种模式。
与选题挖掘 API（topic_candidates.py）完全独立。
"""

from typing import Any, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_current_user
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
    """异步正文生成（Celery 任务）。

    提交正文生成任务，返回任务 ID。可通过 /tasks/{task_id} 查询进度。
    """
    from app.tasks.content_generation_tasks import generate_article_task

    style_dict = req.style_params.dict() if req.style_params else None

    task = generate_article_task.delay(
        candidate_id=req.candidate_id,
        outline_id=req.outline_id,
        user_id=current_user.id,
        style_params=style_dict,
    )

    return {
        "code": 200,
        "message": "正文生成任务已提交",
        "data": {
            "task_id": task.id,
            "status": "PENDING",
        },
    }


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
