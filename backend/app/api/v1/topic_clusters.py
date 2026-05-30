"""话题库 API。

提供 InfoCluster 列表、详情（含候选选题）等接口。
"""

from datetime import date
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.core.security import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.models.info_cluster import InfoCluster
from app.models.raw_info import RawInfo
from app.models.source_registry import SourceRegistry
from app.models.topic_candidate import TopicCandidate
from datetime import datetime, timedelta
from app.core.timezone import utcnow
from app.services.preprocess.rules import MAX_CONTENT_AGE_DAYS, compute_freshness as _compute_freshness
from app.models.info_cluster import INFO_TYPE_WEIGHT

router = APIRouter()


_refresh_running = False


def _celery_available() -> bool:
    """检测 Celery broker (Redis) 是否可用。"""
    try:
        from app.core.celery_app import celery_app
        conn = celery_app.connection()
        conn.connect()
        conn.close()
        return True
    except Exception:
        return False


async def _do_refresh():
    """进程内后台执行 aihot 全量抓取 + 预处理（本地开发用）。"""
    global _refresh_running
    import logging
    log = logging.getLogger(__name__)
    try:
        from app.services.scraping.adapters.aihot_adapter import fetch_aihot
        from app.services.preprocess import preprocess_pipeline
        from app.db.session import AsyncSessionLocal

        async with AsyncSessionLocal() as db:
            result = await fetch_aihot(db, feed_key="all")
            log.info(f"手动抓取 aihot[all] 完成: {result}")

        async with AsyncSessionLocal() as db:
            pp_result = await preprocess_pipeline.run_batch(db, limit=500)
            log.info(f"手动预处理完成: {pp_result}")
    except Exception as e:
        log.error(f"手动刷新失败: {e}", exc_info=True)
    finally:
        _refresh_running = False


@router.post("/refresh", response_model=dict)
async def manual_refresh(
    current_user: User = Depends(get_current_user),
) -> Any:
    """手动触发抓取 + 预处理。有 Celery 走队列，否则进程内异步执行。"""
    import asyncio
    global _refresh_running

    if _celery_available():
        from app.tasks.scraper_tasks import fetch_aihot_task
        from app.tasks.preprocess_tasks import run_batch_task

        fetch_aihot_task.delay(feed_key="all")
        run_batch_task.apply_async(kwargs={"limit": 500}, countdown=120)

        return {
            "code": 200,
            "message": "已提交 AI HOT 全量抓取 + 预处理任务，请稍后刷新页面查看新数据",
            "data": {"mode": "celery"},
        }

    if _refresh_running:
        return {
            "code": 200,
            "message": "已有抓取任务在执行中，请稍后刷新页面查看",
            "data": {},
        }

    _refresh_running = True
    asyncio.create_task(_do_refresh())

    return {
        "code": 200,
        "message": "已开始抓取 + 预处理，请几分钟后刷新页面查看新数据",
        "data": {"mode": "async"},
    }


