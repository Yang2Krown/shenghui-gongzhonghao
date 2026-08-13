"""团队协作文章复盘工作台 API。"""

from __future__ import annotations

import asyncio
import json
import logging
import shutil
import uuid
from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile, status
from fastapi.responses import StreamingResponse
from sqlalchemy import case, delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import load_only, selectinload

from app.core.config import settings
from app.core.progress import progress_store
from app.core.product_access import is_admin_user
from app.core.rate_limit import enforce_rate_limit, rule_from_setting, user_actor
from app.core.security import get_current_user
from app.core.timezone import utcnow
from app.core.upload_security import (
    DOCUMENT_EXTS,
    UploadSecurityError,
    validate_document_path,
    validate_document_upload,
)
from app.db.session import AsyncSessionLocal, get_db
from app.models.article_review import (
    ArticleReview,
    ArticleReviewChange,
    ArticleReviewComment,
    ArticleReviewExperienceSource,
    ArticleReviewMethodologyCandidate,
    ArticleReviewReorderEvent,
    ArticleReviewRun,
    ArticleReviewSemanticBlock,
    ArticleReviewStage,
)
from app.models.content_version import ExperienceCard
from app.models.user import User
from app.schemas.article_review import (
    ArticleReviewAnalysisUpdate,
    ArticleReviewChangeReviewUpdate,
    ArticleReviewCommentCreate,
    ArticleReviewCommentUpdate,
    ArticleReviewMethodologyConfirm,
    ArticleReviewPromote,
    ArticleReviewSemanticBlocksUpdate,
    ArticleReviewTitleUpdate,
)
from app.services.article_review_service import (
    ArticleReviewAnalysisError,
    build_review_experience_content,
    normalize_semantic_text,
    normalize_article_review_analysis,
)
from app.services.experience_service import build_card_payload, create_experience_card, enqueue_embedding
from app.services.team_service import can_access_team_collaboration
from app.tasks.article_review_tasks import (
    align_article_review_task,
    analyze_article_review_task,
    prepare_article_review_task,
    segment_article_review_task,
)
from app.services.article_review_workflow import (
    STAGE_ORDER,
    block_payload,
    change_payload,
    create_run_with_stages,
    invalidate_downstream,
    is_stage_stale,
    load_current_run,
    load_workflow_entities,
    persist_methodology_candidates,
    reorder_payload,
    run_payload,
    update_run,
    update_stage,
)

logger = logging.getLogger(__name__)
router = APIRouter()

MAX_REVIEW_UPLOAD_SIZE = settings.ARTICLE_REVIEW_MAX_FILE_SIZE
MAX_REVIEW_FILES_SIZE = settings.ARTICLE_REVIEW_MAX_FILES_SIZE


async def _require_review_access(db: AsyncSession, user: User) -> None:
    if not await can_access_team_collaboration(db, user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="仅在职员工和管理员可访问文章复盘",
        )


def _iso(value: Any) -> Optional[str]:
    return value.isoformat() if value else None


def _user_payload(user: Optional[User]) -> Optional[dict]:
    if user is None:
        return None
    return {
        "id": user.id,
        "username": user.username,
        "full_name": user.full_name,
        "avatar_url": user.avatar_url,
    }


def _comment_payload(comment: ArticleReviewComment) -> dict:
    return {
        "id": comment.id,
        "review_id": comment.review_id,
        "change_group_id": comment.change_group_id,
        "change_id": comment.change_id,
        "semantic_block_id": comment.semantic_block_id,
        "body": comment.body,
        "resolved": bool(comment.resolved),
        "edit_status": comment.edit_status,
        "processing_status": comment.processing_status,
        "edited_at": _iso(comment.edited_at),
        "author_id": comment.author_id,
        "author": _user_payload(comment.author),
        "created_at": _iso(comment.created_at),
        "updated_at": _iso(comment.updated_at),
    }


def _review_payload(
    review: ArticleReview,
    *,
    include_groups: bool = True,
    include_comments: bool = True,
) -> dict:
    groups = list(review.change_groups or [])
    major = [group for group in groups if group.get("is_major")]
    analysis = review.ai_analysis if isinstance(review.ai_analysis, dict) else None
    comments = (
        [_comment_payload(comment) for comment in (review.comments or [])]
        if include_comments
        else []
    )
    return {
        "id": review.id,
        "title": review.title,
        "status": review.status,
        "analysis_task_id": review.analysis_task_id,
        "progress": {
            "run_id": review.progress_run_id,
            "status": review.status,
        },
        "analysis_error": review.analysis_error,
        "created_by": review.created_by,
        "created_by_user": _user_payload(review.creator),
        "created_at": _iso(review.created_at),
        "updated_at": _iso(review.updated_at),
        "before": {
            "filename": review.before_filename,
            "char_count": review.before_char_count,
            "truncated": bool(review.before_truncated),
        },
        "after": {
            "filename": review.after_filename,
            "char_count": review.after_char_count,
            "truncated": bool(review.after_truncated),
        },
        "stats": {
            "total_groups": len(groups),
            "major_group_count": len(major),
            "added_blocks": sum(group.get("after_block_count", 0) for group in groups),
            "removed_blocks": sum(group.get("before_block_count", 0) for group in groups),
        },
        "change_groups": groups if include_groups else [],
        "major_changes": major if include_groups else [
            {
                "id": group.get("id"),
                "impact": group.get("impact"),
                "is_major": group.get("is_major"),
            }
            for group in major
        ],
        "before_text": review.before_text if include_groups else None,
        "after_text": review.after_text if include_groups else None,
        "ai_analysis": analysis,
        "comments": comments,
        "promoted_card_ids": list(review.promoted_card_ids or []),
    }


def _review_metadata_payload(
    review: ArticleReview,
    *,
    stats: Optional[dict] = None,
    include_analysis: bool = True,
) -> dict:
    """不访问全文、旧 change_groups 或 comments 关系的轻量投影。"""

    analysis = review.ai_analysis if include_analysis and isinstance(review.ai_analysis, dict) else None
    return {
        "id": review.id,
        "title": review.title,
        "status": review.status,
        "analysis_task_id": review.analysis_task_id,
        "progress": {"run_id": review.progress_run_id, "status": review.status},
        "analysis_error": review.analysis_error,
        "created_by": review.created_by,
        "created_by_user": _user_payload(review.creator),
        "created_at": _iso(review.created_at),
        "updated_at": _iso(review.updated_at),
        "before": {
            "filename": review.before_filename,
            "char_count": review.before_char_count,
            "truncated": bool(review.before_truncated),
        },
        "after": {
            "filename": review.after_filename,
            "char_count": review.after_char_count,
            "truncated": bool(review.after_truncated),
        },
        "stats": {
            "total_groups": 0,
            "major_group_count": 0,
            "added_blocks": 0,
            "removed_blocks": 0,
            **(stats or {}),
        },
        "change_groups": [],
        "major_changes": [],
        "before_text": None,
        "after_text": None,
        "ai_analysis": analysis,
        "comments": [],
        "promoted_card_ids": list(review.promoted_card_ids or []) if include_analysis else [],
    }


def _change_group_payload(change: ArticleReviewChange) -> dict:
    """把规范化 change 表映射为旧界面仍使用的 change_group 结构。"""

    return {
        "id": change.stable_id,
        "stable_id": change.stable_id,
        "change_id": change.id,
        "kind": {"addition": "insert", "deletion": "delete"}.get(change.change_type, "replace"),
        "change_type": change.change_type,
        "impact": change.impact,
        "is_major": bool(change.is_major),
        "confidence": change.confidence,
        "change_ratio": change.change_ratio,
        "significance_reason": change.significance_reason,
        "effect": change.effect,
        "before_block_ids": list(change.before_block_ids or []),
        "after_block_ids": list(change.after_block_ids or []),
        "before_block_count": len(change.before_block_ids or []),
        "after_block_count": len(change.after_block_ids or []),
        "before_char_count": len(change.before_text or ""),
        "after_char_count": len(change.after_text or ""),
        "before": change.before_text or "",
        "after": change.after_text or "",
        "position_delta": change.position_delta,
        "human_label": change.human_label,
        "human_note": change.human_note,
        "ai_analysis": change.ai_analysis,
    }


def _methodology_payload(item: ArticleReviewMethodologyCandidate) -> dict:
    return {
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
        "confirmed_at": _iso(item.confirmed_at),
        "experience_card_id": item.experience_card_id,
    }


