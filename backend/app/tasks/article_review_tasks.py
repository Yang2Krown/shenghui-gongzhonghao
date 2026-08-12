"""文章复盘的后台解析、差异计算和 AI 分析任务。"""

from __future__ import annotations

import asyncio
import logging
import mimetypes
import uuid
from pathlib import Path
from typing import Optional

from sqlalchemy import delete, select
from sqlalchemy.orm import selectinload

from app.core.celery_app import celery_app
from app.core.config import settings
from app.core.progress import progress_store
from app.core.timezone import utcnow
from app.core.upload_security import UploadSecurityError, validate_document_path
from app.db.session import AsyncSessionLocal, engine
from app.models.article_review import (
    ArticleReview,
    ArticleReviewChange,
    ArticleReviewMethodologyCandidate,
    ArticleReviewReorderEvent,
    ArticleReviewSemanticBlock,
)
from app.services.article_review_service import (
    analyze_article_review,
    build_change_groups,
    normalize_review_text,
)
from app.services.article_review_workflow import (
    load_current_run,
    persist_diff_artifacts,
    persist_methodology_candidates,
    persist_semantic_blocks,
    update_run,
    update_stage,
)
from app.utils.file_extractor import UnsupportedFileType, extract_text_from_path

logger = logging.getLogger(__name__)

MAX_REVIEW_UPLOAD_CHARS = 150_000


async def _push(run_id: Optional[str], event: dict) -> None:
    if run_id:
        await progress_store.push(run_id, event)


def _same_task_stage_finished(run, stage_key: str, task_id: Optional[str]) -> bool:
    """Celery late-ack 重投同一 task 时，不重复执行已经持久化成功的阶段。"""

    if run is None or not task_id:
        return False
    return any(
        stage.stage_key == stage_key
        and stage.task_id == task_id
        and stage.status in {"succeeded", "awaiting_confirmation"}
        for stage in (run.stages or [])
    )


def _safe_review_path(raw_path: str) -> Path:
    """只允许任务读取 uploads/article_reviews 下的暂存文件。"""

    root = Path(settings.UPLOAD_DIR).resolve()
    path = Path(raw_path).resolve()
    if root != path and root not in path.parents:
        raise ValueError("文章复盘暂存文件路径不合法")
    return path


async def _parse_saved_file(path: str, filename: str) -> tuple[str, int, bool]:
    file_path = _safe_review_path(path)
    try:
        safe = await asyncio.to_thread(
            validate_document_path,
            filename=filename,
            path=file_path,
            max_size=settings.ARTICLE_REVIEW_MAX_FILE_SIZE,
        )
    except UploadSecurityError as exc:
        raise ValueError(str(exc)) from exc

    try:
        extracted = await extract_text_from_path(
            filename=filename,
            path=safe.path,
            content_type=mimetypes.guess_type(filename)[0],
        )
    except UnsupportedFileType as exc:
        raise ValueError(str(exc)) from exc
    except Exception as exc:
        logger.warning("文章复盘后台解析失败 filename=%s: %s", filename, exc, exc_info=True)
        raise ValueError("文件解析失败，请上传未加密的文字版 PDF/Word") from exc

    extracted = (extracted or "").strip()
    if not extracted:
        raise ValueError("未能提取文字，请上传文字版 PDF/Word，扫描件或加密文件请先转成可复制文本")
    truncated = len(extracted) > MAX_REVIEW_UPLOAD_CHARS
    if truncated:
        extracted = extracted[:MAX_REVIEW_UPLOAD_CHARS]
    return extracted, len(extracted), truncated


