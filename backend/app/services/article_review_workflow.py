"""文章复盘可恢复工作流的持久化辅助。

旧版 ArticleReview.change_groups 继续作为兼容投影；本模块把每次运行、
阶段、语义块、对齐结果和候选方法论保存到规范化表中，供断线恢复和人工编辑使用。
"""

from __future__ import annotations

from typing import Any, Optional

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.timezone import utcnow
from app.models.article_review import (
    ArticleReview,
    ArticleReviewChange,
    ArticleReviewExperienceSource,
    ArticleReviewMethodologyCandidate,
    ArticleReviewReorderEvent,
    ArticleReviewRun,
    ArticleReviewSemanticBlock,
    ArticleReviewStage,
)


STAGE_DEFINITIONS = (
    ("parse", 1, "文件解析"),
    ("semantic_segmentation", 2, "语义分段"),
    ("semantic_alignment", 3, "语义对齐与差异识别"),
    ("ai_review", 4, "AI 复盘分析"),
    ("methodology", 5, "方法论候选"),
)
STAGE_ORDER = {key: order for key, order, _label in STAGE_DEFINITIONS}
STAGE_LABELS = {key: label for key, _order, label in STAGE_DEFINITIONS}
QUEUED_STAGE_STALE_SECONDS = 10 * 60
RUNNING_STAGE_STALE_SECONDS = 45 * 60
_UNSET = object()


def is_stage_stale(stage: ArticleReviewStage, *, now=None) -> bool:
    """判断持久化任务是否已失联，让用户可以安全地重提当前阶段。"""

    if stage.status not in {"queued", "running"}:
        return False
    heartbeat = stage.updated_at or stage.started_at or stage.created_at
    if heartbeat is None:
        return True
    age_seconds = max(0.0, ((now or utcnow()) - heartbeat).total_seconds())
    threshold = (
        QUEUED_STAGE_STALE_SECONDS
        if stage.status == "queued"
        else RUNNING_STAGE_STALE_SECONDS
    )
    return age_seconds >= threshold


async def load_current_run(
    db: AsyncSession,
    review_id: int,
    *,
    with_stages: bool = True,
) -> Optional[ArticleReviewRun]:
    query = (
        select(ArticleReviewRun)
        .where(ArticleReviewRun.review_id == review_id)
        .order_by(ArticleReviewRun.run_no.desc(), ArticleReviewRun.id.desc())
    )
    if with_stages:
        query = query.options(selectinload(ArticleReviewRun.stages))
    return (await db.execute(query)).scalars().first()


async def create_run_with_stages(
    db: AsyncSession,
    review: ArticleReview,
    *,
    run_id: str,
    created_by: Optional[int],
) -> ArticleReviewRun:
    existing = await load_current_run(db, review.id, with_stages=False)
    if existing is not None and existing.run_id == run_id:
        return existing
    latest_no = existing.run_no if existing is not None else 0
    run = ArticleReviewRun(
        review_id=review.id,
        run_id=run_id,
        run_no=latest_no + 1,
        status="queued",
        current_stage="parse",
        requested_stage="parse",
        created_by=created_by,
    )
    db.add(run)
    await db.flush()
    for stage_key, stage_order, _label in STAGE_DEFINITIONS:
        db.add(ArticleReviewStage(
            review_run_id=run.id,
            stage_key=stage_key,
            stage_order=stage_order,
            status="queued" if stage_order == 1 else "blocked",
            progress=0,
        ))
    await db.flush()
    return run


async def get_stage(
    db: AsyncSession,
    run_id: str,
    stage_key: str,
) -> Optional[ArticleReviewStage]:
    return (await db.execute(
        select(ArticleReviewStage)
        .join(ArticleReviewRun, ArticleReviewRun.id == ArticleReviewStage.review_run_id)
        .where(
            ArticleReviewRun.run_id == run_id,
            ArticleReviewStage.stage_key == stage_key,
        )
    )).scalar_one_or_none()