async def _load_review_metadata(
    db: AsyncSession,
    review_id: int,
    *,
    include_analysis: bool = True,
) -> Optional[ArticleReview]:
    columns = [
        ArticleReview.id,
        ArticleReview.title,
        ArticleReview.status,
        ArticleReview.analysis_task_id,
        ArticleReview.progress_run_id,
        ArticleReview.analysis_error,
        ArticleReview.created_by,
        ArticleReview.created_at,
        ArticleReview.updated_at,
        ArticleReview.before_filename,
        ArticleReview.before_char_count,
        ArticleReview.before_truncated,
        ArticleReview.after_filename,
        ArticleReview.after_char_count,
        ArticleReview.after_truncated,
    ]
    if include_analysis:
        columns.extend([ArticleReview.ai_analysis, ArticleReview.promoted_card_ids])
    return (await db.execute(
        select(ArticleReview)
        .where(ArticleReview.id == review_id)
        .options(load_only(*columns), selectinload(ArticleReview.creator))
    )).scalar_one_or_none()


async def _review_stats_by_id(db: AsyncSession, review_ids: list[int]) -> dict[int, dict]:
    """一次查询每篇复盘最新 run 的改动计数，避免列表加载大 JSON/全文。"""

    if not review_ids:
        return {}
    run_rows = (await db.execute(
        select(ArticleReviewRun.review_id, ArticleReviewRun.id)
        .where(ArticleReviewRun.review_id.in_(review_ids))
        .order_by(ArticleReviewRun.review_id, ArticleReviewRun.run_no.desc(), ArticleReviewRun.id.desc())
    )).all()
    latest_run_by_review: dict[int, int] = {}
    for review_id, run_id in run_rows:
        latest_run_by_review.setdefault(review_id, run_id)
    if not latest_run_by_review:
        return {}
    rows = (await db.execute(
        select(
            ArticleReviewChange.review_id,
            func.sum(case((ArticleReviewChange.change_type != "unchanged", 1), else_=0)),
            func.sum(case((ArticleReviewChange.is_major.is_(True), 1), else_=0)),
            func.sum(case((ArticleReviewChange.change_type == "addition", 1), else_=0)),
            func.sum(case((ArticleReviewChange.change_type == "deletion", 1), else_=0)),
        )
        .where(ArticleReviewChange.review_run_id.in_(list(latest_run_by_review.values())))
        .group_by(ArticleReviewChange.review_id)
    )).all()
    return {
        review_id: {
            "total_groups": int(total or 0),
            "major_group_count": int(major or 0),
            "added_blocks": int(added or 0),
            "removed_blocks": int(removed or 0),
        }
        for review_id, total, major, added, removed in rows
    }


async def _load_review(db: AsyncSession, review_id: int) -> Optional[ArticleReview]:
    return (await db.execute(
        select(ArticleReview)
        .where(ArticleReview.id == review_id)
        .options(
            selectinload(ArticleReview.creator),
            selectinload(ArticleReview.comments).selectinload(ArticleReviewComment.author),
        )
    )).scalar_one_or_none()


async def _cleanup_review_uploads(review: ArticleReview) -> None:
    """删除复盘仍在解析中的暂存文件，只允许触及 uploads/article_reviews。"""

    root = (Path(settings.UPLOAD_DIR).resolve() / "article_reviews").resolve()
    pending_dirs: set[Path] = set()
    for raw_path in (review.before_file_path, review.after_file_path):
        if not raw_path:
            continue
        try:
            path = Path(raw_path).resolve()
        except OSError:
            logger.warning("文章复盘暂存文件路径无法解析 review_id=%s path=%s", review.id, raw_path)
            continue
        if root not in path.parents:
            logger.warning("跳过删除越界的文章复盘文件 review_id=%s path=%s", review.id, raw_path)
            continue
        if path.parent.parent == root and path.parent.name.startswith("pending-"):
            pending_dirs.add(path.parent)
        try:
            if path.is_file():
                await asyncio.to_thread(path.unlink)
        except FileNotFoundError:
            pass
        except OSError:
            logger.warning("文章复盘暂存文件删除失败 review_id=%s path=%s", review.id, raw_path, exc_info=True)
    for directory in pending_dirs:
        try:
            await asyncio.to_thread(shutil.rmtree, directory, True)
        except OSError:
            logger.warning("文章复盘暂存目录删除失败 review_id=%s path=%s", review.id, directory, exc_info=True)


async def _read_review_upload(file: UploadFile) -> tuple[str, bytes, str]:
    if not file.filename:
        raise HTTPException(status_code=400, detail="上传文件名不能为空")
    data = await file.read()
    if len(data) > MAX_REVIEW_UPLOAD_SIZE:
        actual_mb = len(data) / 1024 / 1024
        limit_mb = MAX_REVIEW_UPLOAD_SIZE / 1024 / 1024
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail={
                "code": "review_single_file_too_large",
                "scope": "single_file",
                "message": (
                    f"单个文件超限：{file.filename} 实际 {actual_mb:.2f}MB，"
                    f"限制 {limit_mb:.0f}MB"
                ),
                "filename": file.filename,
                "actual_bytes": len(data),
                "limit_bytes": MAX_REVIEW_UPLOAD_SIZE,
            },
        )
    try:
        safe = validate_document_upload(
            filename=file.filename,
            data=data,
            max_size=MAX_REVIEW_UPLOAD_SIZE,
        )
    except UploadSecurityError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return file.filename, safe.data, safe.ext


async def _review_upload_size(file: UploadFile) -> int:
    """读取 SpooledTemporaryFile 的真实大小，不把内容复制到 Python bytes。"""

    def measure() -> int:
        position = file.file.tell()
        file.file.seek(0, 2)
        size = file.file.tell()
        file.file.seek(position)
        return size

    return await asyncio.to_thread(measure)


def _single_file_too_large(filename: str, actual_bytes: int) -> HTTPException:
    actual_mb = actual_bytes / 1024 / 1024
    limit_mb = MAX_REVIEW_UPLOAD_SIZE / 1024 / 1024
    return HTTPException(
        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
        detail={
            "code": "review_single_file_too_large",
            "scope": "single_file",
            "message": f"单个文件超限：{filename} 实际 {actual_mb:.2f}MB，限制 {limit_mb:.0f}MB",
            "filename": filename,
            "actual_bytes": actual_bytes,
            "limit_bytes": MAX_REVIEW_UPLOAD_SIZE,
        },
    )


async def _copy_review_upload(file: UploadFile, target: Path) -> None:
    """分块复制 FastAPI 已落盘/缓冲的上传内容，避免二次构造大 bytes。"""

    def copy() -> None:
        file.file.seek(0)
        with target.open("wb") as destination:
            shutil.copyfileobj(file.file, destination, length=1024 * 1024)
        file.file.seek(0)

    await asyncio.to_thread(copy)


async def _stage_review_uploads(
    before_file: UploadFile,
    after_file: UploadFile,
) -> tuple[str, str, str, str]:
    """只做快速校验并把原始文件放入 web/worker 共用的暂存 volume。"""

    if not before_file.filename or not after_file.filename:
        raise HTTPException(status_code=400, detail="上传文件名不能为空")
    before_ext = Path(before_file.filename).suffix.lower()
    after_ext = Path(after_file.filename).suffix.lower()
    if before_ext not in DOCUMENT_EXTS or after_ext not in DOCUMENT_EXTS:
        raise HTTPException(status_code=400, detail="仅支持 PDF、Word（DOCX）、TXT 和 MD 文件")

    before_size, after_size = await asyncio.gather(
        _review_upload_size(before_file),
        _review_upload_size(after_file),
    )
    if before_size > MAX_REVIEW_UPLOAD_SIZE:
        raise _single_file_too_large(before_file.filename, before_size)
    if after_size > MAX_REVIEW_UPLOAD_SIZE:
        raise _single_file_too_large(after_file.filename, after_size)
    files_size = before_size + after_size
    if files_size > MAX_REVIEW_FILES_SIZE:
        actual_mb = files_size / 1024 / 1024
        limit_mb = MAX_REVIEW_FILES_SIZE / 1024 / 1024
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail={
                "code": "review_files_too_large",
                "scope": "files_total",
                "message": (
                    f"本次请求文件总大小超限：实际 {actual_mb:.2f}MB，"
                    f"限制 {limit_mb:.0f}MB（改前和改后文件合计）"
                ),
                "actual_bytes": files_size,
                "limit_bytes": MAX_REVIEW_FILES_SIZE,
            },
        )
    stage_dir = Path(settings.UPLOAD_DIR).resolve() / "article_reviews" / f"pending-{uuid.uuid4().hex}"
    before_path = stage_dir / f"before{before_ext}"
    after_path = stage_dir / f"after{after_ext}"
    try:
        await asyncio.to_thread(stage_dir.mkdir, parents=True, exist_ok=False)
        await asyncio.gather(
            _copy_review_upload(before_file, before_path),
            _copy_review_upload(after_file, after_path),
        )
        await asyncio.gather(
            asyncio.to_thread(
                validate_document_path,
                filename=before_file.filename,
                path=before_path,
                max_size=MAX_REVIEW_UPLOAD_SIZE,
            ),
            asyncio.to_thread(
                validate_document_path,
                filename=after_file.filename,
                path=after_path,
                max_size=MAX_REVIEW_UPLOAD_SIZE,
            ),
        )
    except UploadSecurityError as exc:
        await asyncio.to_thread(shutil.rmtree, stage_dir, True)
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception:
        await asyncio.to_thread(shutil.rmtree, stage_dir, True)
        raise
    return before_file.filename, str(before_path), after_file.filename, str(after_path)


