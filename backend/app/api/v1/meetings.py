"""Phase 1b 会议纪要与方法论沉淀接口。"""

from collections import defaultdict
from datetime import datetime, timedelta
import logging
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.progress import progress_store
from app.core.security import get_current_user
from app.core.timezone import utcnow
from app.db.session import get_db
from app.models.creation import ContentCreation
from app.models.meeting import Meeting, MeetingSuggestion, MeetingSynthesis
from app.models.meeting_methodology import MeetingMethodologyCluster, MeetingMethodologySource
from app.models.user import User
from app.schemas.meeting import (
    MEETING_STATUSES,
    SUGGESTION_STATUSES,
    MeetingCreate,
    MeetingSuggestionLinkRequest,
    MeetingSuggestionUpdate,
    MeetingSynthesisUpdate,
)
from app.services.meeting_synthesis import (
    METHODOLOGY_CATEGORIES,
    normalize_synthesis_payload,
)
from app.services.meeting_methodology_dedup import (
    backfill_missing_methodology_clusters,
    prune_orphan_methodology_clusters,
    sync_methodology_clusters,
)
from app.services.team_service import (
    can_access_creation,
    can_access_team_collaboration,
)
from app.tasks.meeting_tasks import extract_meeting_suggestions_task

router = APIRouter()
logger = logging.getLogger(__name__)

STATUS_TRANSITIONS = {
    "proposed": {"adopted", "rejected"},
    "adopted": {"in_progress", "rejected"},
    "in_progress": {"done", "rejected"},
    "done": set(),
    "rejected": set(),
}


async def _require_meeting_access(db: AsyncSession, user: User) -> None:
    if not await can_access_team_collaboration(db, user):
        raise HTTPException(status_code=403, detail="仅在职员工和管理员可访问会议协作")


async def _get_meeting(
    db: AsyncSession,
    meeting_id: int,
    *,
    with_suggestions: bool = True,
) -> Optional[Meeting]:
    options = [selectinload(Meeting.creator), selectinload(Meeting.synthesis)]
    if with_suggestions:
        options.append(
            selectinload(Meeting.suggestions)
            .selectinload(MeetingSuggestion.owner)
        )
        options.append(
            selectinload(Meeting.suggestions)
            .selectinload(MeetingSuggestion.creation)
        )
    return (await db.execute(
        select(Meeting).where(Meeting.id == meeting_id).options(*options)
    )).scalar_one_or_none()


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


def _suggestion_payload(suggestion: MeetingSuggestion) -> dict:
    creation = suggestion.creation
    return {
        "id": suggestion.id,
        "meeting_id": suggestion.meeting_id,
        "content": suggestion.content,
        "proposer": suggestion.proposer,
        "category": suggestion.category,
        "priority": suggestion.priority,
        "acceptance_criteria": suggestion.acceptance_criteria,
        "status": suggestion.status,
        "owner_id": suggestion.owner_id,
        "owner": _user_payload(suggestion.owner),
        "resolution_note": suggestion.resolution_note,
        "related_creation_id": suggestion.related_creation_id,
        "related_creation": (
            {"id": creation.id, "title": creation.title}
            if creation is not None
            else None
        ),
        # Phase 1c 尚未实现，接口始终返回 null，不伪造版本对象。
        "related_version_id": suggestion.related_version_id,
        "closed_at": _iso(suggestion.closed_at),
        "is_manually_edited": bool(suggestion.is_manually_edited),
        "created_at": _iso(suggestion.created_at),
        "updated_at": _iso(suggestion.updated_at),
    }


def _synthesis_payload(synthesis: Optional[MeetingSynthesis]) -> Optional[dict]:
    if synthesis is None:
        return None
    return {
        "id": synthesis.id,
        "meeting_id": synthesis.meeting_id,
        "summary": synthesis.summary,
        "methodology": synthesis.methodology or [],
        "checklist": synthesis.checklist or [],
        "decisions": synthesis.decisions or [],
        "disagreements": synthesis.disagreements or [],
        "open_questions": synthesis.open_questions or [],
        "follow_ups": synthesis.follow_ups or [],
        "parse_status": synthesis.parse_status,
        "is_manually_edited": bool(synthesis.is_manually_edited),
        "created_at": _iso(synthesis.created_at),
        "updated_at": _iso(synthesis.updated_at),
    }


