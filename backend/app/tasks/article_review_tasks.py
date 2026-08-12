"""文章复盘的后台解析、差异计算和 AI 分析任务。"""

from __future__ import annotations

import asyncio
import logging
import mimetypes
import uuid
from pathlib import Path
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.celery_app import celery_app
from app.core.config import settings
from app.core.progress import progress_store
from app.core.timezone import utcnow
from app.core.upload_security import UploadSecurityError, validate_document_upload
from app.db.session import AsyncSessionLocal
from app.models.article_review import ArticleReview
from app.services.article_review_service import analyze_article_review, build_change_groups
from app.utils.file_extractor import UnsupportedFileType, extract_text

logger = logging.getLogger(__name__)

MAX_REVIEW_UPLOAD_CHARS = 150_000


async def _push(run_id: Optional[str], event: dict) -> None:
    if run_id:
        await progress_store.push(run_id, event)


def _safe_review_path(raw_path: str) -> Path:
    """只允许任务读取 uploads/article_reviews 下的暂存文件。"""

    root = Path(settings.UPLOAD_DIR).resolve()
    path = Path(raw_path).resolve()
    if root != path and root not in path.parents:
        raise ValueError("文章复盘暂存文件路径不合法")
    return path


async def _parse_saved_file(path: str, filename: str) -> tuple[str, int, bool]:
    file_path = _safe_review_path(path)
    data = await asyncio.to_thread(file_path.read_bytes)
    try:
        safe = validate_document_upload(
            filename=filename,
            data=data,
            max_size=20 * 1024 * 1024,
        )
    except UploadSecurityError as exc:
        raise ValueError(str(exc)) from exc

    try:
        extracted = await extract_text(
            filename=filename,
            data=safe.data,
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
) -> dict:
    await db.rollback()
    failed = (await db.execute(
        select(ArticleReview).where(ArticleReview.id == review_id)
    )).scalar_one_or_none()
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

        try:
            await _push(actual_run_id, {
                "event": "step_start",
                "data": {"step": 1, "agent": "document-parser", "action": "正在解析改前稿…"},
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
                "data": {"step": 2, "agent": "document-parser", "action": "正在解析改后稿…"},
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
                "data": {"step": 3, "agent": "diff-engine", "action": "正在识别段落变化和重点修改…"},
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
            review.change_groups = diff["groups"]
            review.status = "analyzing"
            review.analysis_error = None
            review.ai_analysis = {
                "status": "queued",
                "summary": None,
                "key_changes": [],
                "methodology_candidates": [],
                "open_questions": [],
            }
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

            ai_task_id = str(uuid.uuid4())
            review.analysis_task_id = ai_task_id
            await db.commit()
            await _push(actual_run_id, {
                "event": "step_start",
                "data": {"step": 4, "agent": "article-review-ai", "action": "正在分析修改原因、效果和方法论…"},
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
            failure_task_id = review.analysis_task_id or task_id
            return await _mark_failed(
                db,
                review_id,
                str(exc)[:1_000] or "文章复盘任务失败",
                task_id=failure_task_id,
                run_id=actual_run_id,
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

        comments = [
            {
                "change_group_id": comment.change_group_id,
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
            review.ai_analysis = {
                **analysis,
                "status": "succeeded",
                "analyzed_at": utcnow().isoformat(),
                "task_id": task_id or review.analysis_task_id,
            }
            review.status = "reviewing"
            review.analysis_error = None
            await db.commit()
            await _push(actual_run_id, {
                "event": "step_done",
                "data": {"step": 4, "agent": "article-review-ai", "action": "AI 复盘完成"},
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
            )


@celery_app.task(bind=True, name="reviews.prepare_diff", max_retries=0)
def prepare_article_review_task(self, review_id: int, run_id: Optional[str] = None) -> dict:
    task_id = getattr(getattr(self, "request", None), "id", None)
    return asyncio.run(_run_article_review_prepare(review_id, run_id, task_id))


@celery_app.task(bind=True, name="reviews.analyze_diff", max_retries=0)
def analyze_article_review_task(self, review_id: int, run_id: Optional[str] = None) -> dict:
    task_id = getattr(getattr(self, "request", None), "id", None)
    return asyncio.run(_run_article_review_analysis(review_id, run_id, task_id))