async def _enqueue_analysis(db: AsyncSession, review: ArticleReview) -> dict:
    """提交 AI 任务；提交失败不丢弃已经算出的文本 diff。"""

    task_id = str(uuid.uuid4())
    if not review.progress_run_id:
        review.progress_run_id = progress_store.create_run(user_id=review.created_by)
    review.analysis_task_id = task_id
    await update_run(
        db,
        review.progress_run_id,
        status="queued",
        current_stage="ai_review",
        requested_stage="ai_review",
        task_id=task_id,
    )
    await update_stage(
        db,
        review.progress_run_id,
        "ai_review",
        status="queued",
        progress=0,
        message="AI 复盘任务已排队",
        task_id=task_id,
        increment_attempt=True,
    )
    await db.commit()
    try:
        analyze_article_review_task.apply_async(
            args=[review.id, review.progress_run_id],
            task_id=task_id,
        )
        return {
            "status": "queued",
            "task_id": task_id,
            "run_id": review.progress_run_id,
        }
    except Exception as exc:
        await db.rollback()
        failed = await _load_review(db, review.id)
        if failed is not None:
            failed.status = "failed"
            failed.analysis_error = str(exc)[:1_000] or "AI 任务提交失败"
            current = failed.ai_analysis if isinstance(failed.ai_analysis, dict) else {}
            failed.ai_analysis = {
                **current,
                "status": "failed",
                "error": failed.analysis_error,
            }
            await db.commit()
        logger.warning("文章复盘 AI 任务提交失败 review_id=%s: %s", review.id, exc, exc_info=True)
        return {
            "status": "failed",
            "task_id": None,
            "run_id": review.progress_run_id,
            "error": str(exc)[:1_000],
        }


async def _enqueue_prepare(db: AsyncSession, review: ArticleReview) -> dict:
    task_id = str(uuid.uuid4())
    review.analysis_task_id = task_id
    review.status = "processing"
    review.analysis_error = None
    current = dict(review.ai_analysis or {}) if isinstance(review.ai_analysis, dict) else {}
    review.ai_analysis = {**current, "status": "processing", "error": None}
    await update_run(
        db,
        review.progress_run_id,
        status="queued",
        current_stage="parse",
        requested_stage="parse",
        task_id=task_id,
    )
    await update_stage(
        db,
        review.progress_run_id,
        "parse",
        status="queued",
        progress=0,
        message="文件解析任务已排队",
        task_id=task_id,
        increment_attempt=True,
    )
    await db.commit()
    try:
        prepare_article_review_task.apply_async(
            args=[review.id, review.progress_run_id],
            task_id=task_id,
        )
        return {
            "status": "queued",
            "task_id": task_id,
            "run_id": review.progress_run_id,
        }
    except Exception as exc:
        await db.rollback()
        failed = await _load_review(db, review.id)
        if failed is not None:
            failed.status = "failed"
            failed.analysis_error = str(exc)[:1_000] or "文件解析任务提交失败"
            failed.ai_analysis = {
                **(failed.ai_analysis if isinstance(failed.ai_analysis, dict) else {}),
                "status": "failed",
                "error": failed.analysis_error,
            }
            await db.commit()
        await progress_store.push(
            review.progress_run_id,
            {"event": "error", "data": {"message": str(exc)[:1_000]}},
        )
        return {
            "status": "failed",
            "task_id": None,
            "run_id": review.progress_run_id,
            "error": str(exc)[:1_000],
        }


@router.post("", response_model=dict, status_code=status.HTTP_202_ACCEPTED)
async def create_article_review(
    request: Request,
    before_file: UploadFile = File(...),
    after_file: UploadFile = File(...),
    title: Optional[str] = Form(None, max_length=200),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    """快速接收两份文件，解析、diff 和 AI 分析全部交给后台任务。"""

    await _require_review_access(db, current_user)
    await enforce_rate_limit(
        [rule_from_setting(
            "file:upload:user",
            settings.RATE_LIMIT_FILE_UPLOAD_USER,
            user_actor(current_user.id),
        )],
        request=request,
    )
    before_filename, before_path, after_filename, after_path = await _stage_review_uploads(
        before_file,
        after_file,
    )
    clean_title = (title or "").strip() or Path(after_filename).stem or "未命名文章复盘"
    run_id = progress_store.create_run(user_id=current_user.id)

    review = ArticleReview(
        title=clean_title[:200],
        before_filename=before_filename,
        after_filename=after_filename,
        before_file_path=before_path,
        after_file_path=after_path,
        before_text="",
        after_text="",
        before_char_count=0,
        after_char_count=0,
        before_truncated=False,
        after_truncated=False,
        change_groups=[],
        ai_analysis={
            "status": "processing",
            "summary": None,
            "key_changes": [],
            "methodology_candidates": [],
            "open_questions": [],
        },
        status="processing",
        progress_run_id=run_id,
        created_by=current_user.id,
    )
    db.add(review)
    await db.flush()
    await create_run_with_stages(
        db,
        review,
        run_id=run_id,
        created_by=current_user.id,
    )
    await db.commit()
    await db.refresh(review)
    task = await _enqueue_prepare(db, review)
    loaded = await _load_review(db, review.id)
    return {
        "code": 202,
        "message": "文章复盘已创建，文件解析和 AI 分析已进入后台",
        "data": {
            "review": _review_payload(loaded or review),
            "task": task,
        },
    }


@router.get("/{review_id}/stream")
async def stream_article_review_progress(
    review_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    request: Request = None,
) -> StreamingResponse:
    """以 SSE 推送文件解析、diff 和 AI 分析进度。"""

    await _require_review_access(db, current_user)
    review = await _load_review(db, review_id)
    if review is None:
        raise HTTPException(status_code=404, detail="文章复盘不存在")
    run_id = review.progress_run_id
    try:
        last_event_id = int((request.headers.get("Last-Event-ID") if request else None) or 0)
    except (TypeError, ValueError):
        last_event_id = 0

    async def event_stream():
        if not run_id:
            yield "event: progress\ndata: {\"exists\":false}\n\n"
            return
        last_payload = None
        last_sent_event_id = last_event_id
        for index in range(1_800):
            snapshot = await progress_store.snapshot_async(run_id, user_id=current_user.id)
            if snapshot is not None:
                payload = {"review_id": review_id, "progress": snapshot}
                serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True)
                try:
                    event_id = int(snapshot.get("last_event_id") or 0)
                except (TypeError, ValueError):
                    event_id = 0
                if (
                    serialized != last_payload
                    and (event_id > last_sent_event_id or last_payload is None)
                ):
                    frame_id = event_id or last_sent_event_id + 1
                    yield f"id: {frame_id}\nevent: progress\ndata: {serialized}\n\n"
                    last_payload = serialized
                    last_sent_event_id = frame_id
                if snapshot.get("done"):
                    return
            # Redis 降级到内存时，API 和 Celery 进程看不到同一份事件；此时用数据库终态
            # 收口 SSE，避免前端因进度存储故障一直等待。
            if snapshot is None or index % 5 == 0:
                row = (await db.execute(
                    select(ArticleReview.status, ArticleReview.analysis_error)
                    .where(ArticleReview.id == review_id)
                )).one_or_none()
                if row and row[0] not in {"processing", "analyzing"}:
                    fallback = {
                        "exists": True,
                        "done": True,
                        "steps": snapshot.get("steps", []) if snapshot else [],
                        "current_step": snapshot.get("current_step", 0) if snapshot else 0,
                        "done_steps": snapshot.get("done_steps", []) if snapshot else [],
                        "result": {"status": row[0], "review_id": review_id},
                        "error": row[1],
                        "step": snapshot.get("step", 0) if snapshot else 0,
                        "agent": snapshot.get("agent") if snapshot else None,
                        "action": "文章复盘完成" if row[0] == "reviewing" else "文章复盘失败",
                        "avatar": snapshot.get("avatar") if snapshot else None,
                    }
                    serialized = json.dumps({"review_id": review_id, "progress": fallback}, ensure_ascii=False, sort_keys=True)
                    last_sent_event_id += 1
                    yield f"id: {last_sent_event_id}\nevent: progress\ndata: {serialized}\n\n"
                    return
            # AI 请求可能持续数分钟；定期发注释帧，避免中间 Nginx 把空闲 SSE 连接当成超时。
            if index % 15 == 0:
                yield ": keep-alive\n\n"
            await asyncio.sleep(1)
        yield "event: error\ndata: {\"message\":\"复盘进度流已超时，请刷新详情查看最新状态\"}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("", response_model=dict)
