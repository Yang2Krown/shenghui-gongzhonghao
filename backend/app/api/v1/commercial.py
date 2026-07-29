"""潜在商单 API — 品牌聚合视图 + 兼容时间轴视图。"""

from collections import defaultdict
import re
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import and_, case, desc, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.admin_permissions import require_admin_permission
from app.core.security import get_current_user
from app.db.session import get_db
from app.models.raw_info import RawInfo
from app.models.source_registry import SourceRegistry, SourceAccount
from app.models.user import User
from app.services.commercial_classification import (
    BRAND_DISPLAY_ORDER,
    CATEGORY_DISPLAY_ORDER,
    normalize_commercial_label,
)

router = APIRouter()

FOREIGN_PRODUCT_TERMS = (
    "anthropic", "claude", "openai", "chatgpt", "codex", "copilot",
    "gemini", "perplexity", "grok", "xai", "x.ai", "google", "meta",
    "llama", "mistral", "midjourney", "runway", "pika", "elevenlabs",
    "cursor", "windsurf", "lovable", "replit", "notion", "canva", "figma",
    "adobe", "microsoft", "nvidia", "apple", "amazon", "aws", "sora",
    "dall-e", "dalle", "马斯克", "谷歌", "微软", "英伟达", "苹果", "亚马逊",
)
UNTITLED_PREFIX = "未命名文章"


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
        # 仅公众号/极致了来源。URL 有时是短链或长链，source_type 更稳。
        or_(
            RawInfo.url.ilike("%mp.weixin.qq.com%"),
            SourceRegistry.source_type.in_(["dajiala_wechat", "sogou_wechat", "exa_wechat"]),
        ),
        RawInfo.title.isnot(None),
        RawInfo.title != "",
        ~RawInfo.title.ilike(f"{UNTITLED_PREFIX}%"),
    ]
    for term in FOREIGN_PRODUCT_TERMS:
        filters.append(~RawInfo.title.ilike(f"%{term}%"))
        filters.append(or_(RawInfo.commercial_brand.is_(None), ~RawInfo.commercial_brand.ilike(f"%{term}%")))
    if level:
        filters[0] = RawInfo.commercial_level == level
    if brand:
        filters.append(or_(
            RawInfo.commercial_brand == brand,
            RawInfo.commercial_meta["brand"].as_string() == brand,
        ))
    if category:
        filters.append(or_(
            RawInfo.commercial_category == category,
            RawInfo.commercial_meta["category"].as_string() == category,
        ))
    if keyword:
        filters.append(
            or_(
                RawInfo.title.ilike(f"%{keyword}%"),
                RawInfo.summary.ilike(f"%{keyword}%"),
                RawInfo.commercial_brand.ilike(f"%{keyword}%"),
                RawInfo.commercial_category.ilike(f"%{keyword}%"),
                RawInfo.commercial_meta["brand"].as_string().ilike(f"%{keyword}%"),
                RawInfo.commercial_meta["category"].as_string().ilike(f"%{keyword}%"),
                RawInfo.commercial_meta["product"].as_string().ilike(f"%{keyword}%"),
            )
        )
    return filters


def _serialize_row(row: Any) -> dict:
    """序列化单条 RawInfo + 来源信息。"""
    raw = row[0]
    meta = raw.commercial_meta or {}
    account_name = getattr(row, "source_account_name", None) or raw.author or ""
    brand = normalize_commercial_label(raw.commercial_brand or meta.get("brand"))
    product = normalize_commercial_label(meta.get("product"))
    return {
        "id": raw.id,
        "title": raw.title,
        "url": raw.url,
        "author": raw.author,
        "summary": raw.summary,
        "published_at": raw.published_at.isoformat() if raw.published_at else None,
        "scraped_at": raw.scraped_at.isoformat() if raw.scraped_at else None,
        "source_name": row.source_name or "未知来源",
        "source_account_name": account_name,
        "commercial_level": raw.commercial_level or "none",
        "commercial_brand": brand,
        "commercial_category": raw.commercial_category or meta.get("category") or "",
        "product": product,
        "reason": meta.get("reason") or "",
        "advantages": meta.get("advantages") or [],
        "evidence": meta.get("evidence") or [],
    }


_GENERIC_PRODUCT_SUFFIX_RE = re.compile(
    r"(?:设计)?(?:agent|智能体|ai助手|平台|制作服务|服务|工具)$",
    re.IGNORECASE,
)


def _canonical_product(product: str, brand: str = "") -> str:
    """Normalize product variants enough to keep one product on one card."""
    value = normalize_commercial_label(product)
    company = normalize_commercial_label(brand)
    if company and value.lower().startswith(company.lower()):
        value = value[len(company):].lstrip(" -·：:")
    previous = None
    while value and value != previous:
        previous = value
        value = _GENERIC_PRODUCT_SUFFIX_RE.sub("", value).strip(" -·：:")
    return value


