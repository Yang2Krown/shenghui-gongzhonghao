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
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.progress import progress_store
from app.core.rate_limit import enforce_rate_limit, rule_from_setting, user_actor
from app.core.security import get_current_user
from app.core.upload_security import UploadSecurityError, validate_document_upload
from app.db.session import AsyncSessionLocal, get_db
from app.models.article_review import ArticleReview, ArticleReviewComment
from app.models.user import User
from app.schemas.article_review import (
    ArticleReviewAnalysisUpdate,
    ArticleReviewCommentCreate,
    ArticleReviewPromote,
)
from app.services.article_review_service import (
    ArticleReviewAnalysisError,
    build_review_experience_content,
    normalize_article_review_analysis,
)
from app.services.experience_service import build_card_payload, create_experience_card, enqueue_embedding
from app.services.team_service import can_access_team_collaboration
from app.tasks.article_review_tasks import analyze_article_review_task, prepare_article_review_task

logger = logging.getLogger(__name__)
router = APIRouter()

MAX_REVIEW_UPLOAD_SIZE = 20 * 1024 * 1024


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
        "body": comment.body,
        "resolved": bool(comment.resolved),
        "author_id": comment.author_id,
        "author": _user_payload(comment.author),
        "created_at": _iso(comment.created_at),
        "updated_at": _iso(comment.updated_at),
    }


def _review_payload(review: ArticleReview, *, include_groups: bool = True) -> dict:
    groups = list(review.change_groups or [])
    major = [group for group in groups if group.get("is_major")]
    analysis = review.ai_analysis if isinstance(review.ai_analysis, dict) else None
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
        "comments": [_comment_payload(comment) for comment in (review.comments or [])],
        "promoted_card_ids": list(review.promoted_card_ids or []),
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


async def _read_review_upload(file: UploadFile) -> tuple[str, bytes, str]:
    if not file.filename:
        raise HTTPException(status_code=400, detail="上传文件名不能为空")
    data = await file.read()
    try:
        safe = validate_document_upload(
            filename=file.filename,
            data=data,
            max_size=MAX_REVIEW_UPLOAD_SIZE,
        )
    except UploadSecurityError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return file.filename, safe.data, safe.ext


async def _stage_review_uploads(
    before_file: UploadFile,
    after_file: UploadFile,
) -> tuple[str, str, str, str]:
    """只做快速校验并把原始文件放入 web/worker 共用的暂存 volume。"""

    before_filename, before_data, before_ext = await _read_review_upload(before_file)
    after_filename, after_data, after_ext = await _read_review_upload(after_file)
    stage_dir = Path(settings.UPLOAD_DIR).resolve() / "article_reviews" / f"pending-{uuid.uuid4().hex}"
    before_path = stage_dir / f"before{before_ext}"
    after_path = stage_dir / f"after{after_ext}"
    try:
        await asyncio.to_thread(stage_dir.mkdir, parents=True, exist_ok=False)
        await asyncio.gather(
            asyncio.to_thread(before_path.write_bytes, before_data),
            asyncio.to_thread(after_path.write_bytes, after_data),
        )
    except Exception:
        await asyncio.to_thread(shutil.rmtree, stage_dir, True)
        raise
    return before_filename, str(before_path), after_filename, str(after_path)


async def _enqueue_analysis(db: AsyncSession, review: ArticleReview) -> dict:
    """提交 AI 任务；提交失败不丢弃已经算出的文本 diff。"""

    task_id = str(uuid.uuid4())
    if not review.progress_run_id:
        review.progress_run_id = progress_store.create_run(user_id=review.created_by)
    review.analysis_task_id = task_id
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