async def _mark_failed(
    db,
    review_id: int,
    message: str,
    *,
    task_id: Optional[str],
    run_id: Optional[str],
    stage_key: str = "ai_review",
) -> dict:
    await db.rollback()
    failed = (await db.execute(
        select(ArticleReview).where(ArticleReview.id == review_id)
    )).scalar_one_or_none()
    if failed is not None and task_id and failed.analysis_task_id not in (None, task_id):
        logger.info(
            "忽略已被新任务替代的失败结果 review_id=%s old_task_id=%s active_task_id=%s",
            review_id,
            task_id,
            failed.analysis_task_id,
        )
        return {
            "status": "skipped",
            "review_id": review_id,
            "task_id": failed.analysis_task_id,
        }
    if failed is not None and failed.analysis_task_id in (None, task_id):
        failed.status = "failed"
        failed.analysis_error = message[:1_000] or "文章复盘任务失败"
        current = failed.ai_analysis if isinstance(failed.ai_analysis, dict) else {}
        failed.ai_analysis = {
            **current,
            "status": "failed",
            "error": failed.analysis_error,
            "task_id": task_id or failed.analysis_task_id,
        }
        await update_stage(
            db,
            run_id,
            stage_key,
            status="failed",
            progress=0,
            message="阶段执行失败",
            error=message,
        )
        await update_run(
            db,
            run_id,
            status="failed",
            current_stage=stage_key,
            error=message,
        )
        await db.commit()
    await _push(run_id, {"event": "error", "data": {"message": message[:1_000]}})
    logger.warning("文章复盘任务失败 review_id=%s: %s", review_id, message, exc_info=True)
    return {
        "status": "failed",
        "review_id": review_id,
        "task_id": task_id,
        "error": message[:1_000],
    }