@router.get("", response_model=dict)
async def get_topic_clusters(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    page: int = Query(1, ge=1),
    page_size: int = Query(30, ge=1, le=200),
    info_type: Optional[str] = Query(None),
    direction: Optional[str] = Query(None),
    mined: Optional[bool] = Query(None),
    freshness: Optional[str] = Query(None),
    keyword: Optional[str] = Query(None),
    sort_by: str = Query("display_score", description="display_score / heat_score / created_at / source_count"),
    sort_order: str = Query("desc"),
    balanced: bool = Query(True, description="True=每类保底配额，False=纯分数排序"),
) -> Any:
    """话题库列表。

    balanced=True 时：每种 info_type 至少保留 min_per_type 条（按 display_score），
    剩余槽位从全局高分补。保证类型多样性，避免资讯型刷屏。
    """
    from sqlalchemy import or_, case, extract

    # 参数类型兜底（FastAPI Query 对象需取 .default 或显式转换）
    sort_by = str(sort_by) if sort_by else "display_score"
    sort_order = str(sort_order) if sort_order else "desc"
    mined = mined if isinstance(mined, bool) else None

    cutoff = utcnow() - timedelta(days=MAX_CONTENT_AGE_DAYS)
    base_filter = [
        InfoCluster.is_ai_relevant.is_(True),
        or_(InfoCluster.published_at.is_(None), InfoCluster.published_at >= cutoff),
    ]
    if info_type:
        base_filter.append(InfoCluster.info_type == info_type)
    if direction:
        base_filter.append(InfoCluster.direction == direction)
    if mined is not None:
        base_filter.append(InfoCluster.mined == mined)
    if freshness:
        now = utcnow()
        effective_dt = func.coalesce(InfoCluster.published_at, InfoCluster.created_at)
        if freshness == "24h":
            base_filter.append(effective_dt >= now - timedelta(hours=24))
        elif freshness == "7d":
            base_filter.append(effective_dt >= now - timedelta(days=7))
        elif freshness == "30d":
            base_filter.append(effective_dt >= now - timedelta(days=30))
        elif freshness == "expired":
            base_filter.append(or_(effective_dt.is_(None), effective_dt < now - timedelta(days=30)))
    if keyword:
        base_filter.append(
            or_(
                InfoCluster.core_title.ilike(f"%{keyword}%"),
                InfoCluster.latest_title.ilike(f"%{keyword}%"),
                InfoCluster.core_title_zh.ilike(f"%{keyword}%"),
            )
        )

    # display_score 表达式（与 SQL CASE 保持一致）
    weight_case = case(
        {k: v for k, v in INFO_TYPE_WEIGHT.items()},
        value=InfoCluster.info_type,
        else_=0.7,
    )
    effective_ts = func.coalesce(InfoCluster.published_at, InfoCluster.created_at)
    age_hours = extract("epoch", func.now() - effective_ts) / 3600.0
    freshness_boost = case(
        (age_hours < 24, 2.0),
        (age_hours < 24 * 7, 1.2),
        (age_hours < 24 * 30, 0.8),
        else_=0.4,
    )
    # 多源加成：被多篇报道提及的话题加分
    # 1篇=1.0, 2篇=1.15, 3篇=1.25, 5篇=1.4, 10篇=1.6, 20篇=1.8
    source_count_val = func.coalesce(InfoCluster.source_count, 1)
    source_multiplier = case(
        (source_count_val >= 20, 1.8),
        (source_count_val >= 10, 1.6),
        (source_count_val >= 5, 1.4),
        (source_count_val >= 3, 1.25),
        (source_count_val >= 2, 1.15),
        else_=1.0,
    )
    display_score_expr = (InfoCluster.heat_score * weight_case * freshness_boost * source_multiplier).label("display_score")

    if sort_by == "display_score":
        order_col = display_score_expr
    else:
        order_col = getattr(InfoCluster, sort_by, InfoCluster.heat_score)

    # ── balanced 模式：每类保底 + 全局高分补齐 ──
    _FRESHNESS_BOOST = {"24h": 2.0, "7d": 1.2, "30d": 0.8, "expired": 0.4}

    if balanced and not info_type:
        # min_per_type: 每类至少几条（第一页保底，后续页纯分数）
        min_per_type = 5 if page == 1 else 0

        # 1. 先拿总数
        count_q = select(func.count(InfoCluster.id)).where(*base_filter)
        total = (await db.execute(count_q)).scalar() or 0

        # 2. 按 info_type 分组取 top N
        selected_ids = set()
        type_counts = {}
        if min_per_type > 0:
            for t in ["资讯型", "实操案例型", "观点分享型", "教程型"]:
                q = (
                    select(InfoCluster.id)
                    .where(*base_filter, InfoCluster.info_type == t)
                    .order_by(desc(display_score_expr))
                    .limit(min_per_type)
                )
                ids = [row[0] for row in (await db.execute(q)).all()]
                selected_ids.update(ids)
                type_counts[t] = len(ids)

        # 3. 补齐剩余槽位：从全局高分里选没选过的
        remaining = page_size - len(selected_ids)
        if remaining > 0:
            fill_q = (
                select(InfoCluster.id)
                .where(*base_filter)
                .where(InfoCluster.id.notin_(selected_ids) if selected_ids else True)
                .order_by(desc(display_score_expr))
                .limit(remaining)
            )
            fill_ids = [row[0] for row in (await db.execute(fill_q)).all()]
            selected_ids.update(fill_ids)

        # 4. 拉完整对象，按 display_score 排序
        if not selected_ids:
            page_clusters = []
        else:
            fetch_q = (
                select(InfoCluster)
                .where(InfoCluster.id.in_(selected_ids))
                .order_by(desc(display_score_expr))
            )
            page_clusters = (await db.execute(fetch_q)).scalars().all()
    else:
        # 普通分页模式
        query = select(InfoCluster).where(*base_filter)
        if sort_by == "display_score":
            query = query.order_by(desc(display_score_expr))
        else:
            query = query.order_by(desc(order_col) if sort_order == "desc" else order_col)

        count_q = select(func.count(InfoCluster.id)).where(*base_filter)
        total = (await db.execute(count_q)).scalar() or 0
        page_query = query.offset((page - 1) * page_size).limit(page_size)
        page_clusters = (await db.execute(page_query)).scalars().all()

    # 批量查询候选选题数
    cluster_ids = [c.id for c in page_clusters]
    candidate_counts = {}
    if cluster_ids:
        count_result = await db.execute(
            select(TopicCandidate.info_cluster_id, func.count(TopicCandidate.id))
            .where(TopicCandidate.info_cluster_id.in_(cluster_ids))
            .group_by(TopicCandidate.info_cluster_id)
        )
        candidate_counts = {row[0]: row[1] for row in count_result.all()}

    items = []
    for c in page_clusters:
        weight = INFO_TYPE_WEIGHT.get(c.info_type, 0.7)
        live_freshness = _compute_freshness(c.published_at, fallback_dt=c.created_at)
        boost = _FRESHNESS_BOOST.get(live_freshness, 0.4)
        src_count = c.source_count or len(c.source_urls or []) or 1
        if src_count >= 20:
            src_mul = 1.8
        elif src_count >= 10:
            src_mul = 1.6
        elif src_count >= 5:
            src_mul = 1.4
        elif src_count >= 3:
            src_mul = 1.25
        elif src_count >= 2:
            src_mul = 1.15
        else:
            src_mul = 1.0
        display_score = round((c.heat_score or 0) * weight * boost * src_mul, 2)
        items.append({
            "id": c.id,
            "core_title": c.core_title,
            "core_title_zh": c.core_title_zh,
            "latest_title": c.latest_title,
            "summary": c.summary,
            "summary_zh": c.summary_zh,
            "info_type": c.info_type,
            "display_score": display_score,
            "direction": c.direction,
            "source_urls": c.source_urls or [],
            "source_count": c.source_count or len(c.source_urls or []),
            "freshness": live_freshness,
            "heat_score": c.heat_score,
            "low_fan_hit": c.low_fan_hit,
            "mined": c.mined,
            "candidate_count": candidate_counts.get(c.id, 0),
            "created_at": c.created_at.isoformat() if c.created_at else None,
        })

    return {
        "code": 200,
        "message": "获取话题库成功",
        "data": {
            "items": items,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": (total + page_size - 1) // page_size,
        },
    }