def _commercial_subject(item: dict) -> tuple[str, str, str]:
    """Return stable group key, display label, and canonical product."""
    brand = normalize_commercial_label(item.get("commercial_brand"))
    product = _canonical_product(item.get("product") or "", brand)
    if brand and product:
        display = brand if product.lower() == brand.lower() else f"{brand} {product}"
    else:
        display = product or brand or "未识别品牌"
    return display.lower(), display, product


def _time_value(item: dict) -> str:
    return item.get("published_at") or item.get("scraped_at") or ""


def _is_frontend_noise(item: dict) -> bool:
    """Hide stale/dirty positives without waiting for a full re-detect."""
    title = item.get("title") or ""
    if not title or title.startswith(UNTITLED_PREFIX):
        return True

    haystack = "\n".join([
        title,
        item.get("commercial_brand") or "",
        item.get("product") or "",
        item.get("summary") or "",
    ]).lower()
    return any(term in haystack for term in FOREIGN_PRODUCT_TERMS)


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

    # 截断日期范围（published_at 是 naive datetime，cutoff 也要 naive）
    from datetime import datetime, timedelta
    cutoff = datetime.utcnow() - timedelta(days=days)

    filters.append(RawInfo.published_at >= cutoff)

    query = (
        select(
            RawInfo,
            SourceRegistry.name.label("source_name"),
            SourceAccount.display_name.label("source_account_name"),
        )
        .outerjoin(SourceRegistry, RawInfo.source_registry_id == SourceRegistry.id)
        .outerjoin(SourceAccount, RawInfo.source_account_id == SourceAccount.id)
        .where(*filters)
        .order_by(desc(RawInfo.published_at))
        .limit(500)
    )
    rows = (await db.execute(query)).all()

    # 按天分组
    groups: Dict[str, List[dict]] = defaultdict(list)
    for row in rows:
        raw = row[0]
        item = _serialize_row(row)
        if _is_frontend_noise(item):
            continue
        day_key = raw.published_at.strftime("%Y-%m-%d") if raw.published_at else "unknown"
        groups[day_key].append(item)

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

@router.get("/diagnostics", response_model=dict)
async def get_commercial_diagnostics(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin_permission("monitoring:read")),
    days: int = Query(30, ge=1, le=180, description="前端当前时间范围"),
) -> Any:
    """诊断潜在商单为空的具体原因。"""
    from datetime import datetime, timedelta

    cutoff = datetime.utcnow() - timedelta(days=days)

    rows = (await db.execute(
        select(
            RawInfo.content,
            RawInfo.commercial_level,
            RawInfo.commercial_meta,
            RawInfo.published_at,
        )
        .join(SourceRegistry, RawInfo.source_registry_id == SourceRegistry.id)
        .where(SourceRegistry.source_type == "dajiala_wechat")
    )).all()

    data = {
        "total": len(rows),
        "total_in_days": 0,
        "with_fulltext": 0,
        "ai_done": 0,
        "ai_none": 0,
        "suspected": 0,
        "likely": 0,
        "frontend_visible": 0,
    }
    for content, level, meta, published_at in rows:
        in_days = bool(published_at and published_at >= cutoff)
        meta = meta or {}
        signals = meta.get("signals") if isinstance(meta, dict) else {}
        if in_days:
            data["total_in_days"] += 1
        if len(content or "") > 300:
            data["with_fulltext"] += 1
        if isinstance(signals, dict) and signals.get("layer") == "llm":
            data["ai_done"] += 1
        if level == "none":
            data["ai_none"] += 1
        elif level == "suspected":
            data["suspected"] += 1
        elif level == "likely":
            data["likely"] += 1
        if level in ("suspected", "likely") and in_days:
            data["frontend_visible"] += 1

    if data["total"] == 0:
        diagnosis = "极致了文章还没有入库。先跑历史补库或等待当天发文任务。"
    elif data["with_fulltext"] == 0:
        diagnosis = "文章已入库，但没有抓到正文。需要跑全文补抓任务。"
    elif data["ai_done"] == 0:
        diagnosis = "正文已有，但还没有完成 DeepSeek 商单判断。需要触发重检。"
    elif data["suspected"] + data["likely"] == 0:
        diagnosis = "DeepSeek 已判断，但全部是 none。前端为空是因为没有 suspected/likely。"
    elif data["frontend_visible"] == 0:
        diagnosis = f"有商单结果，但不在最近 {days} 天范围内。切到 90/180 天看。"
    else:
        diagnosis = "后端已有可展示商单；如果前端仍为空，是页面筛选或接口请求问题。"

    data["diagnosis"] = diagnosis
    return {"code": 200, "message": "获取潜在商单诊断成功", "data": data}