async def _run_article_review_prepare(
    review_id: int,
    run_id: Optional[str],
    task_id: Optional[str],
) -> dict:
    """后台完成文件解析和文本 diff，再投递 AI 分析任务。"""

    async with AsyncSessionLocal() as db:
        review = (await db.execute(
            select(ArticleReview).where(ArticleReview.id == review_id)
        )).scalar_one_or_none()
        if review is None:
            await _push(run_id, {"event": "error", "data": {"message": "复盘记录不存在"}})
            return {"status": "failed", "error": "复盘记录不存在", "review_id": review_id}

        actual_run_id = run_id or review.progress_run_id
        if review.analysis_task_id not in (None, task_id):
            return {
                "status": "skipped",
                "review_id": review_id,
                "task_id": review.analysis_task_id,
            }
        run = await load_current_run(db, review_id, with_stages=True)
        if _same_task_stage_finished(run, "parse", task_id):
            return {"status": "already_completed", "review_id": review_id, "task_id": task_id}
        await update_run(
            db,
            actual_run_id,
            status="running",
            current_stage="parse",
            requested_stage="parse",
            task_id=task_id,
        )
        await update_stage(
            db,
            actual_run_id,
            "parse",
            status="running",
            progress=5,
            message="正在解析改前稿和改后稿",
            task_id=task_id,
        )
        await db.commit()

        try:
            await _push(actual_run_id, {
                "event": "step_start",
                "data": {"step": 1, "stage": "parse", "agent": "document-parser", "action": "正在解析改前稿…"},
            })
            before_text, before_count, before_truncated = await _parse_saved_file(
                review.before_file_path or "",
                review.before_filename,
            )
            await _push(actual_run_id, {
                "event": "step_done",
                "data": {"step": 1, "agent": "document-parser", "action": "改前稿解析完成"},
            })

            await _push(actual_run_id, {
                "event": "step_start",
                "data": {"step": 2, "stage": "parse", "agent": "document-parser", "action": "正在解析改后稿…"},
            })
            after_text, after_count, after_truncated = await _parse_saved_file(
                review.after_file_path or "",
                review.after_filename,
            )
            await _push(actual_run_id, {
                "event": "step_done",
                "data": {"step": 2, "agent": "document-parser", "action": "改后稿解析完成"},
            })

            await _push(actual_run_id, {
                "event": "step_start",
                "data": {"step": 3, "stage": "semantic_segmentation", "agent": "diff-engine", "action": "正在识别语义块和重点修改…"},
            })
            diff = await asyncio.to_thread(build_change_groups, before_text, after_text)
            await _push(actual_run_id, {
                "event": "step_done",
                "data": {"step": 3, "agent": "diff-engine", "action": "重点改动识别完成"},
            })

            review.before_text = before_text
            review.after_text = after_text
            review.before_char_count = before_count
            review.after_char_count = after_count
            review.before_truncated = before_truncated
            review.after_truncated = after_truncated
            review.change_groups = []
            review.status = "processing"
            review.analysis_error = None
            review.ai_analysis = {
                "status": "waiting_semantic_confirmation",
                "summary": None,
                "key_changes": [],
                "methodology_candidates": [],
                "open_questions": [],
            }
            if run is not None:
                await persist_semantic_blocks(db, review, run, diff)
                await db.execute(delete(ArticleReviewChange).where(
                    ArticleReviewChange.review_run_id == run.id,
                ))
                await db.execute(delete(ArticleReviewReorderEvent).where(
                    ArticleReviewReorderEvent.review_run_id == run.id,
                ))
                await db.execute(delete(ArticleReviewMethodologyCandidate).where(
                    ArticleReviewMethodologyCandidate.review_run_id == run.id,
                ))
                await update_stage(
                    db,
                    actual_run_id,
                    "parse",
                    status="succeeded",
                    progress=100,
                    message="两份文章解析完成",
                    output={
                        "before_char_count": before_count,
                        "after_char_count": after_count,
                        "before_truncated": before_truncated,
                        "after_truncated": after_truncated,
                    },
                )
                await update_stage(
                    db,
                    actual_run_id,
                    "semantic_segmentation",
                    status="awaiting_confirmation",
                    progress=100,
                    message="语义分段已生成，等待人工确认",
                    output={
                        "before_block_count": diff["before_block_count"],
                        "after_block_count": diff["after_block_count"],
                    },
                )
                await update_stage(
                    db,
                    actual_run_id,
                    "semantic_alignment",
                    status="blocked",
                    progress=0,
                    message="等待人工确认语义块",
                )
                await update_stage(
                    db,
                    actual_run_id,
                    "ai_review",
                    status="blocked",
                    progress=0,
                    message="等待语义对齐完成",
                )
                await update_stage(
                    db,
                    actual_run_id,
                    "methodology",
                    status="blocked",
                    progress=0,
                    message="等待 AI 复盘分析",
                )
                await update_run(
                    db,
                    actual_run_id,
                    status="waiting",
                    current_stage="semantic_segmentation",
                    requested_stage="semantic_segmentation",
                    task_id=None,
                    error=None,
                )
            review.analysis_task_id = None
            await db.commit()

            # 文本和 diff 已经持久化，原始文件不再需要；失败时保留，便于管理员排查。
            for raw_path in (review.before_file_path, review.after_file_path):
                if raw_path:
                    try:
                        await asyncio.to_thread(_safe_review_path(raw_path).unlink, True)
                    except FileNotFoundError:
                        pass
                    except Exception:
                        logger.warning("清理文章复盘暂存文件失败 path=%s", raw_path, exc_info=True)
            review.before_file_path = None
            review.after_file_path = None
            await db.commit()
            await _push(actual_run_id, {
                "event": "partial_result",
                "data": {
                    "stage": "semantic_segmentation",
                    "status": "awaiting_confirmation",
                    "before_block_count": diff["before_block_count"],
                    "after_block_count": diff["after_block_count"],
                },
            })
            await _push(actual_run_id, {
                "event": "stage_waiting",
                "data": {
                    "stage": "semantic_segmentation",
                    "message": "语义分段已生成，请确认或编辑后继续",
                    "review_id": review_id,
                },
            })
            return {
                "status": "waiting_confirmation",
                "review_id": review_id,
                "task_id": None,
                "run_id": actual_run_id,
                "stage": "semantic_segmentation",
            }
        except Exception as exc:
            failure_task_id = review.analysis_task_id or task_id
            return await _mark_failed(
                db,
                review_id,
                str(exc)[:1_000] or "文章复盘任务失败",
                task_id=failure_task_id,
                run_id=actual_run_id,
                stage_key="parse",
            )