@router.post("", response_model=dict)
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
    await db.commit()
    await db.refresh(review)
    task = await _enqueue_prepare(db, review)
    loaded = await _load_review(db, review.id)
    return {
        "code": 200,
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
) -> StreamingResponse:
    """以 SSE 推送文件解析、diff 和 AI 分析进度。"""

    await _require_review_access(db, current_user)
    review = await _load_review(db, review_id)
    if review is None:
        raise HTTPException(status_code=404, detail="文章复盘不存在")
    run_id = review.progress_run_id

    async def event_stream():
        if not run_id:
            yield "event: progress\ndata: {\"exists\":false}\n\n"
            return
        last_payload = None
        for index in range(1_800):
            snapshot = await progress_store.snapshot_async(run_id, user_id=current_user.id)
            if snapshot is not None:
                payload = {"review_id": review_id, "progress": snapshot}
                serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True)
                if serialized != last_payload:
                    yield f"event: progress\ndata: {serialized}\n\n"
                    last_payload = serialized
                if snapshot.get("done"):
                    return
            # Redis 降级到内存时，API 和 Celery 进程看不到同一份事件；此时用数据库终态
            # 收口 SSE，避免前端因进度存储故障一直等待。
            if snapshot is None or index % 5 == 0:
                async with AsyncSessionLocal() as status_db:
                    row = (await status_db.execute(
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
                    yield f"event: progress\ndata: {serialized}\n\n"
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
        .options(selectinload(ArticleReview.creator))
        .order_by(ArticleReview.created_at.desc(), ArticleReview.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )).scalars().all()
    return {
        "code": 200,
        "message": "文章复盘列表获取成功",
        "data": {
            "items": [_review_payload(row, include_groups=False) for row in rows],
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": (total + page_size - 1) // page_size,
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
    return {
        "code": 200,
        "message": "文章复盘详情获取成功",
        "data": _review_payload(review),
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
    comment = ArticleReviewComment(
        review_id=review.id,
        change_group_id=comment_in.change_group_id,
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
    current.update(analysis_in.model_dump(exclude_unset=True))
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
    await db.commit()
    loaded = await _load_review(db, review.id)
    return {
        "code": 200,
        "message": "文章复盘分析已保存人工修订",
        "data": {"review": _review_payload(loaded or review)},
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
    if review.status in {"processing", "analyzing"} and review.analysis_task_id:
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


@router.post("/{review_id}/promote", response_model=dict)
async def promote_article_review_methodology(
    review_id: int,
    promote_in: ArticleReviewPromote,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    """把人工确认后的复盘结果沉淀到现有经验库。"""

    await _require_review_access(db, current_user)
    review = await _load_review(db, review_id)
    if review is None:
        raise HTTPException(status_code=404, detail="文章复盘不存在")
    available_ids = {group.get("id") for group in (review.change_groups or [])}
    selected_ids = promote_in.change_group_ids or [
        group.get("id") for group in (review.change_groups or []) if group.get("is_major")
    ]
    invalid_ids = [group_id for group_id in selected_ids if group_id not in available_ids]
    if invalid_ids:
        raise HTTPException(status_code=400, detail="沉淀的改动块不存在")
    analysis = review.ai_analysis if isinstance(review.ai_analysis, dict) else {}
    candidates = analysis.get("methodology_candidates") or []
    default_title = (candidates[0].get("title") if candidates and isinstance(candidates[0], dict) else None)
    card_title = promote_in.title or default_title or f"{review.title} · 修改方法论"
    content = build_review_experience_content(
        review,
        group_ids=selected_ids,
        custom_content=promote_in.content,
    )
    if not content:
        raise HTTPException(status_code=400, detail="没有可沉淀的复盘内容")
    card = await create_experience_card(
        db,
        title=card_title,
        content=content,
        category=promote_in.category or "文章复盘",
        source_type="review_feedback",
        creation_id=None,
        version_pair={
            "review_id": review.id,
            "change_group_ids": selected_ids,
            "before_filename": review.before_filename,
            "after_filename": review.after_filename,
        },
        suggestion_id=None,
        created_by=current_user.id,
    )
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
            "change_group_ids": selected_ids,
        },
    }