async def list_article_reviews(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    keyword: Optional[str] = Query(None, max_length=100),
    review_status: Optional[str] = Query(None, alias="status", max_length=20),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    await _require_review_access(db, current_user)
    filters = []
    if review_status:
        if review_status not in {"processing", "analyzing", "reviewing", "failed"}:
            raise HTTPException(status_code=400, detail="复盘状态不合法")
        filters.append(ArticleReview.status == review_status)
    if keyword and keyword.strip():
        value = f"%{keyword.strip()}%"
        filters.append(or_(
            ArticleReview.title.ilike(value),
            ArticleReview.before_filename.ilike(value),
            ArticleReview.after_filename.ilike(value),
        ))
    total = (await db.execute(
        select(func.count(ArticleReview.id)).where(*filters)
    )).scalar_one()
    rows = (await db.execute(
        select(ArticleReview)
        .where(*filters)
        .options(
            load_only(
                ArticleReview.id,
                ArticleReview.title,
                ArticleReview.status,
                ArticleReview.analysis_task_id,
                ArticleReview.progress_run_id,
                ArticleReview.analysis_error,
                ArticleReview.created_by,
                ArticleReview.created_at,
                ArticleReview.updated_at,
                ArticleReview.before_filename,
                ArticleReview.before_char_count,
                ArticleReview.before_truncated,
                ArticleReview.after_filename,
                ArticleReview.after_char_count,
                ArticleReview.after_truncated,
            ),
            selectinload(ArticleReview.creator),
        )
        .order_by(ArticleReview.created_at.desc(), ArticleReview.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )).scalars().all()
    stats_by_id = await _review_stats_by_id(db, [row.id for row in rows])
    return {
        "code": 200,
        "message": "文章复盘列表获取成功",
        "data": {
            "items": [
                _review_metadata_payload(
                    row,
                    stats=stats_by_id.get(row.id),
                    include_analysis=False,
                )
                for row in rows
            ],
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": (total + page_size - 1) // page_size,
        },
    }


@router.delete("/{review_id}", response_model=dict)
async def delete_article_review(
    review_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    """删除复盘及其运行产物；已沉淀经验的复盘保留以维护来源追溯。"""

    await _require_review_access(db, current_user)
    review = await _load_review(db, review_id)
    if review is None:
        raise HTTPException(status_code=404, detail="文章复盘不存在")
    if review.created_by != current_user.id and not is_admin_user(current_user):
        raise HTTPException(status_code=403, detail="只有复盘创建者或管理员可以删除记录")

    source_count = (await db.execute(
        select(func.count(ArticleReviewExperienceSource.id)).where(
            ArticleReviewExperienceSource.review_id == review.id,
        )
    )).scalar_one()
    if source_count or review.promoted_card_ids:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "review_has_experience_sources",
                "message": "该复盘已经沉淀到经验库，为保留来源追溯不能删除",
            },
        )

    run_ids = list((await db.execute(
        select(ArticleReviewRun.id).where(ArticleReviewRun.review_id == review.id)
    )).scalars())
    # 先删带有具体 change/block/run 外键的记录，再删运行和复盘本体；
    # 不依赖异步 ORM 懒加载，也让 SQLite 测试和 PostgreSQL 级联行为一致。
    await db.execute(delete(ArticleReviewComment).where(ArticleReviewComment.review_id == review.id))
    await db.execute(delete(ArticleReviewMethodologyCandidate).where(ArticleReviewMethodologyCandidate.review_id == review.id))
    await db.execute(delete(ArticleReviewExperienceSource).where(ArticleReviewExperienceSource.review_id == review.id))
    await db.execute(delete(ArticleReviewChange).where(ArticleReviewChange.review_id == review.id))
    await db.execute(delete(ArticleReviewReorderEvent).where(ArticleReviewReorderEvent.review_id == review.id))
    await db.execute(delete(ArticleReviewSemanticBlock).where(ArticleReviewSemanticBlock.review_id == review.id))
    if run_ids:
        await db.execute(delete(ArticleReviewStage).where(ArticleReviewStage.review_run_id.in_(run_ids)))
        await db.execute(delete(ArticleReviewRun).where(ArticleReviewRun.id.in_(run_ids)))
    await db.execute(delete(ArticleReview).where(ArticleReview.id == review.id))
    await db.commit()

    if review.progress_run_id:
        progress_store.cleanup(review.progress_run_id)
    await _cleanup_review_uploads(review)
    return {
        "code": 200,
        "message": "文章复盘已删除",
        "data": {"review_id": review_id},
    }


@router.put("/{review_id}/title", response_model=dict)
async def update_article_review_title(
    review_id: int,
    title_in: ArticleReviewTitleUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    """更新复盘标题；团队协作成员均可修改，且不会影响已完成的分析产物。"""

    await _require_review_access(db, current_user)
    review = await _load_review_metadata(db, review_id, include_analysis=False)
    if review is None:
        raise HTTPException(status_code=404, detail="文章复盘不存在")

    review.title = title_in.title
    await db.commit()
    await db.refresh(review)
    return {
        "code": 200,
        "message": "文章复盘标题已更新",
        "data": {"review": _review_metadata_payload(review, include_analysis=False)},
    }


@router.get("/{review_id}/summary", response_model=dict)
async def get_article_review_summary(
    review_id: int,
    preview_size: int = Query(12, ge=1, le=30),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    """返回切换记录所需的轻量摘要，不读取全文、全部分段或全部评论。"""

    await _require_review_access(db, current_user)
    review = await _load_review_metadata(db, review_id)
    if review is None:
        raise HTTPException(status_code=404, detail="文章复盘不存在")
    run = await load_current_run(db, review_id, with_stages=True)
    changes: list[ArticleReviewChange] = []
    reorder_events: list[ArticleReviewReorderEvent] = []
    candidates: list[ArticleReviewMethodologyCandidate] = []
    stats = {
        "total_groups": 0,
        "major_group_count": 0,
        "added_blocks": 0,
        "removed_blocks": 0,
        "before_block_count": 0,
        "after_block_count": 0,
    }
    if run is not None:
        count_row = (await db.execute(
            select(
                func.sum(case((ArticleReviewChange.change_type != "unchanged", 1), else_=0)),
                func.sum(case((ArticleReviewChange.is_major.is_(True), 1), else_=0)),
                func.sum(case((ArticleReviewChange.change_type == "addition", 1), else_=0)),
                func.sum(case((ArticleReviewChange.change_type == "deletion", 1), else_=0)),
            ).where(ArticleReviewChange.review_run_id == run.id)
        )).one()
        stats.update({
            "total_groups": int(count_row[0] or 0),
            "major_group_count": int(count_row[1] or 0),
            "added_blocks": int(count_row[2] or 0),
            "removed_blocks": int(count_row[3] or 0),
        })
        for side, count in (await db.execute(
            select(ArticleReviewSemanticBlock.side, func.count(ArticleReviewSemanticBlock.id))
            .where(ArticleReviewSemanticBlock.review_run_id == run.id)
            .group_by(ArticleReviewSemanticBlock.side)
        )).all():
            stats[f"{side}_block_count"] = int(count or 0)
        changes = list((await db.execute(
            select(ArticleReviewChange)
            .where(
                ArticleReviewChange.review_run_id == run.id,
                ArticleReviewChange.change_type != "unchanged",
            )
            .order_by(
                ArticleReviewChange.is_major.desc(),
                case(
                    (ArticleReviewChange.impact == "high", 0),
                    (ArticleReviewChange.impact == "medium", 1),
                    else_=2,
                ),
                ArticleReviewChange.ordinal,
            )
            .limit(preview_size)
        )).scalars())
        reorder_events = list((await db.execute(
            select(ArticleReviewReorderEvent)
            .where(ArticleReviewReorderEvent.review_run_id == run.id)
            .order_by(ArticleReviewReorderEvent.ordinal)
            .limit(50)
        )).scalars())
        candidates = list((await db.execute(
            select(ArticleReviewMethodologyCandidate)
            .where(ArticleReviewMethodologyCandidate.review_run_id == run.id)
            .order_by(ArticleReviewMethodologyCandidate.created_at, ArticleReviewMethodologyCandidate.id)
            .limit(20)
        )).scalars())

    comments_count = (await db.execute(
        select(func.count(ArticleReviewComment.id)).where(
            ArticleReviewComment.review_id == review_id,
        )
    )).scalar_one()
    review_payload = _review_metadata_payload(review, stats=stats)
    review_payload["change_groups"] = [_change_group_payload(item) for item in changes]
    review_payload["major_changes"] = [
        item for item in review_payload["change_groups"] if item["is_major"]
    ]
    review_payload["comments_count"] = int(comments_count or 0)
    return {
        "code": 200,
        "message": "文章复盘摘要获取成功",
        "data": {
            "review": review_payload,
            "run": run_payload(run) if run is not None else None,
            "blocks": [],
            "changes": [change_payload(item) for item in changes],
            "reorder_events": [reorder_payload(item) for item in reorder_events],
            "methodology_candidates": [_methodology_payload(item) for item in candidates],
            "experience_sources": [],
            "change_pagination": {
                "page": 1,
                "page_size": preview_size,
                "total": stats["total_groups"],
                "has_more": len(changes) < stats["total_groups"],
            },
        },
    }


@router.get("/{review_id}/semantic-blocks", response_model=dict)
async def get_article_review_semantic_blocks(
    review_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    await _require_review_access(db, current_user)
    review = await _load_review_metadata(db, review_id, include_analysis=False)
    if review is None:
        raise HTTPException(status_code=404, detail="文章复盘不存在")
    run = await load_current_run(db, review_id, with_stages=False)
    if run is None:
        blocks = []
    else:
        blocks = list((await db.execute(
            select(ArticleReviewSemanticBlock)
            .where(ArticleReviewSemanticBlock.review_run_id == run.id)
            .order_by(ArticleReviewSemanticBlock.side, ArticleReviewSemanticBlock.ordinal)
        )).scalars())
    return {
        "code": 200,
        "message": "语义分段获取成功",
        "data": {"blocks": [block_payload(item) for item in blocks]},
    }


@router.get("/{review_id}/changes", response_model=dict)
async def list_article_review_changes(
    review_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(12, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    await _require_review_access(db, current_user)
    review = await _load_review_metadata(db, review_id, include_analysis=False)
    if review is None:
        raise HTTPException(status_code=404, detail="文章复盘不存在")
    run = await load_current_run(db, review_id, with_stages=False)
    total = 0
    changes: list[ArticleReviewChange] = []
    if run is not None:
        filters = (
            ArticleReviewChange.review_run_id == run.id,
            ArticleReviewChange.change_type != "unchanged",
        )
        total = (await db.execute(
            select(func.count(ArticleReviewChange.id)).where(*filters)
        )).scalar_one()
        changes = list((await db.execute(
            select(ArticleReviewChange)
            .where(*filters)
            .order_by(
                ArticleReviewChange.is_major.desc(),
                case(
                    (ArticleReviewChange.impact == "high", 0),
                    (ArticleReviewChange.impact == "medium", 1),
                    else_=2,
                ),
                ArticleReviewChange.ordinal,
            )
            .offset((page - 1) * page_size)
            .limit(page_size)
        )).scalars())
    return {
        "code": 200,
        "message": "复盘改动获取成功",
        "data": {
            "change_groups": [_change_group_payload(item) for item in changes],
            "changes": [change_payload(item) for item in changes],
            "page": page,
            "page_size": page_size,
            "total": int(total or 0),
            "has_more": page * page_size < int(total or 0),
        },
    }


@router.get("/{review_id}/comments", response_model=dict)
async def list_article_review_comments(
    review_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    await _require_review_access(db, current_user)
    review = await _load_review_metadata(db, review_id, include_analysis=False)
    if review is None:
        raise HTTPException(status_code=404, detail="文章复盘不存在")
    comments = list((await db.execute(
        select(ArticleReviewComment)
        .where(ArticleReviewComment.review_id == review_id)
        .options(selectinload(ArticleReviewComment.author))
        .order_by(ArticleReviewComment.created_at, ArticleReviewComment.id)
    )).scalars())
    return {
        "code": 200,
        "message": "复盘评论获取成功",
        "data": {"comments": [_comment_payload(item) for item in comments]},
    }


@router.get("/{review_id}/source-text", response_model=dict)
async def get_article_review_source_text(
    review_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    await _require_review_access(db, current_user)
    row = (await db.execute(
        select(
            ArticleReview.before_text,
            ArticleReview.after_text,
            ArticleReview.before_char_count,
            ArticleReview.after_char_count,
        ).where(ArticleReview.id == review_id)
    )).one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="文章复盘不存在")
    return {
        "code": 200,
        "message": "复盘原文获取成功",
        "data": {
            "before_text": row[0],
            "after_text": row[1],
            "before_char_count": row[2],
            "after_char_count": row[3],
        },
    }


@router.get("/{review_id}/workflow", response_model=dict)
async def get_article_review_workflow(
    review_id: int,
    run_id: Optional[str] = Query(None, max_length=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    """返回可恢复工作流的阶段、语义块、对齐、顺序事件和候选方法论。"""

    await _require_review_access(db, current_user)
    review = await _load_review(db, review_id)
    if review is None:
        raise HTTPException(status_code=404, detail="文章复盘不存在")
    workflow = await load_workflow_entities(db, review_id, run_id)
    return {
        "code": 200,
        "message": "文章复盘工作流获取成功",
        "data": {
            "review": _review_payload(review),
            **workflow,
        },
    }


@router.get("/{review_id}", response_model=dict)
async def get_article_review(
    review_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    await _require_review_access(db, current_user)
    review = await _load_review(db, review_id)
    if review is None:
        raise HTTPException(status_code=404, detail="文章复盘不存在")
    workflow = await load_workflow_entities(db, review_id)
    payload = _review_payload(review)
    payload["workflow"] = workflow
    return {
        "code": 200,
        "message": "文章复盘详情获取成功",
        "data": payload,
    }


@router.post("/{review_id}/comments", response_model=dict)
async def add_article_review_comment(
    review_id: int,
    comment_in: ArticleReviewCommentCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    await _require_review_access(db, current_user)
    review = await _load_review(db, review_id)
    if review is None:
        raise HTTPException(status_code=404, detail="文章复盘不存在")
    if comment_in.change_group_id and comment_in.change_group_id not in {
        group.get("id") for group in (review.change_groups or [])
    }:
        raise HTTPException(status_code=400, detail="评论对应的改动块不存在")
    change = None
    if comment_in.change_id:
        change = (await db.execute(
            select(ArticleReviewChange).where(
                ArticleReviewChange.id == comment_in.change_id,
                ArticleReviewChange.review_id == review.id,
            )
        )).scalar_one_or_none()
        if change is None:
            raise HTTPException(status_code=400, detail="评论对应的语义变化不存在")
    semantic_block = None
    if comment_in.semantic_block_id:
        semantic_block = (await db.execute(
            select(ArticleReviewSemanticBlock).where(
                ArticleReviewSemanticBlock.id == comment_in.semantic_block_id,
                ArticleReviewSemanticBlock.review_id == review.id,
            )
        )).scalar_one_or_none()
        if semantic_block is None:
            raise HTTPException(status_code=400, detail="评论对应的语义块不存在")
    if not comment_in.change_group_id and not change and not semantic_block:
        # 允许整篇复盘评论，但具体评论优先要求挂到一个可追溯对象。
        comment_in.change_group_id = None
    comment = ArticleReviewComment(
        review_id=review.id,
        change_group_id=comment_in.change_group_id,
        change_id=change.id if change else None,
        semantic_block_id=semantic_block.id if semantic_block else None,
        body=comment_in.body,
        author_id=current_user.id,
    )
    db.add(comment)
    await db.commit()
    loaded = (await db.execute(
        select(ArticleReviewComment)
        .where(ArticleReviewComment.id == comment.id)
        .options(selectinload(ArticleReviewComment.author))
    )).scalar_one()
    return {
        "code": 200,
        "message": "复盘评论已保存",
        "data": {"comment": _comment_payload(loaded)},
    }


@router.put("/{review_id}/comments/{comment_id}", response_model=dict)
async def update_article_review_comment(
    review_id: int,
    comment_id: int,
    comment_in: ArticleReviewCommentUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    """编辑评论或更新团队处理状态，不能改变评论挂载的复盘对象。"""

    await _require_review_access(db, current_user)
    comment = (await db.execute(
        select(ArticleReviewComment)
        .where(
            ArticleReviewComment.id == comment_id,
            ArticleReviewComment.review_id == review_id,
        )
        .options(selectinload(ArticleReviewComment.author))
    )).scalar_one_or_none()
    if comment is None:
        raise HTTPException(status_code=404, detail="复盘评论不存在")
    is_admin = is_admin_user(current_user)
    if comment.author_id != current_user.id and not is_admin:
        raise HTTPException(status_code=403, detail="只有评论作者或管理员可以编辑评论")
    updates = comment_in.model_dump(exclude_unset=True)
    if "body" in updates:
        comment.body = updates["body"]
        comment.edit_status = "edited"
        comment.edited_at = utcnow()
    if "edit_status" in updates:
        comment.edit_status = updates["edit_status"]
        comment.edited_at = utcnow()
    if "resolved" in updates:
        comment.resolved = updates["resolved"]
    if "processing_status" in updates:
        comment.processing_status = updates["processing_status"]
    await db.commit()
    await db.refresh(comment)
    return {
        "code": 200,
        "message": "复盘评论状态已更新",
        "data": {"comment": _comment_payload(comment)},
    }


@router.put("/{review_id}/analysis", response_model=dict)
async def update_article_review_analysis(
    review_id: int,
    analysis_in: ArticleReviewAnalysisUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    """人工修订/确认 AI 分析，保证经验库沉淀的是团队认可的版本。"""

    await _require_review_access(db, current_user)
    review = await _load_review(db, review_id)
    if review is None:
        raise HTTPException(status_code=404, detail="文章复盘不存在")
    current = dict(review.ai_analysis or {}) if isinstance(review.ai_analysis, dict) else {}
    updates = analysis_in.model_dump(exclude_unset=True)
    current.update(updates)
    try:
        normalized = normalize_article_review_analysis(
            current,
            parse_status="manual",
            allow_empty=True,
        )
    except ArticleReviewAnalysisError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    normalized.update({
        "status": "succeeded",
        "manually_edited": True,
        "edited_by": current_user.id,
    })
    review.ai_analysis = normalized
    review.status = "reviewing"
    review.analysis_error = None
    run = await load_current_run(db, review_id, with_stages=False)
    if run is not None and "methodology_candidates" in updates:
        # 方法论正文被人工改过后，旧的确认状态不再可信，重新回到候选态。
        await persist_methodology_candidates(
            db,
            review,
            run,
            normalized.get("methodology_candidates") or [],
        )
        await update_stage(
            db,
            run.run_id,
            "methodology",
            status="succeeded",
            progress=100,
            message="人工修订已保存，等待重新确认方法论",
            output={"candidate_count": len(normalized.get("methodology_candidates") or [])},
        )
        await update_run(
            db,
            run.run_id,
            status="succeeded",
            current_stage="methodology",
            requested_stage="methodology",
            error=None,
        )
    await db.commit()
    loaded = await _load_review(db, review.id)
    workflow = await load_workflow_entities(db, review.id)
    return {
        "code": 200,
        "message": "文章复盘分析已保存人工修订",
        "data": {"review": _review_payload(loaded or review), **workflow},
    }


@router.put("/{review_id}/semantic-blocks", response_model=dict)
async def update_article_review_semantic_blocks(
    review_id: int,
    blocks_in: ArticleReviewSemanticBlocksUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    """保存人工合并/拆分/编辑后的语义块，并使下游结果明确失效。"""

    await _require_review_access(db, current_user)
    review = await _load_review(db, review_id)
    if review is None:
        raise HTTPException(status_code=404, detail="文章复盘不存在")
    run = await load_current_run(db, review_id, with_stages=False)
    if run is None:
        if not review.progress_run_id:
            review.progress_run_id = progress_store.create_run(user_id=current_user.id)
        run = await create_run_with_stages(
            db,
            review,
            run_id=review.progress_run_id,
            created_by=current_user.id,
        )
    sides = {item.side for item in blocks_in.blocks}
    if sides != {"before", "after"}:
        raise HTTPException(status_code=400, detail="语义块必须同时包含改前和改后两侧")
    seen = set()
    seen_stable_ids = set()
    for item in blocks_in.blocks:
        key = (item.side, item.ordinal)
        if key in seen:
            raise HTTPException(status_code=400, detail="同一侧语义块序号不能重复")
        seen.add(key)
        if item.stable_id and item.stable_id in seen_stable_ids:
            raise HTTPException(status_code=400, detail="语义块稳定 ID 不能重复")
        if item.stable_id:
            seen_stable_ids.add(item.stable_id)

    await db.execute(delete(ArticleReviewSemanticBlock).where(
        ArticleReviewSemanticBlock.review_run_id == run.id,
    ))
    for item in sorted(blocks_in.blocks, key=lambda value: (value.side, value.ordinal)):
        stable_id = item.stable_id or f"sb-{item.side[:1]}-manual-{item.ordinal:04d}"
        db.add(ArticleReviewSemanticBlock(
            review_id=review.id,
            review_run_id=run.id,
            stable_id=stable_id[:120],
            side=item.side,
            ordinal=item.ordinal,
            text=item.text,
            normalized_text=normalize_semantic_text(item.text),
            start_offset=item.start_offset,
            end_offset=max(item.end_offset, item.start_offset),
            user_edited=bool(item.user_edited),
            locked=bool(blocks_in.lock),
            block_metadata={"source": "human_semantic_edit"},
        ))
    await db.execute(delete(ArticleReviewChange).where(ArticleReviewChange.review_run_id == run.id))
    await db.execute(delete(ArticleReviewReorderEvent).where(ArticleReviewReorderEvent.review_run_id == run.id))
    await db.execute(delete(ArticleReviewMethodologyCandidate).where(
        ArticleReviewMethodologyCandidate.review_run_id == run.id,
    ))
    review.change_groups = []
    review.ai_analysis = {
        "status": "queued",
        "summary": None,
        "key_changes": [],
        "methodology_candidates": [],
        "open_questions": ["语义块已人工调整，等待重新对齐"],
    }
    review.status = "analyzing"
    review.analysis_error = None
    await invalidate_downstream(db, run.run_id, "semantic_alignment")
    await update_run(
        db,
        run.run_id,
        status="queued",
        current_stage="semantic_alignment",
        requested_stage="semantic_alignment",
        error=None,
    )
    await update_stage(
        db,
        run.run_id,
        "semantic_segmentation",
        status="succeeded",
        progress=100,
        message="语义块已由人工确认",
        output={"block_count": len(blocks_in.blocks), "locked": blocks_in.lock},
    )
    await update_stage(
        db,
        run.run_id,
        "semantic_alignment",
        status="queued",
        progress=0,
        message="等待重新计算语义对齐",
        increment_attempt=True,
    )
    task_id = str(uuid.uuid4())
    review.analysis_task_id = task_id
    await update_stage(db, run.run_id, "semantic_alignment", task_id=task_id)
    await update_run(db, run.run_id, task_id=task_id)
    await db.commit()
    try:
        align_article_review_task.apply_async(
            args=[review.id, run.run_id],
            task_id=task_id,
        )
        await progress_store.push(run.run_id, {
            "event": "step_start",
            "data": {
                "step": 3,
                "stage": "semantic_alignment",
                "agent": "diff-engine",
                "action": "正在根据确认后的语义块重新对齐…",
            },
        })
    except Exception as exc:
        await db.rollback()
        await update_stage(
            db,
            run.run_id,
            "semantic_alignment",
            status="failed",
            error=str(exc),
            message="语义对齐任务提交失败",
        )
        await update_run(db, run.run_id, status="failed", error=str(exc))
        await db.commit()
        raise HTTPException(status_code=503, detail="语义对齐任务提交失败") from exc
    workflow = await load_workflow_entities(db, review_id, run.run_id)
    return {
        "code": 202,
        "message": "语义块已锁定，正在重新计算下游差异",
        "data": {"review": _review_payload(review), **workflow, "task_id": task_id},
    }


@router.put("/{review_id}/changes/{change_id}/review", response_model=dict)
async def review_article_review_change(
    review_id: int,
    change_id: int,
    change_in: ArticleReviewChangeReviewUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    """人工把算法结果标记为重要、不重要、误判或需要确认。"""

    await _require_review_access(db, current_user)
    review = await _load_review(db, review_id)
    if review is None:
        raise HTTPException(status_code=404, detail="文章复盘不存在")
    change = (await db.execute(
        select(ArticleReviewChange).where(
            ArticleReviewChange.id == change_id,
            ArticleReviewChange.review_id == review_id,
        )
    )).scalar_one_or_none()
    if change is None:
        raise HTTPException(status_code=404, detail="语义变化不存在")
    change.human_label = change_in.human_label
    change.human_note = change_in.human_note
    for group in review.change_groups or []:
        if group.get("id") == change.stable_id or group.get("stable_id") == change.stable_id:
            group["human_label"] = change_in.human_label
            group["human_note"] = change_in.human_note
    review.change_groups = list(review.change_groups or [])
    await db.commit()
    return {
        "code": 200,
        "message": "人工判断已保存",
        "data": {
            "change": {
                "id": change.id,
                "stable_id": change.stable_id,
                "human_label": change.human_label,
                "human_note": change.human_note,
            },
            "review": _review_payload(review),
        },
    }


@router.post("/{review_id}/stages/{stage_key}/retry", response_model=dict)
async def retry_article_review_stage(
    review_id: int,
    stage_key: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    """只重跑失败/失效阶段，已经成功的上游阶段保持不动。"""

    await _require_review_access(db, current_user)
    if stage_key not in STAGE_ORDER:
        raise HTTPException(status_code=400, detail="文章复盘阶段不合法")
    review = await _load_review(db, review_id)
    if review is None:
        raise HTTPException(status_code=404, detail="文章复盘不存在")
    run = await load_current_run(db, review_id, with_stages=False)
    if run is None:
        raise HTTPException(status_code=409, detail="当前复盘没有可恢复的运行记录")
    if stage_key == "methodology":
        raise HTTPException(status_code=400, detail="方法论阶段由 AI 分析完成后自动生成")
    stage = await update_stage(db, run.run_id, stage_key)
    if stage is None:
        raise HTTPException(status_code=409, detail="当前运行记录缺少目标阶段")
    if (
        stage
        and stage.status in {"queued", "running"}
        and stage.task_id
        and not is_stage_stale(stage)
    ):
        return {
            "code": 200,
            "message": "该阶段已有任务在排队或执行",
            "data": {"review": _review_payload(review), "task_id": stage.task_id},
        }
    if stage_key == "parse" and not (review.before_file_path and review.after_file_path):
        raise HTTPException(
            status_code=409,
            detail="原始文件已完成解析并清理，当前可从语义对齐阶段重试",
        )
    task_id = str(uuid.uuid4())
    review.analysis_task_id = task_id
    review.analysis_error = None
    review.status = "processing" if stage_key == "parse" else "analyzing"
    await update_stage(
        db,
        run.run_id,
        stage_key,
        status="queued",
        progress=0,
        message="阶段重试任务已排队",
        task_id=task_id,
        error=None,
        increment_attempt=True,
    )
    await update_run(
        db,
        run.run_id,
        status="queued",
        current_stage=stage_key,
        requested_stage=stage_key,
        task_id=task_id,
        error=None,
    )
    await db.commit()
    task = {
        "status": "queued",
        "task_id": task_id,
        "run_id": run.run_id,
        "stage": stage_key,
    }
    try:
        if stage_key == "parse":
            prepare_article_review_task.apply_async(
                args=[review.id, run.run_id],
                task_id=task_id,
            )
        elif stage_key == "semantic_segmentation":
            segment_article_review_task.apply_async(
                args=[review.id, run.run_id],
                task_id=task_id,
            )
        elif stage_key == "semantic_alignment":
            align_article_review_task.apply_async(
                args=[review.id, run.run_id],
                task_id=task_id,
            )
        elif stage_key == "ai_review":
            analyze_article_review_task.apply_async(
                args=[review.id, run.run_id],
                task_id=task_id,
            )
        else:
            raise HTTPException(status_code=400, detail="文章复盘阶段不支持手动提交")
        if stage_key in {"semantic_segmentation", "semantic_alignment", "ai_review"}:
            progress_stage = {
                "semantic_segmentation": "semantic_segmentation",
                "semantic_alignment": "semantic_alignment",
                "ai_review": "ai_review",
            }[stage_key]
            await progress_store.push(run.run_id, {
                "event": "step_start",
                "data": {
                    "step": {"semantic_segmentation": 3, "semantic_alignment": 3, "ai_review": 4}[progress_stage],
                    "stage": progress_stage,
                    "agent": "article-review-ai" if progress_stage == "ai_review" else "diff-engine",
                    "action": (
                        "正在重试 AI 复盘分析…" if progress_stage == "ai_review"
                        else "正在重试语义分段…" if progress_stage == "semantic_segmentation"
                        else "正在重试语义对齐…"
                    ),
                },
            })
    except HTTPException:
        raise
    except Exception as exc:
        await db.rollback()
        await update_stage(
            db,
            run.run_id,
            stage_key,
            status="failed",
            error=str(exc),
            message="阶段任务提交失败",
        )
        await update_run(db, run.run_id, status="failed", error=str(exc))
        await db.commit()
        raise HTTPException(status_code=503, detail="阶段任务提交失败") from exc
    loaded = await _load_review(db, review.id)
    return {
        "code": 202,
        "message": f"{stage_key} 阶段已重新提交",
        "data": {"review": _review_payload(loaded or review), "task": task},
    }


@router.post("/{review_id}/analyze", response_model=dict)
async def retry_article_review_analysis(
    review_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    await _require_review_access(db, current_user)
    review = await _load_review(db, review_id)
    if review is None:
        raise HTTPException(status_code=404, detail="文章复盘不存在")
    current_run = await load_current_run(db, review_id, with_stages=True)
    if current_run is not None:
        segmentation_stage = next(
            (item for item in current_run.stages if item.stage_key == "semantic_segmentation"),
            None,
        )
        if segmentation_stage is not None and segmentation_stage.status == "awaiting_confirmation":
            raise HTTPException(status_code=409, detail="请先确认或编辑语义分段，再启动 AI 复盘")
    active_stage = None
    if current_run is not None:
        active_stage = next(
            (item for item in current_run.stages if item.stage_key == current_run.current_stage),
            None,
        )
    task_is_stale = bool(active_stage and is_stage_stale(active_stage))
    if (
        review.status in {"processing", "analyzing"}
        and review.analysis_task_id
        and not task_is_stale
    ):
        return {
            "code": 200,
            "message": "已有 AI 分析任务在执行",
            "data": {
                "review": _review_payload(review),
                "task": {
                    "status": "queued",
                    "task_id": review.analysis_task_id,
                    "run_id": review.progress_run_id,
                },
            },
        }

    if not review.progress_run_id:
        review.progress_run_id = progress_store.create_run(user_id=current_user.id)
        await db.commit()

    needs_prepare = bool(
        review.before_file_path
        and review.after_file_path
        and not review.change_groups
    )
    if needs_prepare:
        task = await _enqueue_prepare(db, review)
    else:
        review.status = "analyzing"
        review.analysis_task_id = None
        review.analysis_error = None
        current = dict(review.ai_analysis or {}) if isinstance(review.ai_analysis, dict) else {}
        review.ai_analysis = {**current, "status": "queued", "error": None}
        await db.commit()
        task = await _enqueue_analysis(db, review)
    loaded = await _load_review(db, review.id)
    return {
        "code": 200,
        "message": "AI 差异分析已重新提交",
        "data": {"review": _review_payload(loaded or review), "task": task},
    }


@router.post("/{review_id}/methodology/{candidate_id}/confirm", response_model=dict)
async def confirm_article_review_methodology(
    review_id: int,
    candidate_id: int,
    confirm_in: ArticleReviewMethodologyConfirm,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    """确认或驳回候选方法论；确认本身不自动写入经验库。"""

    await _require_review_access(db, current_user)
    review = await _load_review(db, review_id)
    if review is None:
        raise HTTPException(status_code=404, detail="文章复盘不存在")
    candidate = (await db.execute(
        select(ArticleReviewMethodologyCandidate).where(
            ArticleReviewMethodologyCandidate.id == candidate_id,
            ArticleReviewMethodologyCandidate.review_id == review_id,
        )
    )).scalar_one_or_none()
    if candidate is None:
        raise HTTPException(status_code=404, detail="方法论候选不存在")
    candidate.status = confirm_in.status
    candidate.confirmed_by = current_user.id
    candidate.confirmed_at = utcnow()
    if confirm_in.conclusion:
        candidate.rationale = (
            f"{candidate.rationale or ''}\n人工确认结论：{confirm_in.conclusion}"
        ).strip()[:10_000]
    await db.commit()
    workflow = await load_workflow_entities(db, review_id)
    return {
        "code": 200,
        "message": "方法论候选已确认" if confirm_in.status == "confirmed" else "方法论候选已驳回",
        "data": {
            "candidate_id": candidate.id,
            "status": candidate.status,
            "review": _review_payload(review),
            **workflow,
        },
    }


@router.post("/{review_id}/promote", response_model=dict)
async def promote_article_review_methodology(
    review_id: int,
    promote_in: ArticleReviewPromote,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    """将单条方法论候选确认并沉淀到现有经验库。"""

    await _require_review_access(db, current_user)
    review = await _load_review(db, review_id)
    if review is None:
        raise HTTPException(status_code=404, detail="文章复盘不存在")
    selected_candidate = None
    if promote_in.methodology_candidate_id:
        selected_candidate = (await db.execute(
            select(ArticleReviewMethodologyCandidate).where(
                ArticleReviewMethodologyCandidate.id == promote_in.methodology_candidate_id,
                ArticleReviewMethodologyCandidate.review_id == review_id,
            )
        )).scalar_one_or_none()
        if selected_candidate is None:
            raise HTTPException(status_code=404, detail="方法论候选不存在")
        if selected_candidate.status == "rejected":
            raise HTTPException(status_code=409, detail="已驳回的方法论候选不能沉淀")
    available_ids = {group.get("id") for group in (review.change_groups or [])}
    selected_ids = promote_in.change_group_ids or (
        list(selected_candidate.evidence_change_ids or [])
        if selected_candidate is not None
        else [group.get("id") for group in (review.change_groups or []) if group.get("is_major")]
    )
    invalid_ids = [group_id for group_id in selected_ids if group_id not in available_ids]
    if invalid_ids:
        raise HTTPException(status_code=400, detail="沉淀的改动块不存在")
    analysis = review.ai_analysis if isinstance(review.ai_analysis, dict) else {}
    candidates = analysis.get("methodology_candidates") or []
    default_title = (
        selected_candidate.title
        if selected_candidate is not None
        else (candidates[0].get("title") if candidates and isinstance(candidates[0], dict) else None)
    )
    candidate_content = None
    if selected_candidate is not None:
        candidate_content = "\n\n".join([
            selected_candidate.title or "未命名方法",
            selected_candidate.rule or "",
            f"为什么：{selected_candidate.rationale or '未说明'}",
            f"本次例子：{selected_candidate.example or '未说明'}",
        ]).strip()
    card_title = promote_in.title or default_title or f"{review.title} · 修改方法论"
    content = build_review_experience_content(
        review,
        group_ids=selected_ids,
        custom_content=promote_in.content or candidate_content,
    )
    if not content:
        raise HTTPException(status_code=400, detail="没有可沉淀的复盘内容")
    existing_card_ids = list(review.promoted_card_ids or [])
    if existing_card_ids:
        existing_cards = (await db.execute(
            select(ExperienceCard).where(ExperienceCard.id.in_(existing_card_ids))
        )).scalars().all()
        selected_key = sorted(selected_ids)
        for existing in existing_cards:
            pair = existing.version_pair if isinstance(existing.version_pair, dict) else {}
            if (
                pair.get("review_id") == review.id
                and pair.get("methodology_candidate_id") == (selected_candidate.id if selected_candidate else None)
                and sorted(pair.get("change_group_ids") or []) == selected_key
                and (not promote_in.title or existing.title == card_title)
                and (not promote_in.content or existing.content == content)
            ):
                return {
                    "code": 200,
                    "message": "该复盘方法论已经沉淀过",
                    "data": {
                        "card": build_card_payload(
                            existing,
                            creator=current_user,
                            source_creation=None,
                            suggestion=None,
                            source_accessible=None,
                        ),
                        "embedding": {
                            "status": existing.embedding_status,
                            "task_id": existing.embedding_task_id,
                        },
                        "review_id": review.id,
                        "change_group_ids": selected_ids,
                        "idempotent": True,
                    },
                }
    run = await load_current_run(db, review.id, with_stages=False)
    candidate_rows = []
    if run is not None:
        candidate_rows = (await db.execute(
            select(ArticleReviewMethodologyCandidate).where(
                ArticleReviewMethodologyCandidate.review_id == review.id,
                ArticleReviewMethodologyCandidate.review_run_id == run.id,
            )
        )).scalars().all()
    card = await create_experience_card(
        db,
        title=card_title,
        content=content,
        category=promote_in.category or "文章复盘",
        source_type="review_feedback",
        creation_id=None,
        version_pair={
            "review_id": review.id,
            "methodology_candidate_id": selected_candidate.id if selected_candidate is not None else None,
            "change_group_ids": selected_ids,
            "before_filename": review.before_filename,
            "after_filename": review.after_filename,
        },
        suggestion_id=None,
        created_by=current_user.id,
    )
    normalized_changes = []
    if run is not None:
        normalized_changes = (await db.execute(
            select(ArticleReviewChange).where(
                ArticleReviewChange.review_id == review.id,
                ArticleReviewChange.review_run_id == run.id,
                ArticleReviewChange.stable_id.in_(selected_ids),
            )
        )).scalars().all()
    for change in normalized_changes:
        comment_rows = (await db.execute(
            select(ArticleReviewComment.id).where(
                ArticleReviewComment.review_id == review.id,
                or_(
                    ArticleReviewComment.change_id == change.id,
                    ArticleReviewComment.change_group_id == change.stable_id,
                ),
            )
        )).scalars().all()
        db.add(ArticleReviewExperienceSource(
            experience_card_id=card.id,
            review_id=review.id,
            review_run_id=run.id if run is not None else None,
            change_id=change.id,
            comment_ids=list(comment_rows),
            confirmed_conclusion=(
                change.human_note
                or (change.ai_analysis or {}).get("effect")
                if isinstance(change.ai_analysis, dict)
                else change.human_note
            ),
            confirmed_by=current_user.id,
            confirmed_at=utcnow(),
        ))
    if not normalized_changes:
        for group_id in selected_ids:
            group = next(
                (item for item in (review.change_groups or []) if item.get("id") == group_id),
                {},
            )
            comment_rows = (await db.execute(
                select(ArticleReviewComment.id).where(
                    ArticleReviewComment.review_id == review.id,
                    ArticleReviewComment.change_group_id == group_id,
                )
            )).scalars().all()
            db.add(ArticleReviewExperienceSource(
                experience_card_id=card.id,
                review_id=review.id,
                review_run_id=run.id if run is not None else None,
                comment_ids=list(comment_rows),
                confirmed_conclusion=group.get("human_note") or group.get("significance_reason"),
                confirmed_by=current_user.id,
                confirmed_at=utcnow(),
            ))
    if selected_candidate is not None:
        selected_candidate.status = "promoted"
        selected_candidate.confirmed_by = current_user.id
        selected_candidate.confirmed_at = selected_candidate.confirmed_at or utcnow()
        selected_candidate.experience_card_id = card.id
    else:
        for candidate in candidate_rows:
            if set(candidate.evidence_change_ids or []) & set(selected_ids):
                candidate.status = "promoted"
                candidate.experience_card_id = card.id
    embedding = await enqueue_embedding(card, db)
    review.promoted_card_ids = list(dict.fromkeys([*(review.promoted_card_ids or []), card.id]))
    await db.commit()
    return {
        "code": 200,
        "message": "复盘方法论已沉淀到经验库",
        "data": {
            "card": build_card_payload(
                card,
                creator=current_user,
                source_creation=None,
                suggestion=None,
                source_accessible=None,
            ),
            "embedding": embedding,
            "review_id": review.id,
            "methodology_candidate_id": selected_candidate.id if selected_candidate is not None else None,
            "change_group_ids": selected_ids,
        },
    }