@router.get("/{cluster_id}", response_model=dict)
async def get_topic_cluster_detail(
    cluster_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    result = await db.execute(
        select(InfoCluster).where(InfoCluster.id == cluster_id)
    )
    cluster = result.scalar_one_or_none()

    if not cluster:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="话题不存在")

    # 查询关联的候选选题
    cand_result = await db.execute(
        select(TopicCandidate)
        .options(
            joinedload(TopicCandidate.persona_reviews),
            joinedload(TopicCandidate.score),
        )
        .where(TopicCandidate.info_cluster_id == cluster_id)
        .order_by(desc(TopicCandidate.weighted_score))
    )
    candidates = cand_result.scalars().unique().all()

    candidate_list = []
    for c in candidates:
        persona_reviews = [
            {"persona": pr.persona, "score": pr.score, "rationale": pr.rationale}
            for pr in c.persona_reviews
        ]
        score_data = None
        if c.score:
            score_data = {
                "pain_point": c.score.pain_point,
                "value_density": c.score.value_density,
                "propagation": c.score.propagation,
                "differentiation": c.score.differentiation,
                "freshness": c.score.freshness,
                "audience_fit": c.score.audience_fit,
                "evidence": c.score.evidence,
            }
        candidate_list.append({
            "id": c.id,
            "title": c.title,
            "summary": c.summary,
            "direction": c.direction,
            "routine": c.routine,
            "dimension_combo": c.dimension_combo,
            "value_promise": c.value_promise,
            "angle_note": c.angle_note,
            "persona_divergence": c.persona_divergence,
            "persona_divergence_flag": c.persona_divergence_flag,
            "veto_passed": c.veto_passed,
            "veto_reasons": c.veto_reasons,
            "business_sensitive": c.business_sensitive,
            "weighted_score": c.weighted_score,
            "verdict": c.verdict,
            "persona_reviews": persona_reviews,
            "score": score_data,
            "created_at": c.created_at.isoformat() if c.created_at else None,
        })

    # 拉关联的原文（带来源平台名）
    raw_result = await db.execute(
        select(RawInfo, SourceRegistry.name.label("source_name"), SourceRegistry.platform.label("source_platform"))
        .outerjoin(SourceRegistry, RawInfo.source_registry_id == SourceRegistry.id)
        .where(RawInfo.info_cluster_id == cluster_id)
        .order_by(RawInfo.published_at.desc().nulls_last())
    )
    raw_infos_list = []
    for row in raw_result.all():
        raw = row[0]
        raw_infos_list.append({
            "id": raw.id,
            "title": raw.title,
            "url": raw.url,
            "summary": (raw.summary or "")[:200] if raw.summary else None,
            "author": raw.author,
            "published_at": raw.published_at.isoformat() if raw.published_at else None,
            "source_name": row.source_name or "未知来源",
            "source_platform": row.source_platform or "",
        })

    return {
        "code": 200,
        "message": "获取话题详情成功",
        "data": {
            "id": cluster.id,
            "core_title": cluster.core_title,
            "core_title_zh": cluster.core_title_zh,
            "latest_title": cluster.latest_title,
            "summary": cluster.summary,
            "summary_zh": cluster.summary_zh,
            "info_type": cluster.info_type,
            "direction": cluster.direction,
            "elements": cluster.elements,
            "source_urls": cluster.source_urls or [],
            "source_count": cluster.source_count or len(cluster.source_urls or []),
            "raw_infos": raw_infos_list,
            "freshness": _compute_freshness(cluster.published_at, fallback_dt=cluster.created_at),
            "heat_score": cluster.heat_score,
            "low_fan_hit": cluster.low_fan_hit,
            "mined": cluster.mined,
            "created_at": cluster.created_at.isoformat() if cluster.created_at else None,
            "candidates": candidate_list,
        },
    }