async def _run_article_review_semantic_segmentation(
    review_id: int,
    run_id: Optional[str],
    task_id: Optional[str],
) -> dict:
    """只重跑语义分段，成功后停在人工确认，不越过下游阶段。"""

    async with AsyncSessionLocal() as db:
        review = (await db.execute(
            select(ArticleReview).where(ArticleReview.id == review_id)
        )).scalar_one_or_none()
        if review is None:
            return {"status": "failed", "error": "复盘记录不存在", "review_id": review_id}
        actual_run_id = run_id or review.progress_run_id
        if review.analysis_task_id not in (None, task_id):
            return {
                "status": "skipped",
                "review_id": review_id,
                "task_id": review.analysis_task_id,
            }
        run = await load_current_run(db, review_id, with_stages=True)
        if _same_task_stage_finished(run, "semantic_segmentation", task_id):
            return {"status": "already_completed", "review_id": review_id, "task_id": task_id}
        await update_run(
            db,
            actual_run_id,
            status="running",
            current_stage="semantic_segmentation",
            requested_stage="semantic_segmentation",
            task_id=task_id,
        )
        await update_stage(
            db,
            actual_run_id,
            "semantic_segmentation",
            status="running",
            progress=10,
            message="正在重新生成语义分段",
            task_id=task_id,
        )
        await db.commit()
        try:
            if not review.before_text or not review.after_text:
                raise ValueError("改前稿或改后稿文本为空，无法重新生成语义分段")
            review.before_text = normalize_review_text(review.before_text)
            review.after_text = normalize_review_text(review.after_text)
            review.before_char_count = len(review.before_text)
            review.after_char_count = len(review.after_text)
            diff = await asyncio.to_thread(
                build_change_groups,
                review.before_text,
                review.after_text,
            )
            review.change_groups = []
            review.status = "processing"
            review.analysis_task_id = None
            review.analysis_error = None
            review.ai_analysis = {
                "status": "waiting_semantic_confirmation",
                "summary": None,
                "key_changes": [],
                "methodology_candidates": [],
                "open_questions": [],
            }
            if run is not None:
                await persist_semantic_blocks(db, review, run, diff)
                await db.execute(delete(ArticleReviewChange).where(
                    ArticleReviewChange.review_run_id == run.id,
                ))
                await db.execute(delete(ArticleReviewReorderEvent).where(
                    ArticleReviewReorderEvent.review_run_id == run.id,
                ))
                await db.execute(delete(ArticleReviewMethodologyCandidate).where(
                    ArticleReviewMethodologyCandidate.review_run_id == run.id,
                ))
                await update_stage(
                    db,
                    actual_run_id,
                    "semantic_segmentation",
                    status="awaiting_confirmation",
                    progress=100,
                    message="语义分段已重新生成，等待人工确认",
                    output={
                        "before_block_count": diff["before_block_count"],
                        "after_block_count": diff["after_block_count"],
                    },
                )
                for downstream_key, message in (
                    ("semantic_alignment", "等待人工确认语义块"),
                    ("ai_review", "等待语义对齐完成"),
                    ("methodology", "等待 AI 复盘分析"),
                ):
                    await update_stage(
                        db,
                        actual_run_id,
                        downstream_key,
                        status="blocked",
                        progress=0,
                        message=message,
                    )
                await update_run(
                    db,
                    actual_run_id,
                    status="waiting",
                    current_stage="semantic_segmentation",
                    requested_stage="semantic_segmentation",
                    task_id=None,
                    error=None,
                )
            await db.commit()
            await _push(actual_run_id, {
                "event": "partial_result",
                "data": {
                    "stage": "semantic_segmentation",
                    "status": "awaiting_confirmation",
                    "before_block_count": diff["before_block_count"],
                    "after_block_count": diff["after_block_count"],
                },
            })
            await _push(actual_run_id, {
                "event": "stage_waiting",
                "data": {
                    "stage": "semantic_segmentation",
                    "message": "语义分段已重新生成，请确认或编辑后继续",
                    "review_id": review_id,
                },
            })
            return {
                "status": "waiting_confirmation",
                "review_id": review_id,
                "task_id": None,
                "run_id": actual_run_id,
                "stage": "semantic_segmentation",
            }
        except Exception as exc:
            return await _mark_failed(
                db,
                review_id,
                str(exc)[:1_000] or "语义分段失败",
                task_id=task_id,
                run_id=actual_run_id,
                stage_key="semantic_segmentation",
            )


