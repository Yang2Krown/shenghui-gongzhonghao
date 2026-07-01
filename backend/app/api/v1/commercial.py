"""Commercial soft-ad review APIs."""

from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import desc, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_current_user
from app.db.session import get_db
from app.models.raw_info import RawInfo
from app.models.source_registry import SourceRegistry
from app.models.user import User

router = APIRouter()


def _serialize_raw(row: Any) -> dict:
    raw = row[0]
    meta = raw.commercial_meta or {}
    return {
        "id": raw.id,
        "title": raw.title,
        "url": raw.url,
        "author": raw.author,
        "summary": raw.summary,
        "published_at": raw.published_at.isoformat() if raw.published_at else None,
        "scraped_at": raw.scraped_at.isoformat() if raw.scraped_at else None,
        "source_name": row.source_name or "未知来源",
        "source_platform": row.source_platform or "",
        "commercial_level": raw.commercial_level or "none",
        "commercial_meta": meta,
        "product": meta.get("product") or "",
        "reason": meta.get("reason") or "",
    }


@router.get("/raw-infos", response_model=dict)
async def list_commercial_raw_infos(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    page: int = Query(1, ge=1),
    page_size: int = Query(30, ge=1, le=200),
    level: Optional[str] = Query(None, description="suspected / likely / none"),
    keyword: Optional[str] = Query(None),
) -> Any:
    """List RawInfo rows with commercial detection results."""
    levels = [level] if level else ["suspected", "likely"]
    filters = [RawInfo.commercial_level.in_(levels)]
    if keyword:
        filters.append(
            or_(
                RawInfo.title.ilike(f"%{keyword}%"),
                RawInfo.summary.ilike(f"%{keyword}%"),
                RawInfo.content.ilike(f"%{keyword}%"),
            )
        )

    count_q = select(func.count(RawInfo.id)).where(*filters)
    total = (await db.execute(count_q)).scalar() or 0

    query = (
        select(
            RawInfo,
            SourceRegistry.name.label("source_name"),
            SourceRegistry.platform.label("source_platform"),
        )
        .outerjoin(SourceRegistry, RawInfo.source_registry_id == SourceRegistry.id)
        .where(*filters)
        .order_by(desc(RawInfo.published_at).nulls_last(), desc(RawInfo.scraped_at).nulls_last())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    rows = (await db.execute(query)).all()

    return {
        "code": 200,
        "message": "获取疑似商单列表成功",
        "data": {
            "items": [_serialize_raw(row) for row in rows],
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": (total + page_size - 1) // page_size,
        },
    }


@router.post("/raw-infos/{raw_info_id}/detect", response_model=dict)
async def rerun_commercial_detection(
    raw_info_id: int,
    force_llm: bool = Query(False),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    """Queue a single RawInfo row for commercial detection."""
    exists = (
        await db.execute(select(RawInfo.id).where(RawInfo.id == raw_info_id))
    ).scalar_one_or_none()
    if not exists:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="原文不存在")

    from app.tasks.commercial_tasks import detect_commercial_task

    detect_commercial_task.delay(raw_info_id, force_llm=force_llm)
    return {
        "code": 200,
        "message": "已提交商单检测任务",
        "data": {"raw_info_id": raw_info_id, "force_llm": force_llm},
    }