async def update_stage(
    db: AsyncSession,
    run_id: Optional[str],
    stage_key: str,
    *,
    status: Optional[str] = None,
    progress: Optional[int] = None,
    message: Optional[str] = None,
    task_id: Any = _UNSET,
    output: Any = None,
    error: Any = _UNSET,
    increment_attempt: bool = False,
) -> Optional[ArticleReviewStage]:
    if not run_id:
        return None
    stage = await get_stage(db, run_id, stage_key)
    if stage is None:
        return None
    now = utcnow()
    if status is not None:
        stage.status = status
        if status == "running" and stage.started_at is None:
            stage.started_at = now
        if status in {"succeeded", "failed", "blocked", "invalidated"}:
            stage.finished_at = now
    if progress is not None:
        stage.progress = max(0, min(100, int(progress)))
    if message is not None:
        stage.message = message[:500]
    if task_id is not _UNSET:
        stage.task_id = task_id
    if output is not None:
        stage.output = output
    if error is not _UNSET:
        stage.error = (str(error)[:1_000] if error else None)
    if increment_attempt:
        stage.attempt += 1
    return stage


async def update_run(
    db: AsyncSession,
    run_id: Optional[str],
    *,
    status: Optional[str] = None,
    current_stage: Optional[str] = None,
    requested_stage: Optional[str] = None,
    task_id: Any = _UNSET,
    error: Any = _UNSET,
) -> Optional[ArticleReviewRun]:
    if not run_id:
        return None
    run = (await db.execute(
        select(ArticleReviewRun).where(ArticleReviewRun.run_id == run_id)
    )).scalar_one_or_none()
    if run is None:
        return None
    if status is not None:
        run.status = status
        if status == "running" and run.started_at is None:
            run.started_at = utcnow()
        if status in {"succeeded", "failed"}:
            run.finished_at = utcnow()
    if current_stage is not None:
        run.current_stage = current_stage
    if requested_stage is not None:
        run.requested_stage = requested_stage
    if task_id is not _UNSET:
        run.task_id = task_id
    if error is not _UNSET:
        run.error = (str(error)[:1_000] if error else None)
    return run


async def invalidate_downstream(
    db: AsyncSession,
    run_id: str,
    from_stage: str,
) -> None:
    from_order = STAGE_ORDER.get(from_stage, 1)
    stages = (await db.execute(
        select(ArticleReviewStage)
        .join(ArticleReviewRun, ArticleReviewRun.id == ArticleReviewStage.review_run_id)
        .where(
            ArticleReviewRun.run_id == run_id,
            ArticleReviewStage.stage_order >= from_order,
        )
    )).scalars().all()
    for stage in stages:
        stage.status = "invalidated" if stage.stage_order > from_order else "queued"
        stage.progress = 0
        stage.message = (
            f"{STAGE_LABELS.get(from_stage, from_stage)}已变化，需重新计算"
            if stage.stage_order > from_order
            else None
        )
        stage.error = None
        stage.output = None
        stage.finished_at = None


def block_payload(block: ArticleReviewSemanticBlock) -> dict:
    return {
        "id": block.id,
        "stable_id": block.stable_id,
        "review_id": block.review_id,
        "review_run_id": block.review_run_id,
        "side": block.side,
        "ordinal": block.ordinal,
        "text": block.text,
        "normalized_text": block.normalized_text,
        "start_offset": block.start_offset,
        "end_offset": block.end_offset,
        "source_line_start": block.source_line_start,
        "source_line_end": block.source_line_end,
        "raw_block_count": block.raw_block_count,
        "user_edited": bool(block.user_edited),
        "locked": bool(block.locked),
        "metadata": block.block_metadata,
    }


def change_payload(change: ArticleReviewChange) -> dict:
    return {
        "id": change.id,
        "stable_id": change.stable_id,
        "review_id": change.review_id,
        "review_run_id": change.review_run_id,
        "ordinal": change.ordinal,
        "change_type": change.change_type,
        "impact": change.impact,
        "is_major": bool(change.is_major),
        "confidence": change.confidence,
        "change_ratio": change.change_ratio,
        "significance_reason": change.significance_reason,
        "effect": change.effect,
        "before_block_ids": list(change.before_block_ids or []),
        "after_block_ids": list(change.after_block_ids or []),
        "before_text": change.before_text,
        "after_text": change.after_text,
        "position_delta": change.position_delta,
        "human_label": change.human_label,
        "human_note": change.human_note,
        "ai_analysis": change.ai_analysis,
    }