async def _run_article_review_alignment(
    review_id: int,
    run_id: Optional[str],
    task_id: Optional[str],
) -> dict:
    """基于已确认语义块重新计算对齐，成功后只投递 AI 阶段。"""

    async with AsyncSessionLocal() as db:
        review = (await db.execute(
            select(ArticleReview).where(ArticleReview.id == review_id)
        )).scalar_one_or_none()
        if review is None:
            return {"status": "failed", "error": "复盘记录不存在", "review_id": review_id}
        actual_run_id = run_id or review.progress_run_id
        if review.analysis_task_id not in (None, task_id):
            return {
                "status": "skipped",
                "review_id": review_id,
                "task_id": review.analysis_task_id,
            }
        run = await load_current_run(db, review_id, with_stages=True)
        if _same_task_stage_finished(run, "semantic_alignment", task_id):
            return {"status": "already_completed", "review_id": review_id, "task_id": task_id}
        await update_run(
            db,
            actual_run_id,
            status="running",
            current_stage="semantic_alignment",
            requested_stage="semantic_alignment",
            task_id=task_id,
        )
        await update_stage(
            db,
            actual_run_id,
            "semantic_alignment",
            status="running",
            progress=10,
            message="正在根据确认后的语义块重新对齐",
            task_id=task_id,
        )
        await db.commit()
        try:
            rows = []
            if run is not None:
                rows = (await db.execute(
                    select(ArticleReviewSemanticBlock)
                    .where(ArticleReviewSemanticBlock.review_run_id == run.id)
                    .order_by(ArticleReviewSemanticBlock.side, ArticleReviewSemanticBlock.ordinal)
                )).scalars().all()
            semantic_blocks = {
                "before": [
                    {
                        "stable_id": row.stable_id,
                        "id": row.stable_id,
                        "side": row.side,
                        "ordinal": row.ordinal,
                        "text": row.text,
                        "normalized_text": row.normalized_text,
                        "start_offset": row.start_offset,
                        "end_offset": row.end_offset,
                        "source_line_start": row.source_line_start,
                        "source_line_end": row.source_line_end,
                        "raw_block_count": row.raw_block_count,
                        "user_edited": row.user_edited,
                        "locked": row.locked,
                    }
                    for row in rows if row.side == "before"
                ],
                "after": [
                    {
                        "stable_id": row.stable_id,
                        "id": row.stable_id,
                        "side": row.side,
                        "ordinal": row.ordinal,
                        "text": row.text,
                        "normalized_text": row.normalized_text,
                        "start_offset": row.start_offset,
                        "end_offset": row.end_offset,
                        "source_line_start": row.source_line_start,
                        "source_line_end": row.source_line_end,
                        "raw_block_count": row.raw_block_count,
                        "user_edited": row.user_edited,
                        "locked": row.locked,
                    }
                    for row in rows if row.side == "after"
                ],
            }
            if not semantic_blocks["before"] or not semantic_blocks["after"]:
                diff = await asyncio.to_thread(
                    build_change_groups,
                    review.before_text,
                    review.after_text,
                )
            else:
                diff = await asyncio.to_thread(
                    build_change_groups,
                    review.before_text,
                    review.after_text,
                    semantic_blocks=semantic_blocks,
                )
            review.change_groups = diff["groups"]
            review.ai_analysis = {
                "status": "queued",
                "summary": None,
                "key_changes": [],
                "methodology_candidates": [],
                "open_questions": [],
            }
            review.status = "analyzing"
            review.analysis_error = None
            if run is not None:
                await persist_diff_artifacts(
                    db,
                    review,
                    run,
                    diff,
                    persist_blocks=not (
                        bool(semantic_blocks["before"]) and bool(semantic_blocks["after"])
                    ),
                )
                await update_stage(
                    db,
                    actual_run_id,
                    "semantic_segmentation",
                    status="succeeded",
                    progress=100,
                    message="语义块已确认",
                )
                await update_stage(
                    db,
                    actual_run_id,
                    "semantic_alignment",
                    status="succeeded",
                    progress=100,
                    message="语义对齐和重点修改识别完成",
                    output={
                        "total_groups": diff["total_groups"],
                        "major_group_count": diff["major_group_count"],
                        "reorder_count": len(diff.get("reorder_events") or []),
                    },
                )
                await update_stage(
                    db,
                    actual_run_id,
                    "ai_review",
                    status="queued",
                    progress=0,
                    message="等待 AI 复盘分析",
                )
            ai_task_id = str(uuid.uuid4())
            review.analysis_task_id = ai_task_id
            await update_run(
                db,
                actual_run_id,
                status="queued",
                current_stage="ai_review",
                requested_stage="ai_review",
                task_id=ai_task_id,
            )
            await update_stage(
                db,
                actual_run_id,
                "ai_review",
                status="queued",
                progress=0,
                message="AI 复盘任务已排队",
                task_id=ai_task_id,
                increment_attempt=True,
            )
            await db.commit()
            await _push(actual_run_id, {
                "event": "step_done",
                "data": {"step": 3, "stage": "semantic_alignment", "agent": "diff-engine", "action": "语义对齐完成"},
            })
            await _push(actual_run_id, {
                "event": "partial_result",
                "data": {
                    "stage": "semantic_alignment",
                    "status": "succeeded",
                    "total_groups": diff["total_groups"],
                    "major_group_count": diff["major_group_count"],
                    "reorder_count": len(diff.get("reorder_events") or []),
                },
            })
            await _push(actual_run_id, {
                "event": "step_start",
                "data": {"step": 4, "stage": "ai_review", "agent": "article-review-ai", "action": "正在分析修改原因、效果和方法论…"},
            })
            analyze_article_review_task.apply_async(
                args=[review.id, actual_run_id],
                task_id=ai_task_id,
            )
            return {
                "status": "queued",
                "review_id": review_id,
                "task_id": ai_task_id,
                "run_id": actual_run_id,
            }
        except Exception as exc:
            return await _mark_failed(
                db,
                review_id,
                str(exc)[:1_000] or "语义对齐失败",
                task_id=task_id,
                run_id=actual_run_id,
                stage_key="semantic_alignment",
            )


