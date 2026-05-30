"""预处理 Celery 任务：RawInfo → InfoCluster。"""

import asyncio
import logging
from typing import Any, Dict

from celery import shared_task

from app.db.session import AsyncSessionLocal, engine
from app.services.preprocess import preprocess_pipeline

logger = logging.getLogger(__name__)


async def _run(limit: int) -> Dict[str, Any]:
    try:
        async with AsyncSessionLocal() as db:
            return await preprocess_pipeline.run_batch(db, limit=limit)
    finally:
        await engine.dispose()


@shared_task(bind=True, name="preprocess.run_batch")
def run_batch_task(self, limit: int = 100):
    """批处理：拉一批 pending RawInfo → 聚类 → 富集 → 落库。"""
    try:
        result = asyncio.run(_run(limit))
        return result
    except Exception as e:
        logger.error(f"preprocess 失败: {e}")
        self.retry(exc=e, countdown=120, max_retries=2)


async def _rescore():
    """重新计算所有活跃 cluster 的 heat_score（让排序反映最新状态）。"""
    from datetime import timedelta
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload
    from app.models.info_cluster import InfoCluster
    from app.models.raw_info import RawInfo
    from app.services.preprocess.rules import compute_heat_score, compute_freshness, compute_low_fan_hit
    from app.core.timezone import utcnow

    async with AsyncSessionLocal() as db:
        cutoff = utcnow() - timedelta(days=30)
        clusters = (await db.execute(
            select(InfoCluster)
            .where(InfoCluster.is_ai_relevant.is_(True))
            .where(InfoCluster.created_at >= cutoff)
        )).scalars().all()

        updated = 0
        for cluster in clusters:
            raws = (await db.execute(
                select(RawInfo)
                .options(selectinload(RawInfo.source))
                .where(RawInfo.info_cluster_id == cluster.id)
            )).scalars().all()
            if not raws:
                continue

            engagements = [r.engagement or {} for r in raws]
            old_score = cluster.heat_score
            cluster.heat_score = compute_heat_score(
                engagements=engagements,
                source_count=cluster.source_count or len(raws),
            )
            # 更新 freshness
            cluster.freshness = compute_freshness(cluster.published_at, fallback_dt=cluster.created_at)
            # 回填低粉爆款标记（采信采集源的显式 low_fan 标记），让存量聚类也能亮角标
            cluster.low_fan_hit = compute_low_fan_hit(engagements)
            if cluster.heat_score != old_score:
                updated += 1

        await db.commit()
        logger.info(f"rescore 完成: checked={len(clusters)} updated={updated}")
        return {"checked": len(clusters), "updated": updated}


@shared_task(bind=True, name="preprocess.rescore")
def rescore_task(self):
    """定时重算活跃 cluster 的 heat_score。"""
    try:
        result = asyncio.run(_rescore())
        return result
    except Exception as e:
        logger.error(f"rescore 失败: {e}")
        self.retry(exc=e, countdown=60, max_retries=2)
