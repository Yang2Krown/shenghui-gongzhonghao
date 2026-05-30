"""选题挖掘 Celery 任务。

编排：Agent A（衍生）→ Agent B（评分）→ 落库。
"""

import logging
from typing import Optional

from sqlalchemy import select

from app.core.celery_app import celery_app
from app.db.session import SessionLocal
from app.models.info_cluster import InfoCluster
from app.models.topic_candidate import TopicCandidate, PersonaReview, CandidateScore
from app.services.topic_mining.agent_a_deriver import derive_candidates
from app.services.topic_mining.agent_b_scorer import score_candidates
from app.services.topic_mining.schemas import InfoClusterInput, AgentBInput

logger = logging.getLogger(__name__)


def _cluster_to_input(cluster: InfoCluster) -> InfoClusterInput:
    """将 InfoCluster ORM 对象转为 Agent A 的输入 schema。"""
    return InfoClusterInput(
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


@celery_app.task(bind=True, name="mining.mine_cluster", max_retries=2, default_retry_delay=30)
def mine_cluster(self, cluster_id: int) -> dict:
    """对单个 InfoCluster 执行选题挖掘（Agent A → Agent B → 落库）。

    Args:
        cluster_id: InfoCluster 的 ID

    Returns:
        {
            "cluster_id": int,
            "candidates_count": int,
            "selected": int,
            "backup": int,
            "rejected": int,
            "vetoed": int,
        }
    """
    import asyncio

    db = SessionLocal()
    try:
        cluster = db.query(InfoCluster).filter(InfoCluster.id == cluster_id).first()
        if not cluster:
            logger.error(f"InfoCluster {cluster_id} 不存在")
            return {"error": f"cluster {cluster_id} not found"}

        if cluster.mined:
            logger.info(f"InfoCluster {cluster_id} 已挖掘过，跳过")
            return {"cluster_id": cluster_id, "status": "already_mined"}

        # Step 1: Agent A 衍生
        info_input = _cluster_to_input(cluster)
        candidates_a = asyncio.run(derive_candidates(info_input))

        # Step 2: Agent B 评分
        b_input = AgentBInput(
            cluster_id=cluster_id,
            core_title=cluster.core_title,
            info_type=cluster.info_type or "资讯型",
            freshness=cluster.freshness,
            candidates=candidates_a,
        )
        result_b = asyncio.run(score_candidates(b_input))

        # Step 3: 落库
        for scored in result_b.candidates:
            candidate = TopicCandidate(
                info_cluster_id=cluster_id,
                title=scored.title,
                summary=scored.summary,
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
            db.add(candidate)
            db.flush()

            # Persona 评议
            for pr in scored.persona_reviews:
                db.add(PersonaReview(
                    candidate_id=candidate.id,
                    persona=pr.persona,
                    score=pr.score,
                    rationale=pr.rationale,
                ))

            # 6 维度评分
            db.add(CandidateScore(
                candidate_id=candidate.id,
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

        # 标记已挖掘
        cluster.mined = True
        db.commit()

        logger.info(f"InfoCluster {cluster_id} 挖掘完成: {result_b.stats}")
        return {"cluster_id": cluster_id, **result_b.stats}

    except Exception as exc:
        db.rollback()
        logger.exception(f"InfoCluster {cluster_id} 挖掘失败: {exc}")
        raise self.retry(exc=exc)
    finally:
        db.close()


@celery_app.task(bind=True, name="mining.run_batch")
def run_batch(self, limit: int = 10, min_heat_score: float = 0.0) -> dict:
    """批量挖掘：拉 mined=False 的 InfoCluster，按 heat_score 倒序，逐个调 mine_cluster。

    Args:
        limit: 单次最多挖几个簇（控成本）
        min_heat_score: 热度门槛，过低的簇不挖

    Returns:
        {"dispatched": int, "stats": [...]}
    """
    db = SessionLocal()
    try:
        stmt = (
            select(InfoCluster.id)
            .where(
                InfoCluster.mined.is_(False),
                InfoCluster.info_type.is_not(None),
                InfoCluster.heat_score >= min_heat_score,
            )
            .order_by(InfoCluster.heat_score.desc())
            .limit(limit)
        )
        cluster_ids = [r[0] for r in db.execute(stmt).all()]
    finally:
        db.close()

    if not cluster_ids:
        logger.info("mining.run_batch: 没有待挖掘的 InfoCluster")
        return {"dispatched": 0, "stats": []}

    # 顺序串行（避免 LLM API 限速；要并行可改 group/chord）
    stats = []
    for cid in cluster_ids:
        try:
            result = mine_cluster.run(cid)
            stats.append(result)
        except Exception as e:
            logger.error(f"mine_cluster {cid} 失败: {e}")
            stats.append({"cluster_id": cid, "error": str(e)})

    logger.info(f"mining.run_batch 完成: dispatched={len(cluster_ids)}")
    return {"dispatched": len(cluster_ids), "stats": stats}