async def _run_article_review_analysis(
    review_id: int,
    run_id: Optional[str] = None,
    task_id: Optional[str] = None,
) -> dict:
    async with AsyncSessionLocal() as db:
        review = (await db.execute(
            select(ArticleReview)
            .where(ArticleReview.id == review_id)
            .options(selectinload(ArticleReview.comments))
        )).scalar_one_or_none()
        if review is None:
            return {"status": "failed", "error": "复盘记录不存在", "review_id": review_id}

        actual_run_id = run_id or review.progress_run_id
        if review.analysis_task_id not in (None, task_id):
            return {
                "status": "skipped",
                "review_id": review_id,
                "task_id": review.analysis_task_id,
            }
        run = await load_current_run(db, review_id, with_stages=True)
        if _same_task_stage_finished(run, "ai_review", task_id):
            return {"status": "already_completed", "review_id": review_id, "task_id": task_id}
        await update_run(
            db,
            actual_run_id,
            status="running",
            current_stage="ai_review",
            requested_stage="ai_review",
            task_id=task_id,
        )
        await update_stage(
            db,
            actual_run_id,
            "ai_review",
            status="running",
            progress=10,
            message="正在分析重要修改的原因和效果",
            task_id=task_id,
        )
        await db.commit()

        comments = [
            {
                "change_group_id": comment.change_group_id,
                "change_id": comment.change_id,
                "semantic_block_id": comment.semantic_block_id,
                "body": comment.body,
            }
            for comment in (review.comments or [])
        ]
        try:
            analysis = await analyze_article_review(
                title=review.title,
                change_groups=list(review.change_groups or []),
                comments=comments,
            )
            # 用户可能已从“失联”阶段发起了新任务。旧 LLM 调用即使随后返回，
            # 也不能覆盖新任务的状态和结果。
            await db.refresh(review, attribute_names=["analysis_task_id"])
            if task_id and review.analysis_task_id != task_id:
                return {
                    "status": "skipped",
                    "review_id": review_id,
                    "task_id": review.analysis_task_id,
                }
            review.ai_analysis = {
                **analysis,
                "status": "succeeded",
                "analyzed_at": utcnow().isoformat(),
                "task_id": task_id or review.analysis_task_id,
            }
            review.status = "reviewing"
            review.analysis_error = None
            if run is not None:
                await persist_methodology_candidates(
                    db,
                    review,
                    run,
                    analysis.get("methodology_candidates") or [],
                )
                await update_stage(
                    db,
                    actual_run_id,
                    "ai_review",
                    status="succeeded",
                    progress=100,
                    message="AI 复盘分析完成",
                    output={
                        "summary": analysis.get("summary"),
                        "key_change_count": len(analysis.get("key_changes") or []),
                    },
                )
                await update_stage(
                    db,
                    actual_run_id,
                    "methodology",
                    status="succeeded",
                    progress=100,
                    message="方法论候选已生成，等待人工确认",
                    output={
                        "candidate_count": len(analysis.get("methodology_candidates") or []),
                    },
                )
                await update_run(
                    db,
                    actual_run_id,
                    status="succeeded",
                    current_stage="methodology",
                    requested_stage="methodology",
                    error=None,
                )
            await db.commit()
            await _push(actual_run_id, {
                "event": "step_done",
                "data": {"step": 4, "stage": "ai_review", "agent": "article-review-ai", "action": "AI 复盘完成"},
            })
            await _push(actual_run_id, {
                "event": "partial_result",
                "data": {
                    "stage": "ai_review",
                    "status": "succeeded",
                    "summary": analysis.get("summary"),
                    "key_change_count": len(analysis.get("key_changes") or []),
                    "methodology_candidate_count": len(analysis.get("methodology_candidates") or []),
                },
            })
            await _push(actual_run_id, {
                "event": "result",
                "data": {"status": "reviewing", "review_id": review_id},
            })
            return {
                "status": "succeeded",
                "review_id": review_id,
                "task_id": task_id or review.analysis_task_id,
                "summary": analysis.get("summary"),
            }
        except Exception as exc:
            return await _mark_failed(
                db,
                review_id,
                str(exc)[:1_000] or "AI 差异分析失败",
                task_id=task_id,
                run_id=actual_run_id,
                stage_key="ai_review",
            )