def _meeting_payload(meeting: Meeting, *, include_suggestions: bool = False) -> dict:
    suggestions = list(meeting.suggestions or [])
    status_counts = {status: 0 for status in SUGGESTION_STATUSES}
    for suggestion in suggestions:
        if suggestion.status in status_counts:
            status_counts[suggestion.status] += 1
    payload = {
        "id": meeting.id,
        "title": meeting.title,
        "meeting_at": _iso(meeting.meeting_at),
        "raw_text": meeting.raw_text,
        "source_kind": meeting.source_kind,
        "status": meeting.status,
        "created_by": meeting.created_by,
        "created_by_user": _user_payload(meeting.creator),
        "extract_task_id": meeting.extract_task_id,
        "extract_run_id": meeting.extract_run_id,
        "created_at": _iso(meeting.created_at),
        "updated_at": _iso(meeting.updated_at),
        "suggestion_count": len(suggestions),
        "status_counts": status_counts,
        "synthesis": _synthesis_payload(meeting.synthesis)
        if include_suggestions
        else None,
        "synthesis_summary": meeting.synthesis.summary if meeting.synthesis else None,
        "synthesis_parse_status": meeting.synthesis.parse_status if meeting.synthesis else None,
        "synthesis_counts": {
            "methodology": len(meeting.synthesis.methodology or [])
            if meeting.synthesis
            else 0,
            "checklist": len(meeting.synthesis.checklist or [])
            if meeting.synthesis
            else 0,
            "decisions": len(meeting.synthesis.decisions or [])
            if meeting.synthesis
            else 0,
            "disagreements": len(meeting.synthesis.disagreements or [])
            if meeting.synthesis
            else 0,
            "open_questions": len(meeting.synthesis.open_questions or [])
            if meeting.synthesis
            else 0,
            "follow_ups": len(meeting.synthesis.follow_ups or [])
            if meeting.synthesis
            else 0,
        },
    }
    if include_suggestions:
        payload["suggestions"] = [_suggestion_payload(item) for item in suggestions]
    return payload


def _task_payload(
    meeting: Meeting,
    *,
    task_id: Optional[str] = None,
    run_id: Optional[str] = None,
    deduplicated: bool = False,
    status: str = "queued",
) -> dict:
    return {
        "task_id": task_id or meeting.extract_task_id,
        "run_id": run_id or meeting.extract_run_id,
        "status": status,
        "deduplicated": deduplicated,
    }


async def _enqueue_extraction(db: AsyncSession, meeting: Meeting) -> dict:
    """提交提取任务，并把 Celery/ProgressStore ID 写入会议记录。"""
    # 在生产 PostgreSQL 中用行锁串行化重试/重复点击；首个新会议尚未有
    # extract_run_id，允许继续创建任务，之后的请求直接复用已有运行态。
    locked_meeting = (await db.execute(
        select(Meeting).where(Meeting.id == meeting.id).with_for_update()
    )).scalar_one()
    if locked_meeting.status == "extracting" and locked_meeting.extract_run_id:
        return _task_payload(locked_meeting, deduplicated=True)

    meeting = locked_meeting
    run_id = progress_store.create_run(user_id=meeting.created_by)
    meeting.status = "extracting"
    meeting.extract_run_id = run_id
    meeting.extract_task_id = None
    await db.commit()

    try:
        task = extract_meeting_suggestions_task.apply_async(
            args=[meeting.id, run_id]
        )
    except Exception as exc:
        await db.rollback()
        failed = await _get_meeting(db, meeting.id, with_suggestions=False)
        if failed is not None:
            failed.status = "failed"
            await db.commit()
        await progress_store.push(
            run_id,
            {"event": "error", "data": {"message": f"任务投递失败：{str(exc)[:300]}"}},
        )
        raise HTTPException(status_code=503, detail="提取任务暂时无法提交") from exc

    meeting.extract_task_id = str(task.id)
    await db.commit()
    return _task_payload(meeting, task_id=str(task.id), run_id=run_id)


