"""文章版本快照、文本 diff 和异步语义摘要接口（Phase 1c）。"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import desc, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.progress import progress_store
from app.core.security import get_current_user
from app.db.session import get_db
from app.models.content_version import ContentVersion
from app.models.creation import ContentCreation
from app.models.meeting import MeetingSuggestion
from app.models.user import User
from app.schemas.content_version import ContentVersionCreate
from app.services.content_snapshot import build_content_snapshot
from app.services.content_version_service import (
    build_experience_content,
    build_text_diff,
    get_pair_summary,
    semantic_summary_status,
    set_pair_summary,
)
from app.services.experience_service import create_experience_card, enqueue_embedding
from app.services.team_service import (
    can_access_creation,
    can_access_team_collaboration,
    can_edit_creation,
)
from app.tasks.content_version_tasks import summarize_version_diff_task

router = APIRouter()


def _iso(value: Optional[datetime]) -> Optional[str]:
    return value.isoformat() if value else None


def _user_payload(user: Optional[User]) -> Optional[dict]:
    if user is None:
        return None
    return {
        "id": user.id,
        "username": user.username,
        "full_name": user.full_name,
        "role": user.role,
    }


def _suggestion_payload(suggestion: Optional[MeetingSuggestion]) -> Optional[dict]:
    if suggestion is None:
        return None
    return {
        "id": suggestion.id,
        "meeting_id": suggestion.meeting_id,
        "content": suggestion.content,
        "category": suggestion.category,
        "priority": suggestion.priority,
        "status": suggestion.status,
        "related_creation_id": suggestion.related_creation_id,
        "related_version_id": suggestion.related_version_id,
    }


def _version_payload(
    version: ContentVersion,
    *,
    include_content: bool = False,
    include_suggestion: bool = True,
) -> dict:
    payload = {
        "id": version.id,
        "creation_id": version.creation_id,
        "version_no": version.version_no,
        "version_type": version.version_type,
        "title": version.title,
        "word_count": version.word_count,
        "note": version.note,
        "created_by": version.created_by,
        "created_by_user": _user_payload(version.creator),
        "suggestion_id": version.suggestion_id,
        "suggestion": _suggestion_payload(version.suggestion) if include_suggestion else None,
        "has_semantic_summary": semantic_summary_status(version.diff_summary) is not None,
        "semantic_summary_status": semantic_summary_status(version.diff_summary),
        "created_at": _iso(version.created_at),
        "updated_at": _iso(version.updated_at),
    }
    if include_content:
        payload.update({
            "content_json": version.content_json,
            "content_text": version.content_text,
            "diff_summary": version.diff_summary,
        })
    return payload


async def _get_creation(db: AsyncSession, creation_id: int) -> ContentCreation:
    creation = (await db.execute(
        select(ContentCreation).where(ContentCreation.id == creation_id)
    )).scalar_one_or_none()
    if creation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="创作不存在")
    return creation


async def _load_versions_for_diff(
    db: AsyncSession,
    creation_id: int,
    before_version_id: int,
    after_version_id: int,
) -> tuple[ContentCreation, ContentVersion, ContentVersion]:
    creation = await _get_creation(db, creation_id)
    versions = (await db.execute(
        select(ContentVersion)
        .where(ContentVersion.id.in_([before_version_id, after_version_id]))
        .options(
            selectinload(ContentVersion.creator),
            selectinload(ContentVersion.suggestion),
        )
    )).scalars().all()
    by_id = {version.id: version for version in versions}
    before = by_id.get(before_version_id)
    after = by_id.get(after_version_id)
    if before is None or after is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="版本不存在")
    if before.creation_id != creation_id or after.creation_id != creation_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="只能比较同一篇文章的版本")
    return creation, before, after


async def _validate_suggestion(
    db: AsyncSession,
    current_user: User,
    creation_id: int,
    suggestion_id: int,
) -> MeetingSuggestion:
    if not await can_access_team_collaboration(db, current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权关联会议建议")
    suggestion = (await db.execute(
        select(MeetingSuggestion).where(MeetingSuggestion.id == suggestion_id)
    )).scalar_one_or_none()
    if suggestion is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="会议建议不存在")
    if suggestion.related_creation_id != creation_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="会议建议尚未关联当前文章，不能绕过文章权限建立版本关联",
        )
    return suggestion


async def _save_version(
    db: AsyncSession,
    *,
    creation_id: int,
    created_by: int,
    version_in: ContentVersionCreate,
) -> tuple[ContentVersion, Optional[ContentVersion]]:
    """在文章行锁下分配版本号；唯一约束异常时重试。"""

    for attempt in range(3):
        try:
            locked_creation = (await db.execute(
                select(ContentCreation)
                .where(ContentCreation.id == creation_id)
                .with_for_update()
            )).scalar_one_or_none()
            if locked_creation is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="创作不存在")

            max_no = (await db.execute(
                select(func.max(ContentVersion.version_no)).where(
                    ContentVersion.creation_id == creation_id
                )
            )).scalar_one()
            previous = (await db.execute(
                select(ContentVersion)
                .where(
                    ContentVersion.creation_id == creation_id,
                    ContentVersion.version_no == max_no,
                )
            )).scalar_one_or_none() if max_no is not None else None
            version_no = int(max_no or 0) + 1
            snapshot = build_content_snapshot(locked_creation.content)
            version = ContentVersion(
                creation_id=creation_id,
                version_no=version_no,
                version_type=version_in.version_type,
                title=locked_creation.title,
                content_json=snapshot[0],
                content_text=snapshot[1],
                word_count=snapshot[2],
                note=version_in.note,
                created_by=created_by,
                suggestion_id=version_in.suggestion_id,
            )
            db.add(version)
            await db.flush()
            if version_in.suggestion_id:
                suggestion = (await db.execute(
                    select(MeetingSuggestion).where(MeetingSuggestion.id == version_in.suggestion_id)
                )).scalar_one_or_none()
                if suggestion is not None:
                    suggestion.related_version_id = version.id
            await db.commit()
            await db.refresh(version)
            return version, previous
        except IntegrityError:
            await db.rollback()
            if attempt == 2:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="版本号分配发生并发冲突，请重试",
                )
    raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="版本号分配失败")


async def _load_version_with_relations(db: AsyncSession, version_id: int) -> Optional[ContentVersion]:
    return (await db.execute(
        select(ContentVersion)
        .where(ContentVersion.id == version_id)
        .options(
            selectinload(ContentVersion.creator),
            selectinload(ContentVersion.suggestion),
        )
    )).scalar_one_or_none()


@router.post("/{creation_id}/versions", response_model=dict)
async def save_creation_version(
    creation_id: int,
    version_in: ContentVersionCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    creation = await _get_creation(db, creation_id)
    if not await can_edit_creation(db, current_user, creation):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权保存文章版本")
    if version_in.suggestion_id:
        await _validate_suggestion(db, current_user, creation_id, version_in.suggestion_id)

    version, previous = await _save_version(
        db,
        creation_id=creation_id,
        created_by=current_user.id,
        version_in=version_in,
    )
    version = await _load_version_with_relations(db, version.id) or version

    experience_result = {
        "requested": bool(version_in.save_as_experience),
        "status": "not_requested",
        "card": None,
        "embedding": None,
    }
    if version_in.save_as_experience:
        try:
            suggestion_text = version.suggestion.content if version.suggestion else None
            before = previous
            if before is None:
                before = version
            text_diff = build_text_diff(
                previous.content_text if previous else "",
                version.content_text,
                before_label=f"v{previous.version_no}" if previous else "empty",
                after_label=f"v{version.version_no}",
            )
            card_content = build_experience_content(
                before_version=previous,
                after_version=version,
                text_diff=text_diff,
                note=version.note,
                suggestion_text=suggestion_text,
            )
            card_title = version_in.experience_title or (
                f"文章版本变更经验 · v{previous.version_no} → v{version.version_no}"
                if previous
                else f"文章版本经验 · v{version.version_no}"
            )
            card = await create_experience_card(
                db,
                title=card_title,
                content=card_content,
                source_type="meeting_diff",
                created_by=current_user.id,
                category=version_in.experience_category,
                creation_id=creation_id,
                version_pair={
                    "before": previous.id if previous else None,
                    "after": version.id,
                },
                suggestion_id=version.suggestion_id,
            )
            embedding_result = await enqueue_embedding(card, db)
            experience_result = {
                "requested": True,
                "status": "created",
                "card": {
                    "id": card.id,
                    "title": card.title,
                    "embedding_status": card.embedding_status,
                },
                "embedding": embedding_result,
            }
        except Exception as exc:
            # 版本已经独立提交；经验卡片生成异常只返回失败状态，不能回滚版本。
            await db.rollback()
            experience_result = {
                "requested": True,
                "status": "failed",
                "error": str(exc)[:1000],
                "card": None,
                "embedding": None,
            }

    return {
        "code": 200,
        "message": "文章版本保存成功",
        "data": {
            "version": _version_payload(version, include_content=True),
            "experience": experience_result,
        },
    }


@router.get("/{creation_id}/versions", response_model=dict)
async def list_creation_versions(
    creation_id: int,
    version_type: Optional[str] = Query(None, max_length=20),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    creation = await _get_creation(db, creation_id)
    if not await can_access_creation(db, current_user, creation):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权访问文章版本")
    filters = [ContentVersion.creation_id == creation_id]
    if version_type:
        filters.append(ContentVersion.version_type == version_type.strip().lower())
    rows = (await db.execute(
        select(ContentVersion)
        .where(*filters)
        .options(
            selectinload(ContentVersion.creator),
            selectinload(ContentVersion.suggestion),
        )
        .order_by(desc(ContentVersion.version_no), desc(ContentVersion.created_at))
    )).scalars().all()
    suggestions = (await db.execute(
        select(MeetingSuggestion)
        .where(MeetingSuggestion.related_creation_id == creation_id)
        .order_by(MeetingSuggestion.id.desc())
    )).scalars().all()
    return {
        "code": 200,
        "message": "文章版本列表获取成功",
        "data": {
            "items": [_version_payload(row) for row in rows],
            "total": len(rows),
            "creation_id": creation_id,
            "suggestions": [_suggestion_payload(item) for item in suggestions],
        },
    }


# 静态 diff 路由必须在 /{version_id} 之前定义，避免被动态路由拦截。
@router.get("/{creation_id}/versions/diff", response_model=dict)
async def diff_creation_versions(
    creation_id: int,
    a: int = Query(..., ge=1),
    b: int = Query(..., ge=1),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    creation, before, after = await _load_versions_for_diff(db, creation_id, a, b)
    if not await can_access_creation(db, current_user, creation):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权访问文章版本")
    diff = build_text_diff(
        before.content_text,
        after.content_text,
        before_label=f"v{before.version_no}",
        after_label=f"v{after.version_no}",
    )
    return {
        "code": 200,
        "message": "文章版本文本 diff 获取成功",
        "data": {
            "before_version_id": before.id,
            "after_version_id": after.id,
            "before_version_no": before.version_no,
            "after_version_no": after.version_no,
            "before_title": before.title,
            "after_title": after.title,
            "before_word_count": before.word_count,
            "after_word_count": after.word_count,
            "semantic_summary": get_pair_summary(after.diff_summary, before.id, after.id),
            **diff,
        },
    }


@router.post("/{creation_id}/versions/diff/summary", response_model=dict)
async def summarize_creation_versions(
    creation_id: int,
    a: int = Query(..., ge=1),
    b: int = Query(..., ge=1),
    retry: bool = Query(False),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    creation, before, after = await _load_versions_for_diff(db, creation_id, a, b)
    if not await can_access_creation(db, current_user, creation):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权访问文章版本")
    if before.id == after.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="不能对比同一个版本")

    locked_after = (await db.execute(
        select(ContentVersion)
        .where(ContentVersion.id == after.id)
        .with_for_update()
    )).scalar_one()
    existing = get_pair_summary(locked_after.diff_summary, before.id, after.id)
    if existing and existing.get("status") != "failed":
        return {
            "code": 200,
            "message": "已返回现有语义摘要任务",
            "data": {"task": existing, "deduplicated": True},
        }
    if existing and existing.get("status") == "failed" and not retry:
        return {
            "code": 200,
            "message": "语义摘要上次失败，可点击重试",
            "data": {"task": existing, "deduplicated": True},
        }

    run_id = progress_store.create_run(user_id=current_user.id)
    task_id = str(uuid.uuid4())
    task_state = {
        "status": "queued",
        "task_id": task_id,
        "run_id": run_id,
        "before_version_id": before.id,
        "after_version_id": after.id,
        "summary": None,
        "changes": [],
        "suggestion_match": None,
        "raw_output": existing.get("raw_output", "") if existing else "",
        "parsed_at": None,
    }
    locked_after.diff_summary = set_pair_summary(
        locked_after.diff_summary,
        before.id,
        after.id,
        task_state,
    )
    await db.commit()
    try:
        summarize_version_diff_task.apply_async(
            args=[creation_id, before.id, after.id, run_id],
            task_id=task_id,
        )
    except Exception as exc:
        failed_after = (await db.execute(
            select(ContentVersion).where(ContentVersion.id == after.id)
        )).scalar_one_or_none()
        error = str(exc)[:1000]
        if failed_after is not None:
            failed_after.diff_summary = set_pair_summary(
                failed_after.diff_summary,
                before.id,
                after.id,
                {**task_state, "status": "failed", "error": error},
            )
            await db.commit()
        await progress_store.push(run_id, {"event": "error", "data": {"message": error}})
        task_state = {**task_state, "status": "failed", "error": error}

    return {
        "code": 200,
        "message": "语义差异摘要任务已提交" if task_state["status"] == "queued" else "语义差异摘要任务提交失败",
        "data": {"task": task_state, "deduplicated": False},
    }


@router.get("/{creation_id}/versions/{version_id}", response_model=dict)
async def get_creation_version(
    creation_id: int,
    version_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    creation = await _get_creation(db, creation_id)
    if not await can_access_creation(db, current_user, creation):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权访问文章版本")
    version = await _load_version_with_relations(db, version_id)
    if version is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="版本不存在")
    if version.creation_id != creation_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="版本不属于当前文章")
    return {
        "code": 200,
        "message": "文章版本详情获取成功",
        "data": _version_payload(version, include_content=True),
    }