async def _run_with_engine_cleanup(awaitable):
    """Celery 每次用 asyncio.run 创建事件循环，任务结束必须释放旧连接池。"""

    try:
        return await awaitable
    finally:
        await engine.dispose()


@celery_app.task(
    bind=True,
    name="reviews.prepare_diff",
    max_retries=0,
    acks_late=True,
    reject_on_worker_lost=True,
)
def prepare_article_review_task(self, review_id: int, run_id: Optional[str] = None) -> dict:
    task_id = getattr(getattr(self, "request", None), "id", None)
    return asyncio.run(_run_with_engine_cleanup(_run_article_review_prepare(review_id, run_id, task_id)))


@celery_app.task(
    bind=True,
    name="reviews.segment_semantic_blocks",
    max_retries=0,
    acks_late=True,
    reject_on_worker_lost=True,
)
def segment_article_review_task(self, review_id: int, run_id: Optional[str] = None) -> dict:
    task_id = getattr(getattr(self, "request", None), "id", None)
    return asyncio.run(_run_with_engine_cleanup(
        _run_article_review_semantic_segmentation(review_id, run_id, task_id)
    ))


@celery_app.task(
    bind=True,
    name="reviews.analyze_diff",
    max_retries=0,
    acks_late=True,
    reject_on_worker_lost=True,
)
def analyze_article_review_task(self, review_id: int, run_id: Optional[str] = None) -> dict:
    task_id = getattr(getattr(self, "request", None), "id", None)
    return asyncio.run(_run_with_engine_cleanup(_run_article_review_analysis(review_id, run_id, task_id)))


@celery_app.task(
    bind=True,
    name="reviews.align_semantic_blocks",
    max_retries=0,
    acks_late=True,
    reject_on_worker_lost=True,
)
def align_article_review_task(self, review_id: int, run_id: Optional[str] = None) -> dict:
    task_id = getattr(getattr(self, "request", None), "id", None)
    return asyncio.run(_run_with_engine_cleanup(_run_article_review_alignment(review_id, run_id, task_id)))
