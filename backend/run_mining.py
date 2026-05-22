"""批量运行选题挖掘任务。"""

import asyncio
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.db.session import SessionLocal
from app.models.info_cluster import InfoCluster
from app.models.topic_candidate import TopicCandidate, PersonaReview, CandidateScore
from app.services.topic_mining.agent_a_deriver import derive_candidates
from app.services.topic_mining.agent_b_scorer import score_candidates
from app.services.topic_mining.schemas import InfoClusterInput, AgentBInput


def cluster_to_input(cluster):
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


async def mine_one(db, cluster):
    info_input = cluster_to_input(cluster)
    print(f"  Agent A: {cluster.core_title[:40]}...")

    candidates_a = await derive_candidates(info_input)
    print(f"    衍生 {len(candidates_a)} 个候选")

    b_input = AgentBInput(
        cluster_id=cluster.id,
        core_title=cluster.core_title,
        info_type=cluster.info_type or "资讯型",
        freshness=cluster.freshness,
        candidates=candidates_a,
    )
    result_b = await score_candidates(b_input)

    for scored in result_b.candidates:
        candidate = TopicCandidate(
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
            weighted_score=scored.weighted_score,
            verdict=scored.verdict,
        )
        db.add(candidate)
        db.flush()

        for pr in scored.persona_reviews:
            db.add(PersonaReview(
                candidate_id=candidate.id,
                persona=pr.persona,
                score=pr.score,
                rationale=pr.rationale,
            ))

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

    cluster.mined = True
    db.commit()
    print(f"    入选 {result_b.stats.get('selected', 0)}, 备选 {result_b.stats.get('backup', 0)}, 淘汰 {result_b.stats.get('rejected', 0)}")
    return result_b


async def main():
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else 3
    db = SessionLocal()

    clusters = db.query(InfoCluster).filter(InfoCluster.mined == False).limit(limit).all()
    if not clusters:
        print("没有未挖掘的 InfoCluster")
        return

    print(f"开始挖掘 {len(clusters)} 条 InfoCluster\n")
    for i, cluster in enumerate(clusters):
        print(f"[{i+1}/{len(clusters)}] {cluster.core_title[:50]}")
        try:
            await mine_one(db, cluster)
        except Exception as e:
            print(f"    失败: {e}")
            db.rollback()

    total = db.query(TopicCandidate).count()
    print(f"\n完成。当前共有 {total} 个候选选题")
    db.close()


if __name__ == "__main__":
    asyncio.run(main())