def reorder_payload(event: ArticleReviewReorderEvent) -> dict:
    return {
        "id": event.id,
        "stable_id": event.stable_id,
        "review_id": event.review_id,
        "review_run_id": event.review_run_id,
        "ordinal": event.ordinal,
        "before_block_ids": list(event.before_block_ids or []),
        "after_block_ids": list(event.after_block_ids or []),
        "summary": event.summary,
        "confidence": event.confidence,
        "human_label": event.human_label,
    }


def stage_payload(stage: ArticleReviewStage) -> dict:
    return {
        "id": stage.id,
        "stage_key": stage.stage_key,
        "label": STAGE_LABELS.get(stage.stage_key, stage.stage_key),
        "stage_order": stage.stage_order,
        "status": stage.status,
        "progress": stage.progress,
        "message": stage.message,
        "task_id": stage.task_id,
        "attempt": stage.attempt,
        "error": stage.error,
        "started_at": stage.started_at.isoformat() if stage.started_at else None,
        "finished_at": stage.finished_at.isoformat() if stage.finished_at else None,
        "updated_at": stage.updated_at.isoformat() if stage.updated_at else None,
        "is_stale": is_stage_stale(stage),
        "output": stage.output,
    }


def run_payload(run: ArticleReviewRun) -> dict:
    return {
        "id": run.id,
        "run_id": run.run_id,
        "run_no": run.run_no,
        "status": run.status,
        "current_stage": run.current_stage,
        "requested_stage": run.requested_stage,
        "task_id": run.task_id,
        "error": run.error,
        "started_at": run.started_at.isoformat() if run.started_at else None,
        "finished_at": run.finished_at.isoformat() if run.finished_at else None,
        "stages": [stage_payload(stage) for stage in (run.stages or [])],
    }


async def persist_diff_artifacts(
    db: AsyncSession,
    review: ArticleReview,
    run: ArticleReviewRun,
    diff: dict,
    *,
    persist_blocks: bool = True,
) -> None:
    if persist_blocks:
        await persist_semantic_blocks(db, review, run, diff)
    await db.execute(delete(ArticleReviewChange).where(ArticleReviewChange.review_run_id == run.id))
    await db.execute(delete(ArticleReviewReorderEvent).where(ArticleReviewReorderEvent.review_run_id == run.id))

    for ordinal, change in enumerate(diff.get("alignments", []), start=1):
        db.add(ArticleReviewChange(
            review_id=review.id,
            review_run_id=run.id,
            stable_id=change["stable_id"],
            ordinal=ordinal,
            change_type=change["change_type"],
            impact=change["impact"],
            is_major=bool(change["is_major"]),
            confidence=change.get("confidence", 0.0),
            change_ratio=change.get("change_ratio", 0.0),
            significance_reason=change.get("significance_reason"),
            before_block_ids=change.get("before_block_ids", []),
            after_block_ids=change.get("after_block_ids", []),
            before_text=change.get("before"),
            after_text=change.get("after"),
            position_delta=change.get("position_delta"),
        ))
    for ordinal, event in enumerate(diff.get("reorder_events", []), start=1):
        db.add(ArticleReviewReorderEvent(
            review_id=review.id,
            review_run_id=run.id,
            stable_id=event["id"],
            ordinal=ordinal,
            before_block_ids=event.get("before_block_ids", []),
            after_block_ids=event.get("after_block_ids", []),
            summary=event.get("summary"),
            confidence=event.get("confidence", 0.0),
        ))
    await db.flush()


async def persist_semantic_blocks(
    db: AsyncSession,
    review: ArticleReview,
    run: ArticleReviewRun,
    diff: dict,
) -> None:
    """只保存语义分段，供人工确认前的预览使用。"""

    await db.execute(delete(ArticleReviewSemanticBlock).where(
        ArticleReviewSemanticBlock.review_run_id == run.id,
    ))
    for side in ("before", "after"):
        for block in diff.get("semantic_blocks", {}).get(side, []):
            db.add(ArticleReviewSemanticBlock(
                review_id=review.id,
                review_run_id=run.id,
                stable_id=block["stable_id"],
                side=side,
                ordinal=block["ordinal"],
                text=block["text"],
                normalized_text=block["normalized_text"],
                start_offset=block.get("start_offset", 0),
                end_offset=block.get("end_offset", 0),
                source_line_start=block.get("source_line_start"),
                source_line_end=block.get("source_line_end"),
                raw_block_count=block.get("raw_block_count", 1),
                user_edited=bool(block.get("user_edited")),
                locked=bool(block.get("locked")),
                block_metadata={"source": "deterministic_semantic_split"},
            ))
    await db.flush()


