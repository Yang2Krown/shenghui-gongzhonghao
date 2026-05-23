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
from app.services.preprocess.rules import MAX_CONTENT_AGE_DAYS
from app.models.info_cluster import INFO_TYPE_WEIGHT

router = APIRouter()


@router.get("", response_model=dict)
async def get_topic_clusters(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    info_type: Optional[str] = Query(None),
    direction: Optional[str] = Query(None),
    mined: Optional[bool] = Query(None),
    freshness: Optional[str] = Query(None),
    keyword: Optional[str] = Query(None),
    sort_by: str = Query("display_score", description="display_score（按公众号价值加权）/ heat_score / created_at / source_count"),
    sort_order: str = Query("desc"),
) -> Any:
    # 构建基础查询：
    # - 默认过滤掉超过 90 天的老话题（保留 published_at IS NULL 的）
    # - 默认只取 is_ai_relevant=True（预处理时打的标）—— 避免每次请求都把全表拉到内存过滤
    cutoff = datetime.utcnow() - timedelta(days=MAX_CONTENT_AGE_DAYS)
    from sqlalchemy import or_
    query = select(InfoCluster).where(
        InfoCluster.is_ai_relevant.is_(True),
        or_(InfoCluster.published_at.is_(None), InfoCluster.published_at >= cutoff),
    )
    if info_type:
        query = query.where(InfoCluster.info_type == info_type)
    if direction:
        query = query.where(InfoCluster.direction == direction)
    if mined is not None:
        query = query.where(InfoCluster.mined == mined)
    if freshness:
        query = query.where(InfoCluster.freshness == freshness)
    if keyword:
        query = query.where(InfoCluster.core_title.ilike(f"%{keyword}%"))

    # 排序：display_score = heat_score × info_type_weight（公众号创作价值加权）
    # 在 SQL 层用 CASE 表达式，避免拉全表到内存排序
    from sqlalchemy import case
    weight_case = case(
        {k: v for k, v in INFO_TYPE_WEIGHT.items()},
        value=InfoCluster.info_type,
        else_=0.7,  # 未知类型默认中等权重
    )
    display_score_expr = (InfoCluster.heat_score * weight_case).label("display_score")

    if sort_by == "display_score":
        order_col = display_score_expr
    else:
        order_col = getattr(InfoCluster, sort_by, InfoCluster.heat_score)
    if sort_order == "desc":
        query = query.order_by(desc(order_col))
    else:
        query = query.order_by(order_col)

    # 总数（DB 层 count，不再把全表拉内存）
    count_q = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_q)).scalar() or 0

    # 当前页（SQL 层 LIMIT/OFFSET）
    page_query = query.offset((page - 1) * page_size).limit(page_size)
    page_clusters = (await db.execute(page_query)).scalars().all()

    # 批量查询每个 cluster 的候选选题数
    cluster_ids = [c.id for c in page_clusters]
    candidate_counts = {}
    if cluster_ids:
        count_result = await db.execute(
            select(
                TopicCandidate.info_cluster_id,
                func.count(TopicCandidate.id)
            )
            .where(TopicCandidate.info_cluster_id.in_(cluster_ids))
            .group_by(TopicCandidate.info_cluster_id)
        )
        candidate_counts = {row[0]: row[1] for row in count_result.all()}

    items = []
    for c in page_clusters:
        weight = INFO_TYPE_WEIGHT.get(c.info_type, 0.7)
        display_score = round((c.heat_score or 0) * weight, 2)
        items.append({
            "id": c.id,
            "core_title": c.core_title,
            "core_title_zh": c.core_title_zh,
            "summary": c.summary,
            "summary_zh": c.summary_zh,
            "info_type": c.info_type,
            "display_score": display_score,
            "direction": c.direction,
            "source_urls": c.source_urls or [],
            "source_count": c.source_count or len(c.source_urls or []),
            "freshness": c.freshness,
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
            "summary": cluster.summary,
            "summary_zh": cluster.summary_zh,
            "info_type": cluster.info_type,
            "direction": cluster.direction,
            "elements": cluster.elements,
            "source_urls": cluster.source_urls or [],
            "source_count": cluster.source_count or len(cluster.source_urls or []),
            "raw_infos": raw_infos_list,                 # 新增：完整原文卡片列表
            "freshness": cluster.freshness,
            "heat_score": cluster.heat_score,
            "low_fan_hit": cluster.low_fan_hit,
            "mined": cluster.mined,
            "created_at": cluster.created_at.isoformat() if cluster.created_at else None,
            "candidates": candidate_list,
        },
    }