@router.post("", response_model=dict)
async def create_meeting(
    meeting_in: MeetingCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    """创建会议记录；LLM 提取通过 Celery 异步执行。"""
    await _require_meeting_access(db, current_user)
    meeting = Meeting(
        title=meeting_in.title,
        meeting_at=meeting_in.meeting_at,
        raw_text=meeting_in.raw_text,
        source_kind="pasted_text",
        status="extracting",
        created_by=current_user.id,
    )
    db.add(meeting)
    await db.flush()
    task_info = await _enqueue_extraction(db, meeting)
    loaded = await _get_meeting(db, meeting.id)
    return {
        "code": 200,
        "message": "会议已创建，方法论整理任务已提交",
        "data": {
            "meeting": _meeting_payload(loaded or meeting, include_suggestions=True),
            "task": task_info,
        },
    }


@router.get("", response_model=dict)
async def list_meetings(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    keyword: Optional[str] = Query(None, max_length=100),
    status: Optional[str] = Query(None, alias="status"),
    start_at: Optional[datetime] = Query(None),
    end_at: Optional[datetime] = Query(None),
    meeting_at_from: Optional[datetime] = Query(None),
    meeting_at_to: Optional[datetime] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    await _require_meeting_access(db, current_user)
    if status and status not in MEETING_STATUSES:
        raise HTTPException(status_code=400, detail="会议状态不合法")
    lower_bound = start_at or meeting_at_from
    upper_bound = end_at or meeting_at_to

    filters = []
    if keyword and keyword.strip():
        like = f"%{keyword.strip()}%"
        filters.append(or_(Meeting.title.ilike(like), Meeting.raw_text.ilike(like)))
    if status:
        filters.append(Meeting.status == status)
    if lower_bound:
        filters.append(Meeting.meeting_at >= lower_bound)
    if upper_bound:
        filters.append(Meeting.meeting_at <= upper_bound)

    total_count = (await db.execute(
        select(func.count(Meeting.id)).where(*filters)
    )).scalar_one()
    rows = (await db.execute(
        select(Meeting)
        .where(*filters)
        .options(
            selectinload(Meeting.creator),
            selectinload(Meeting.suggestions),
            selectinload(Meeting.synthesis),
        )
        .order_by(Meeting.meeting_at.desc(), Meeting.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )).scalars().all()
    return {
        "code": 200,
        "message": "会议列表获取成功",
        "data": {
            "items": [_meeting_payload(row) for row in rows],
            "total": total_count,
            "page": page,
            "page_size": page_size,
            "total_pages": (total_count + page_size - 1) // page_size,
        },
    }


@router.get("/summary", response_model=dict)
async def meeting_summary(
    start_at: Optional[datetime] = Query(None),
    end_at: Optional[datetime] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    """按主题汇总方法论，供会议方法论首页快速查阅。"""
    await _require_meeting_access(db, current_user)
    filters = []
    if start_at:
        filters.append(Meeting.meeting_at >= start_at)
    if end_at:
        filters.append(Meeting.meeting_at <= end_at)
    meetings = (await db.execute(
        select(Meeting)
        .where(*filters)
        .options(selectinload(Meeting.synthesis))
        .order_by(Meeting.meeting_at.desc(), Meeting.id.desc())
    )).scalars().all()

    # 为已部署语义归并前产生的 JSON 沉淀补建来源投影；只走本地文本兜底，
    # 不在 GET 请求里调用 embedding/LLM，后续重新整理时再补充向量。
    await backfill_missing_methodology_clusters(db, meetings)
    await prune_orphan_methodology_clusters(db)
    await db.commit()

    cluster_filters = [MeetingMethodologyCluster.status == "active"]
    if start_at:
        cluster_filters.append(MeetingMethodologySource.meeting_id.in_(
            select(Meeting.id).where(Meeting.meeting_at >= start_at)
        ))
    if end_at:
        cluster_filters.append(MeetingMethodologySource.meeting_id.in_(
            select(Meeting.id).where(Meeting.meeting_at <= end_at)
        ))
    clusters = (await db.execute(
        select(MeetingMethodologyCluster)
        .join(MeetingMethodologyCluster.sources)
        .where(*cluster_filters)
        .options(
            selectinload(MeetingMethodologyCluster.sources)
            .selectinload(MeetingMethodologySource.meeting)
        )
        .distinct()
        .order_by(MeetingMethodologyCluster.id)
    )).scalars().unique().all()

    def source_in_range(source: MeetingMethodologySource) -> bool:
        meeting = source.meeting
        if meeting is None:
            return False
        return (not start_at or meeting.meeting_at >= start_at) and (not end_at or meeting.meeting_at <= end_at)

    def source_payload(source: MeetingMethodologySource) -> dict:
        return {
            "meeting_id": source.meeting_id,
            "meeting_title": source.meeting.title if source.meeting else "未知会议",
            "meeting_at": _iso(source.meeting.meeting_at) if source.meeting else None,
            "item": source.item or {},
            "similarity": source.similarity,
            "match_kind": source.match_kind,
        }

    grouped = {definition["key"]: [] for definition in METHODOLOGY_CATEGORIES}
    for cluster in clusters:
        sources = [source for source in cluster.sources if source_in_range(source)]
        if not sources:
            continue
        primary = next((source for source in sources if source.is_primary), sources[0])
        source_list = [source_payload(source) for source in sources]
        item = {
            "type": cluster.section,
            "title": cluster.title,
            "rule": cluster.rule,
            "rationale": cluster.rationale,
            "example": cluster.example,
            "evidence": cluster.evidence,
            "when_to_use": cluster.rationale if cluster.section == "checklist" else None,
            "meeting_id": primary.meeting_id,
            "meeting_title": primary.meeting.title if primary.meeting else "未知会议",
            "meeting_at": _iso(primary.meeting.meeting_at) if primary.meeting else None,
            "cluster_id": cluster.id,
            "source_count": len(source_list),
            "meeting_count": len({source["meeting_id"] for source in source_list}),
            "sources": source_list,
        }
        grouped.setdefault(cluster.category, []).append(item)

    total_methodology = sum(len(items) for items in grouped.values() for item in items if item["type"] == "methodology")
    total_checklist = sum(len(items) for items in grouped.values() for item in items if item["type"] == "checklist")
    total_meetings = len({source["meeting_id"] for items in grouped.values() for item in items for source in item["sources"]})

    categories = []
    for definition in METHODOLOGY_CATEGORIES:
        items = grouped.get(definition["key"], [])
        if not items:
            continue
        categories.append({
            "key": definition["key"],
            "title": definition["title"],
            "description": definition["description"],
            "item_count": len(items),
            "methodology_count": sum(item["type"] == "methodology" for item in items),
            "checklist_count": sum(item["type"] == "checklist" for item in items),
            "meeting_count": len({source["meeting_id"] for item in items for source in item["sources"]}),
            "preview_titles": [item["title"] for item in items[:3]],
            "items": items,
        })

    return {
        "code": 200,
        "message": "会议方法论汇总获取成功",
        "data": {
            "total_meetings": total_meetings,
            "total_methodology": total_methodology,
            "total_checklist": total_checklist,
            "total_items": total_methodology + total_checklist,
            "categories": categories,
        },
    }


@router.get("/stats", response_model=dict)
async def meeting_stats(
    start_at: Optional[datetime] = Query(None),
    end_at: Optional[datetime] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    """方法论沉淀看板：只统计沉淀内容，不把会议强行变成任务 KPI。"""
    await _require_meeting_access(db, current_user)
    filters = []
    if start_at:
        filters.append(Meeting.meeting_at >= start_at)
    if end_at:
        filters.append(Meeting.meeting_at <= end_at)
    meetings = (await db.execute(
        select(Meeting)
        .where(*filters)
        .options(selectinload(Meeting.synthesis), selectinload(Meeting.suggestions))
        .order_by(Meeting.meeting_at.desc(), Meeting.id.desc())
    )).scalars().all()

    def item_counts(meeting: Meeting) -> dict[str, int]:
        synthesis = meeting.synthesis
        return {
            "methodology": len(synthesis.methodology or []) if synthesis else 0,
            "checklist": len(synthesis.checklist or []) if synthesis else 0,
            "decisions": len(synthesis.decisions or []) if synthesis else 0,
            "disagreements": len(synthesis.disagreements or []) if synthesis else 0,
            "open_questions": len(synthesis.open_questions or []) if synthesis else 0,
            "follow_ups": len(synthesis.follow_ups or []) if synthesis else 0,
            "optional_action_items": len(meeting.suggestions or []),
        }

    def aggregate(items: list[Meeting]) -> dict:
        counts = {status: 0 for status in MEETING_STATUSES}
        totals = {
            key: 0
            for key in (
                "methodology",
                "checklist",
                "decisions",
                "disagreements",
                "open_questions",
                "follow_ups",
                "optional_action_items",
            )
        }
        for meeting in items:
            if meeting.status in counts:
                counts[meeting.status] += 1
            for key, value in item_counts(meeting).items():
                totals[key] += value
        return {
            "total_meetings": len(items),
            "meeting_status_counts": counts,
            **{f"total_{key}": value for key, value in totals.items()},
        }

    def grouped(key_func) -> list[dict]:
        groups: dict[Any, list[Meeting]] = defaultdict(list)
        labels: dict[Any, Any] = {}
        for meeting in meetings:
            label = key_func(meeting)
            group_key = tuple(sorted(label.items())) if isinstance(label, dict) else label
            groups[group_key].append(meeting)
            labels[group_key] = label
        result = []
        for group_key, items in groups.items():
            row = aggregate(items)
            label = labels[group_key]
            row.update(label if isinstance(label, dict) else {"key": label})
            result.append(row)
        return result

    def week_key(meeting: Meeting) -> dict:
        meeting_at = meeting.meeting_at
        if meeting_at is None:
            return {"week": None}
        monday = (meeting_at - timedelta(days=meeting_at.weekday())).date()
        return {"week": monday.isoformat()}

    def meeting_key(meeting: Meeting) -> dict:
        return {"meeting_id": meeting.id, "title": meeting.title}

    overall = aggregate(meetings)
    return {
        "code": 200,
        "message": "会议方法论统计获取成功",
        "data": {
            **overall,
            "by_week": sorted(grouped(week_key), key=lambda row: row.get("week") or ""),
            "by_meeting": grouped(meeting_key),
        },
    }


@router.get("/{meeting_id}", response_model=dict)
async def get_meeting(
    meeting_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    await _require_meeting_access(db, current_user)
    meeting = await _get_meeting(db, meeting_id)
    if meeting is None:
        raise HTTPException(status_code=404, detail="会议不存在")
    return {
        "code": 200,
        "message": "会议详情获取成功",
        "data": _meeting_payload(meeting, include_suggestions=True),
    }


@router.put("/{meeting_id}/synthesis", response_model=dict)
async def update_meeting_synthesis(
    meeting_id: int,
    synthesis_in: MeetingSynthesisUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    """允许团队把 AI 初稿修订成真正可复用的内部方法论。"""
    await _require_meeting_access(db, current_user)
    meeting = await _get_meeting(db, meeting_id)
    if meeting is None:
        raise HTTPException(status_code=404, detail="会议不存在")

    current = {
        "summary": meeting.synthesis.summary if meeting.synthesis else None,
        "methodology": meeting.synthesis.methodology if meeting.synthesis else [],
        "checklist": meeting.synthesis.checklist if meeting.synthesis else [],
        "decisions": meeting.synthesis.decisions if meeting.synthesis else [],
        "disagreements": meeting.synthesis.disagreements if meeting.synthesis else [],
        "open_questions": meeting.synthesis.open_questions if meeting.synthesis else [],
        "follow_ups": meeting.synthesis.follow_ups if meeting.synthesis else [],
    }
    current.update(synthesis_in.model_dump(exclude_unset=True))
    try:
        normalized = normalize_synthesis_payload(current, parse_status="parsed")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    synthesis = meeting.synthesis
    if synthesis is None:
        synthesis = MeetingSynthesis(meeting_id=meeting.id)
        db.add(synthesis)
    for field in (
        "summary",
        "methodology",
        "checklist",
        "decisions",
        "disagreements",
        "open_questions",
        "follow_ups",
    ):
        setattr(synthesis, field, normalized[field])
    synthesis.is_manually_edited = True
    await db.commit()
    dedup_stats = {"source_count": 0, "new_clusters": 0, "merged": 0, "reviewed": 0}
    response_data = _synthesis_payload(synthesis)
    try:
        dedup_stats = await sync_methodology_clusters(
            db,
            meeting.id,
            {
                "methodology": normalized["methodology"],
                "checklist": normalized["checklist"],
            },
        )
        await db.commit()
    except Exception as dedup_exc:
        await db.rollback()
        # 主沉淀已先提交，语义投影失败可在下一次整理/汇总时重建。
        logger.warning("会议方法论人工修订后的语义归并失败 meeting_id=%s: %s", meeting.id, dedup_exc)
    return {
        "code": 200,
        "message": "会议方法论沉淀已保存",
        "data": {
            **(response_data or {}),
            "dedup": dedup_stats,
        },
    }


@router.post("/{meeting_id}/extract", response_model=dict)
async def extract_meeting(
    meeting_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    await _require_meeting_access(db, current_user)
    meeting = await _get_meeting(db, meeting_id)
    if meeting is None:
        raise HTTPException(status_code=404, detail="会议不存在")

    if meeting.status == "extracting":
        return {
            "code": 200,
            "message": "已有方法论整理任务在执行",
            "data": {
                "meeting": _meeting_payload(meeting, include_suggestions=True),
                "task": _task_payload(meeting, deduplicated=True),
            },
        }

    task_info = await _enqueue_extraction(db, meeting)
    loaded = await _get_meeting(db, meeting.id)
    return {
        "code": 200,
        "message": "方法论整理任务已重新提交",
        "data": {
            "meeting": _meeting_payload(loaded or meeting, include_suggestions=True),
            "task": task_info,
        },
    }


@router.put("/suggestions/{suggestion_id}", response_model=dict)
async def update_meeting_suggestion(
    suggestion_id: int,
    suggestion_in: MeetingSuggestionUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    suggestion = (await db.execute(
        select(MeetingSuggestion)
        .where(MeetingSuggestion.id == suggestion_id)
        .options(
            selectinload(MeetingSuggestion.meeting),
            selectinload(MeetingSuggestion.owner),
            selectinload(MeetingSuggestion.creation),
        )
    )).scalar_one_or_none()
    if suggestion is None:
        raise HTTPException(status_code=404, detail="会议建议不存在")
    await _require_meeting_access(db, current_user)

    changes = suggestion_in.model_dump(exclude_unset=True)
    next_status = changes.get("status")
    if next_status and next_status != suggestion.status:
        allowed = STATUS_TRANSITIONS.get(suggestion.status, set())
        if next_status not in allowed:
            raise HTTPException(
                status_code=400,
                detail=f"不允许从 {suggestion.status} 流转到 {next_status}",
            )

    if next_status == "rejected" or suggestion.status == "rejected":
        reason = changes.get("resolution_note", suggestion.resolution_note)
        if not reason or not str(reason).strip():
            raise HTTPException(status_code=400, detail="驳回必须填写原因")

    if "owner_id" in changes and changes["owner_id"] is not None:
        owner = await db.get(User, changes["owner_id"])
        if owner is None or not await can_access_team_collaboration(db, owner):
            raise HTTPException(status_code=400, detail="负责人必须是在职员工或管理员")

    if next_status == "done" and suggestion.status != "done":
        suggestion.closed_at = utcnow()
    if next_status == "done" and suggestion.closed_at is None:
        suggestion.closed_at = utcnow()

    mutable_fields = {
        "content",
        "proposer",
        "category",
        "priority",
        "acceptance_criteria",
        "status",
        "owner_id",
        "resolution_note",
    }
    for field, value in changes.items():
        if field in mutable_fields:
            setattr(suggestion, field, value)
    if mutable_fields.intersection(changes):
        suggestion.is_manually_edited = True

    await db.commit()
    updated = (await db.execute(
        select(MeetingSuggestion)
        .where(MeetingSuggestion.id == suggestion_id)
        .options(
            selectinload(MeetingSuggestion.owner),
            selectinload(MeetingSuggestion.creation),
        )
    )).scalar_one()
    return {
        "code": 200,
        "message": "会议建议已更新",
        "data": _suggestion_payload(updated),
    }


@router.post("/suggestions/{suggestion_id}/link", response_model=dict)
async def link_meeting_suggestion(
    suggestion_id: int,
    link_in: MeetingSuggestionLinkRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    suggestion = (await db.execute(
        select(MeetingSuggestion)
        .where(MeetingSuggestion.id == suggestion_id)
        .options(selectinload(MeetingSuggestion.meeting))
    )).scalar_one_or_none()
    if suggestion is None:
        raise HTTPException(status_code=404, detail="会议建议不存在")
    await _require_meeting_access(db, current_user)

    creation = await db.get(ContentCreation, link_in.creation_id)
    if creation is None:
        raise HTTPException(status_code=404, detail="关联文章不存在")
    # 关联动作必须经过既有文章对象权限，不能因为用户能看会议就越权看文章。
    if not await can_access_creation(db, current_user, creation):
        raise HTTPException(status_code=403, detail="无权访问要关联的文章")

    suggestion.related_creation_id = creation.id
    suggestion.related_version_id = None
    suggestion.is_manually_edited = True
    await db.commit()
    updated = (await db.execute(
        select(MeetingSuggestion)
        .where(MeetingSuggestion.id == suggestion_id)
        .options(
            selectinload(MeetingSuggestion.owner),
            selectinload(MeetingSuggestion.creation),
        )
    )).scalar_one()
    return {
        "code": 200,
        "message": "会议建议已关联文章",
        "data": _suggestion_payload(updated),
    }