async def persist_methodology_candidates(
    db: AsyncSession,
    review: ArticleReview,
    run: ArticleReviewRun,
    candidates: list[dict],
) -> None:
    await db.execute(delete(ArticleReviewMethodologyCandidate).where(
        ArticleReviewMethodologyCandidate.review_run_id == run.id,
    ))
    for item in candidates[:20]:
        db.add(ArticleReviewMethodologyCandidate(
            review_id=review.id,
            review_run_id=run.id,
            title=(item.get("title") or "未命名方法")[:200],
            rule=(item.get("rule") or "").strip()[:10_000],
            rationale=item.get("rationale"),
            example=item.get("example"),
            evidence_change_ids=item.get("evidence_group_ids") or [],
            status="candidate",
        ))
    await db.flush()


async def load_workflow_entities(
    db: AsyncSession,
    review_id: int,
    run_id: Optional[str] = None,
) -> dict:
    run_query = (
        select(ArticleReviewRun)
        .where(ArticleReviewRun.review_id == review_id)
        .order_by(ArticleReviewRun.run_no.desc(), ArticleReviewRun.id.desc())
        .options(selectinload(ArticleReviewRun.stages))
    )
    if run_id:
        run_query = run_query.where(ArticleReviewRun.run_id == run_id)
    run = (await db.execute(run_query)).scalars().first()
    if run is None:
        return {"run": None, "blocks": [], "changes": [], "reorder_events": [], "methodology_candidates": [], "experience_sources": []}

    blocks = (await db.execute(
        select(ArticleReviewSemanticBlock)
        .where(ArticleReviewSemanticBlock.review_run_id == run.id)
        .order_by(ArticleReviewSemanticBlock.side, ArticleReviewSemanticBlock.ordinal)
    )).scalars().all()
    changes = (await db.execute(
        select(ArticleReviewChange)
        .where(ArticleReviewChange.review_run_id == run.id)
        .order_by(ArticleReviewChange.ordinal)
    )).scalars().all()
    reorder_events = (await db.execute(
        select(ArticleReviewReorderEvent)
        .where(ArticleReviewReorderEvent.review_run_id == run.id)
        .order_by(ArticleReviewReorderEvent.ordinal)
    )).scalars().all()
    candidates = (await db.execute(
        select(ArticleReviewMethodologyCandidate)
        .where(ArticleReviewMethodologyCandidate.review_run_id == run.id)
        .order_by(ArticleReviewMethodologyCandidate.created_at, ArticleReviewMethodologyCandidate.id)
    )).scalars().all()
    sources = (await db.execute(
        select(ArticleReviewExperienceSource)
        .where(ArticleReviewExperienceSource.review_id == review_id)
        .order_by(ArticleReviewExperienceSource.created_at, ArticleReviewExperienceSource.id)
    )).scalars().all()
    return {
        "run": run_payload(run),
        "blocks": [block_payload(block) for block in blocks],
        "changes": [change_payload(change) for change in changes],
        "reorder_events": [reorder_payload(event) for event in reorder_events],
        "methodology_candidates": [
            {
                "id": item.id,
                "review_id": item.review_id,
                "review_run_id": item.review_run_id,
                "title": item.title,
                "rule": item.rule,
                "rationale": item.rationale,
                "example": item.example,
                "evidence_change_ids": list(item.evidence_change_ids or []),
                "status": item.status,
                "confirmed_by": item.confirmed_by,
                "confirmed_at": item.confirmed_at.isoformat() if item.confirmed_at else None,
                "experience_card_id": item.experience_card_id,
            }
            for item in candidates
        ],
        "experience_sources": [
            {
                "id": source.id,
                "experience_card_id": source.experience_card_id,
                "review_id": source.review_id,
                "review_run_id": source.review_run_id,
                "change_id": source.change_id,
                "comment_ids": list(source.comment_ids or []),
                "confirmed_conclusion": source.confirmed_conclusion,
                "confirmed_by": source.confirmed_by,
                "confirmed_at": source.confirmed_at.isoformat() if source.confirmed_at else None,
            }
            for source in sources
        ],
    }
