"""潜在商单 API — 时间轴视图 + 筛选维度。"""

from collections import defaultdict
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import and_, case, desc, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_current_user
from app.db.session import get_db
from app.models.raw_info import RawInfo
from app.models.source_registry import SourceRegistry
from app.models.user import User
from app.services.commercial_classification import (
    BRAND_DISPLAY_ORDER,
    CATEGORY_DISPLAY_ORDER,
)

router = APIRouter()


# ── 基础查询条件：仅公众号 + 命中商单 ──────────────────────────

def _wechat_commercial_filters(
    level: Optional[str] = None,
    brand: Optional[str] = None,
    category: Optional[str] = None,
    keyword: Optional[str] = None,
) -> list:
    """构建通用筛选条件列表。"""
    filters: list = [
        RawInfo.commercial_level.in_(["suspected", "likely"]),
        # 仅公众号来源：通过 URL 域名判断（platform 存的是 slug 不是域名）
        RawInfo.url.ilike("%mp.weixin.qq.com%"),
    ]
    if level:
        filters[0] = RawInfo.commercial_level == level
    if brand:
        filters.append(RawInfo.commercial_brand == brand)
    if category:
        filters.append(RawInfo.commercial_category == category)
    if keyword:
        filters.append(
            or_(
                RawInfo.title.ilike(f"%{keyword}%"),
                RawInfo.summary.ilike(f"%{keyword}%"),
            )
        )
    return filters


def _serialize_row(row: Any) -> dict:
    """序列化单条 RawInfo + 来源信息。"""
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
        "commercial_level": raw.commercial_level or "none",
        "commercial_brand": raw.commercial_brand or "",
        "commercial_category": raw.commercial_category or "",
        "product": meta.get("product") or "",
        "reason": meta.get("reason") or "",
    }


# ── GET /commercial/timeline ──────────────────────────────────

@router.get("/timeline", response_model=dict)
async def get_commercial_timeline(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    brand: Optional[str] = Query(None, description="按甲方筛选"),
    category: Optional[str] = Query(None, description="按功能方向筛选"),
    level: Optional[str] = Query(None, description="suspected / likely"),
    keyword: Optional[str] = Query(None),
    days: int = Query(14, ge=1, le=90, description="最近 N 天"),
) -> Any:
    """时间轴：按天分组，返回潜在商单列表。"""
    filters = _wechat_commercial_filters(level=level, brand=brand, category=category, keyword=keyword)

    # 截断日期范围（scraped_at 是 naive datetime，cutoff 也要 naive）
    from datetime import datetime, timedelta
    cutoff = datetime.utcnow() - timedelta(days=days)

    filters.append(RawInfo.scraped_at >= cutoff)

    query = (
        select(
            RawInfo,
            SourceRegistry.name.label("source_name"),
        )
        .outerjoin(SourceRegistry, RawInfo.source_registry_id == SourceRegistry.id)
        .where(*filters)
        .order_by(desc(RawInfo.scraped_at))
        .limit(500)
    )
    rows = (await db.execute(query)).all()

    # 按天分组
    groups: Dict[str, List[dict]] = defaultdict(list)
    for row in rows:
        raw = row[0]
        day_key = raw.scraped_at.strftime("%Y-%m-%d") if raw.scraped_at else "unknown"
        groups[day_key].append(_serialize_row(row))

    # 排序输出（日期降序）
    timeline = [
        {"date": day, "items": items}
        for day, items in sorted(groups.items(), reverse=True)
    ]

    return {
        "code": 200,
        "message": "获取潜在商单时间轴成功",
        "data": {
            "timeline": timeline,
            "total": sum(len(g["items"]) for g in timeline),
        },
    }


# ── GET /commercial/filters ───────────────────────────────────

@router.get("/filters", response_model=dict)
async def get_commercial_filters(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    """返回可用的筛选维度（甲方 + 功能方向），带计数。"""
    base_filter = [
        RawInfo.commercial_level.in_(["suspected", "likely"]),
        RawInfo.url.ilike("%mp.weixin.qq.com%"),
    ]

    # 品牌分布
    brand_query = (
        select(
            RawInfo.commercial_brand,
            func.count(RawInfo.id).label("count"),
        )
        .outerjoin(SourceRegistry, RawInfo.source_registry_id == SourceRegistry.id)
        .where(*base_filter)
        .where(RawInfo.commercial_brand.isnot(None))
        .where(RawInfo.commercial_brand != "")
        .group_by(RawInfo.commercial_brand)
        .order_by(desc("count"))
    )
    brand_rows = (await db.execute(brand_query)).all()
    valid_brands = set(BRAND_DISPLAY_ORDER) | {"其他"}
    brands = [
        {"value": r[0], "label": r[0], "count": r[1]}
        for r in brand_rows
        if r[0] in valid_brands
    ]

    # 功能方向分布
    cat_query = (
        select(
            RawInfo.commercial_category,
            func.count(RawInfo.id).label("count"),
        )
        .outerjoin(SourceRegistry, RawInfo.source_registry_id == SourceRegistry.id)
        .where(*base_filter)
        .where(RawInfo.commercial_category.isnot(None))
        .where(RawInfo.commercial_category != "")
        .group_by(RawInfo.commercial_category)
        .order_by(desc("count"))
    )
    cat_rows = (await db.execute(cat_query)).all()
    categories = [{"value": r[0], "label": r[0], "count": r[1]} for r in cat_rows]

    return {
        "code": 200,
        "message": "获取筛选维度成功",
        "data": {
            "brands": brands,
            "categories": categories,
            "brand_display_order": BRAND_DISPLAY_ORDER,
            "category_display_order": CATEGORY_DISPLAY_ORDER,
        },
    }


# ── GET /commercial/raw-infos (兼容旧接口) ────────────────────

@router.get("/raw-infos", response_model=dict)
async def list_commercial_raw_infos(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    page: int = Query(1, ge=1),
    page_size: int = Query(30, ge=1, le=200),
    level: Optional[str] = Query(None, description="suspected / likely"),
    keyword: Optional[str] = Query(None),
) -> Any:
    """兼容旧接口：列出商单检测结果（仅公众号来源）。"""
    filters = _wechat_commercial_filters(level=level, keyword=keyword)

    count_q = (
        select(func.count(RawInfo.id))
        .outerjoin(SourceRegistry, RawInfo.source_registry_id == SourceRegistry.id)
        .where(*filters)
    )
    total = (await db.execute(count_q)).scalar() or 0

    query = (
        select(
            RawInfo,
            SourceRegistry.name.label("source_name"),
            SourceRegistry.platform.label("source_platform"),
        )
        .outerjoin(SourceRegistry, RawInfo.source_registry_id == SourceRegistry.id)
        .where(*filters)
        .order_by(desc(RawInfo.scraped_at).nulls_last())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    rows = (await db.execute(query)).all()

    return {
        "code": 200,
        "message": "获取潜在商单列表成功",
        "data": {
            "items": [_serialize_row(row) for row in rows],
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": (total + page_size - 1) // page_size,
        },
    }


# ── POST /commercial/raw-infos/{id}/detect (手动重检测) ───────

@router.post("/raw-infos/{raw_info_id}/detect", response_model=dict)
async def rerun_commercial_detection(
    raw_info_id: int,
    force_llm: bool = Query(False),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    """手动重新检测单篇文章的商单属性。"""
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
