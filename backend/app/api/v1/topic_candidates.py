"""候选选题 API。

提供候选选题列表、每日清单等接口。
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
from app.models.topic_candidate import TopicCandidate, PersonaReview, CandidateScore
from app.models.daily_topic_list import DailyTopicList
from app.models.info_cluster import InfoCluster
from app.services.ranking_service import generate_daily_list
from app.services.topic_mining.agent_a_deriver import derive_candidates
from app.services.topic_mining.agent_b_scorer import score_candidates
from app.services.topic_mining.schemas import InfoClusterInput, AgentBInput
from app.services.preprocess.rules import is_ai_related

router = APIRouter()


import asyncio

@router.post("/mine", response_model=dict)
async def trigger_mining(
    body: dict = {},
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    """触发选题挖掘任务。

    body 接受两种调用方式：
    - {"cluster_id": 18}                 → 挖指定簇（前端"立即挖掘"按钮）
    - {"limit": 3, "min_heat_score": 4}  → 批量挖未挖掘的热门簇
    """
    cluster_id = body.get("cluster_id")
    if cluster_id is not None:
        return await _mine_one(db, int(cluster_id))

    limit = int(body.get("limit", 3))
    min_heat = float(body.get("min_heat_score", 0))
    result = await _run_mining_batch(db, limit, min_heat)
    return {"code": 200, "message": "挖掘完成", "data": result}


async def _mine_one(db: AsyncSession, cluster_id: int) -> dict:
    """挖单个指定簇。失败时抛 HTTPException 让前端能看到具体原因。"""
    cluster = (await db.execute(
        select(InfoCluster).where(InfoCluster.id == cluster_id)
    )).scalar_one_or_none()

    if not cluster:
        raise HTTPException(status_code=404, detail=f"话题 {cluster_id} 不存在")

    if cluster.mined:
        return {"code": 200, "message": "已挖掘过", "data": {"cluster_id": cluster_id, "skipped": True}}

    if not cluster.info_type:
        raise HTTPException(
            status_code=400,
            detail="该话题还未完成预处理（缺 info_type），请等预处理跑完再挖掘"
        )

    if not is_ai_related(cluster.core_title, cluster.summary or ""):
        raise HTTPException(
            status_code=400,
            detail="该话题与 AI 无关，跳过挖掘"
        )

    try:
        stats = await _mine_cluster_inner(db, cluster)
        await db.commit()
        return {"code": 200, "message": "挖掘完成", "data": {"cluster_id": cluster_id, **stats}}
    except Exception as e:
        await db.rollback()
        import logging
        logging.getLogger(__name__).exception(f"挖掘 cluster {cluster_id} 失败")
        raise HTTPException(status_code=500, detail=f"挖掘失败: {type(e).__name__}: {str(e)[:200]}")


async def _run_mining_batch(db: AsyncSession, limit: int, min_heat_score: float) -> dict:
    """批量挖未挖掘的热门簇（保留旧行为，给定时任务用）。"""
    clusters = (await db.execute(
        select(InfoCluster).where(
            InfoCluster.mined.is_(False),
            InfoCluster.info_type.is_not(None),
            InfoCluster.heat_score >= min_heat_score,
        ).order_by(InfoCluster.heat_score.desc()).limit(limit * 3)  # 多取一些，过滤后可能不够
    )).scalars().all()

    # 过滤非 AI 内容
    clusters = [c for c in clusters if is_ai_related(c.core_title, c.summary or "")][:limit]

    if not clusters:
        return {"mined": 0, "message": "没有待挖掘的话题"}

    mined = 0
    total_candidates = 0
    errors = []
    for cluster in clusters:
        try:
            stats = await _mine_cluster_inner(db, cluster)
            await db.commit()
            mined += 1
            total_candidates += stats["total_candidates"]
        except Exception as e:
            await db.rollback()
            errors.append({"cluster_id": cluster.id, "error": f"{type(e).__name__}: {str(e)[:120]}"})

    return {"mined": mined, "total_candidates": total_candidates, "errors": errors}


async def _mine_cluster_inner(db: AsyncSession, cluster: InfoCluster) -> dict:
    """挖单个簇的核心逻辑：Agent A → Agent B → 写库（不 commit，调用方决定）。"""
    info_input = InfoClusterInput(
        cluster_id=cluster.id,
        core_title=cluster.core_title,
        summary=cluster.summary,
        info_type=cluster.info_type or "资讯型",
        direction=cluster.direction,
        elements=cluster.elements or {},
        freshness=cluster.freshness,
        heat_score=cluster.heat_score or 0.0,
        low_fan_hit=cluster.low_fan_hit or False,
        source_urls=cluster.source_urls or [],
    )
    candidates_a = await derive_candidates(info_input)
    b_input = AgentBInput(
        cluster_id=cluster.id,
        core_title=cluster.core_title,
        info_type=cluster.info_type or "资讯型",
        freshness=cluster.freshness,
        candidates=candidates_a,
    )
    result_b = await score_candidates(b_input)

    total_candidates = 0
    for scored in result_b.candidates:
        tc = TopicCandidate(
            info_cluster_id=cluster.id,
            title=scored.title,
            direction=scored.direction,
            routine=scored.routine,
            dimension_combo=scored.dimension_combo,
            value_promise=scored.value_promise,
            angle_note=scored.angle_note,
            persona_divergence=scored.persona_divergence,
            persona_divergence_flag=scored.persona_divergence_flag,
            veto_passed=scored.veto_passed,
            veto_reasons=scored.veto_reasons,
            business_sensitive=scored.business_sensitive,
            weighted_score=scored.weighted_score,
            verdict=scored.verdict,
        )
        db.add(tc)
        await db.flush()   # ← 关键修复：必须 await，否则 tc.id 还是 None

        for pr in scored.persona_reviews:
            db.add(PersonaReview(
                candidate_id=tc.id,
                persona=pr.persona,
                score=pr.score,
                rationale=pr.rationale,
            ))
        db.add(CandidateScore(
            candidate_id=tc.id,
            pain_point=scored.pain_point.score,
            value_density=scored.value_density.score,
            propagation=scored.propagation.score,
            differentiation=scored.differentiation.score,
            freshness=scored.freshness.score,
            audience_fit=scored.audience_fit.score,
            evidence={
                "pain_point": scored.pain_point.evidence,
                "value_density": scored.value_density.evidence,
                "propagation": scored.propagation.evidence,
                "differentiation": scored.differentiation.evidence,
                "freshness": scored.freshness.evidence,
                "audience_fit": scored.audience_fit.evidence,
            },
        ))
        total_candidates += 1

    cluster.mined = True
    return {"total_candidates": total_candidates, **result_b.stats}


@router.get("", response_model=dict)
async def get_topic_candidates(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    verdict: Optional[str] = Query(None),
    direction: Optional[str] = Query(None),
    min_score: Optional[float] = Query(None, ge=0, le=10),
    keyword: Optional[str] = Query(None),
    sort_by: str = Query("weighted_score"),
    sort_order: str = Query("desc"),
) -> Any:
    skip = (page - 1) * page_size

    # 构建查询
    query = select(TopicCandidate).options(
        joinedload(TopicCandidate.persona_reviews),
        joinedload(TopicCandidate.score),
    )

    # 筛选
    if verdict:
        query = query.where(TopicCandidate.verdict == verdict)
    if direction:
        query = query.where(TopicCandidate.direction == direction)
    if min_score is not None:
        query = query.where(TopicCandidate.weighted_score >= min_score)
    if keyword:
        query = query.where(TopicCandidate.title.ilike(f"%{keyword}%"))

    # 总数
    count_query = select(func.count(TopicCandidate.id))
    if verdict:
        count_query = count_query.where(TopicCandidate.verdict == verdict)
    if direction:
        count_query = count_query.where(TopicCandidate.direction == direction)
    if min_score is not None:
        count_query = count_query.where(TopicCandidate.weighted_score >= min_score)
    if keyword:
        count_query = count_query.where(TopicCandidate.title.ilike(f"%{keyword}%"))
    total_result = await db.execute(count_query)
    total = total_result.scalar()

    # 排序
    order_col = getattr(TopicCandidate, sort_by, TopicCandidate.weighted_score)
    if sort_order == "desc":
        query = query.order_by(desc(order_col))
    else:
        query = query.order_by(order_col)

    query = query.offset(skip).limit(page_size)
    result = await db.execute(query)
    candidates = result.scalars().unique().all()

    return {
        "code": 200,
        "message": "获取候选选题成功",
        "data": {
            "items": [_candidate_to_dict(c) for c in candidates],
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": (total + page_size - 1) // page_size,
        },
    }


@router.get("/stats/overview", response_model=dict)
async def get_stats_overview(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    total = (await db.execute(select(func.count(TopicCandidate.id)))).scalar()
    selected = (await db.execute(
        select(func.count(TopicCandidate.id)).where(TopicCandidate.verdict == "selected")
    )).scalar()
    backup = (await db.execute(
        select(func.count(TopicCandidate.id)).where(TopicCandidate.verdict == "backup")
    )).scalar()
    rejected = (await db.execute(
        select(func.count(TopicCandidate.id)).where(TopicCandidate.verdict == "rejected")
    )).scalar()
    vetoed = (await db.execute(
        select(func.count(TopicCandidate.id)).where(TopicCandidate.verdict == "vetoed")
    )).scalar()

    direction_result = await db.execute(
        select(TopicCandidate.direction, func.count(TopicCandidate.id)).group_by(TopicCandidate.direction)
    )
    direction_stats = {d: c for d, c in direction_result.all()}

    return {
        "code": 200,
        "message": "获取统计成功",
        "data": {
            "total": total or 0,
            "selected": selected or 0,
            "backup": backup or 0,
            "rejected": rejected or 0,
            "vetoed": vetoed or 0,
            "by_direction": direction_stats,
        },
    }


@router.get("/daily-list/{list_date}", response_model=dict)
async def get_daily_list(
    list_date: date,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    result = await db.execute(
        select(DailyTopicList).where(DailyTopicList.list_date == list_date)
    )
    daily_list = result.scalar_one_or_none()

    if not daily_list:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="该日期暂无选题清单")

    return {
        "code": 200,
        "message": "获取每日清单成功",
        "data": {
            "id": daily_list.id,
            "list_date": str(daily_list.list_date),
            "top_n": daily_list.top_n,
            "items": daily_list.items,
            "direction_distribution": daily_list.direction_distribution,
            "notes": daily_list.notes,
        },
    }


@router.post("/daily-list/generate", response_model=dict)
async def trigger_generate_daily_list(
    body: dict = {},
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    try:
        target_date_str = body.get("target_date")
        target_date = date.fromisoformat(target_date_str) if target_date_str else None
        top_n = body.get("top_n", 10)
        result = generate_daily_list(target_date=target_date, top_n=top_n)
        return {"code": 200, "message": "每日清单生成成功", "data": result}
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get("/{candidate_id}", response_model=dict)
async def get_topic_candidate(
    candidate_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    result = await db.execute(
        select(TopicCandidate)
        .options(
            joinedload(TopicCandidate.persona_reviews),
            joinedload(TopicCandidate.score),
            joinedload(TopicCandidate.info_cluster),
        )
        .where(TopicCandidate.id == candidate_id)
    )
    candidate = result.unique().scalar_one_or_none()

    if not candidate:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="候选选题不存在")

    data = _candidate_to_dict(candidate)
    if candidate.info_cluster:
        data["cluster"] = {
            "id": candidate.info_cluster.id,
            "core_title": candidate.info_cluster.core_title,
            "info_type": candidate.info_cluster.info_type,
        }

    return {"code": 200, "message": "获取候选选题详情成功", "data": data}


def _candidate_to_dict(c: TopicCandidate) -> dict:
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

    return {
        "id": c.id,
        "info_cluster_id": c.info_cluster_id,
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
        "weighted_score": c.weighted_score,
        "verdict": c.verdict,
        "persona_reviews": persona_reviews,
        "score": score_data,
        "created_at": c.created_at.isoformat() if c.created_at else None,
    }