@router.get("/filters", response_model=dict)
async def get_commercial_filters(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    """返回可用的筛选维度（甲方 + 功能方向），带计数。"""
    base_filter = _wechat_commercial_filters()
    brand_expr = func.coalesce(
        func.nullif(RawInfo.commercial_brand, ""),
        RawInfo.commercial_meta["brand"].as_string(),
    )
    category_expr = func.coalesce(
        func.nullif(RawInfo.commercial_category, ""),
        RawInfo.commercial_meta["category"].as_string(),
    )

    # 品牌分布
    brand_query = (
        select(
            brand_expr.label("brand"),
            func.count(RawInfo.id).label("count"),
        )
        .outerjoin(SourceRegistry, RawInfo.source_registry_id == SourceRegistry.id)
        .where(*base_filter)
        .where(brand_expr.isnot(None))
        .where(brand_expr != "")
        .group_by(brand_expr)
        .order_by(desc("count"))
    )
    brand_rows = (await db.execute(brand_query)).all()
    brands = [
        {"value": r[0], "label": r[0], "count": r[1]}
        for r in brand_rows
    ]

    # 功能方向分布
    cat_query = (
        select(
            category_expr.label("category"),
            func.count(RawInfo.id).label("count"),
        )
        .outerjoin(SourceRegistry, RawInfo.source_registry_id == SourceRegistry.id)
        .where(*base_filter)
        .where(category_expr.isnot(None))
        .where(category_expr != "")
        .group_by(category_expr)
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
            SourceAccount.display_name.label("source_account_name"),
        )
        .outerjoin(SourceRegistry, RawInfo.source_registry_id == SourceRegistry.id)
        .outerjoin(SourceAccount, RawInfo.source_account_id == SourceAccount.id)
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
            "items": [item for row in rows if not _is_frontend_noise(item := _serialize_row(row))],
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": (total + page_size - 1) // page_size,
        },
    }


# ── GET /commercial/groups ────────────────────────────────────

@router.get("/groups", response_model=dict)
async def get_commercial_groups(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    brand: Optional[str] = Query(None, description="按甲方筛选"),
    category: Optional[str] = Query(None, description="按功能方向筛选"),
    level: Optional[str] = Query(None, description="suspected / likely"),
    keyword: Optional[str] = Query(None),
    days: int = Query(10, ge=1, le=180, description="最近 N 天"),
) -> Any:
    """品牌聚合：按品牌/产品聚合投放账号、时间、链接和主体信息。"""
    filters = _wechat_commercial_filters(level=level, brand=brand, category=category, keyword=keyword)

    from datetime import datetime, timedelta
    cutoff = datetime.utcnow() - timedelta(days=days)
    filters.append(RawInfo.published_at >= cutoff)

    query = (
        select(
            RawInfo,
            SourceRegistry.name.label("source_name"),
            SourceAccount.display_name.label("source_account_name"),
        )
        .outerjoin(SourceRegistry, RawInfo.source_registry_id == SourceRegistry.id)
        .outerjoin(SourceAccount, RawInfo.source_account_id == SourceAccount.id)
        .where(*filters)
        .order_by(desc(RawInfo.published_at).nulls_last(), desc(RawInfo.scraped_at).nulls_last())
        .limit(800)
    )
    rows = (await db.execute(query)).all()

    grouped: Dict[str, dict] = {}
    for row in rows:
        item = _serialize_row(row)
        if _is_frontend_noise(item):
            continue
        key, display_name, product = _commercial_subject(item)
        group = grouped.setdefault(key, {
            "brand": display_name,
            "company_brand": item.get("commercial_brand") or "",
            "category": item.get("commercial_category") or "其他",
            "product": product,
            "count": 0,
            "accounts": [],
            "first_time": None,
            "last_time": None,
            "advantages": [],
            "items": [],
        })
        group["count"] += 1
        account = item.get("source_account_name") or item.get("author") or ""
        if account and account not in group["accounts"]:
            group["accounts"].append(account)
        t = _time_value(item)
        if t:
            group["first_time"] = min([x for x in [group["first_time"], t] if x])
            group["last_time"] = max([x for x in [group["last_time"], t] if x])
        if item.get("product") and not group.get("product"):
            group["product"] = item["product"]
        if item.get("commercial_category") and group.get("category") == "其他":
            group["category"] = item["commercial_category"]
        for adv in item.get("advantages") or []:
            if adv and adv not in group["advantages"]:
                group["advantages"].append(adv)
            if len(group["advantages"]) >= 5:
                break
        group["items"].append(item)

    groups = sorted(grouped.values(), key=lambda g: (g["count"], g.get("last_time") or ""), reverse=True)

    return {
        "code": 200,
        "message": "获取潜在商单品牌聚合成功",
        "data": {
            "groups": groups,
            "total": sum(g["count"] for g in groups),
            "brand_count": len(groups),
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
