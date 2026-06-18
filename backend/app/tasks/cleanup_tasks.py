"""信息库定期清理 Celery 任务。

只删「过期且没人用过」的信息：effective_date 早于 N 天 且
  - 没有任何 TopicCandidate 引用该簇（没人挖掘过）
  - 没有任何 Creation 引用该簇（没人基于它创作过）
这样保留所有有下游产出的旧资讯，避免误删用户成品（大纲/正文挂在 candidate 上）。
"""

import asyncio
import logging
from datetime import timedelta

from celery import shared_task
from sqlalchemy import select, func, delete, and_

from app.db.session import AsyncSessionLocal, engine
from app.core.timezone import utcnow

logger = logging.getLogger(__name__)

CLEANUP_AGE_DAYS = 14


async def _purge(days: int) -> dict:
    from app.models.info_cluster import InfoCluster
    from app.models.raw_info import RawInfo
    from app.models.topic_candidate import TopicCandidate
    from app.models.creation import Creation

    cutoff = utcnow() - timedelta(days=days)
    effective = func.coalesce(InfoCluster.published_at, InfoCluster.created_at)
    has_candidate = (
        select(TopicCandidate.id)
        .where(TopicCandidate.info_cluster_id == InfoCluster.id)
        .exists()
    )
    has_creation = (
        select(Creation.id).where(Creation.cluster_id == InfoCluster.id).exists()
    )
    # 「过期 + 没人用过」的簇。条件只依赖 cluster/candidate/creation，删 raw 不影响它，
    # 所以可以先删 raw 再删簇，两条语句用同一份子查询。
    stale_cond = and_(effective < cutoff, ~has_candidate, ~has_creation)
    stale_ids = select(InfoCluster.id).where(stale_cond)

    try:
        async with AsyncSessionLocal() as db:
            raw_del = (
                await db.execute(
                    delete(RawInfo).where(RawInfo.info_cluster_id.in_(stale_ids))
                )
            ).rowcount
            clu_del = (
                await db.execute(delete(InfoCluster).where(InfoCluster.id.in_(stale_ids)))
            ).rowcount
            await db.commit()
            return {"deleted_clusters": clu_del or 0, "deleted_raw": raw_del or 0}
    finally:
        await engine.dispose()


@shared_task(bind=True, name="cleanup.purge_stale_clusters", max_retries=1)
def purge_stale_clusters(self, days: int = CLEANUP_AGE_DAYS) -> dict:
    """删除 days 天前、且没人挖掘/创作过的信息簇及其原文。"""
    try:
        result = asyncio.run(_purge(days))
        logger.info(f"信息库清理完成: {result}")
        return result
    except Exception as e:
        logger.exception(f"信息库清理失败: {e}")
        self.retry(exc=e, countdown=300)


def demo():
    """自检：构造 cutoff 条件可被 SQLAlchemy 编译（不连库）。"""
    from app.models.info_cluster import InfoCluster
    from app.models.topic_candidate import TopicCandidate

    cutoff = utcnow() - timedelta(days=CLEANUP_AGE_DAYS)
    effective = func.coalesce(InfoCluster.published_at, InfoCluster.created_at)
    has_candidate = (
        select(TopicCandidate.id)
        .where(TopicCandidate.info_cluster_id == InfoCluster.id)
        .exists()
    )
    cond = and_(effective < cutoff, ~has_candidate)
    compiled = str(select(InfoCluster.id).where(cond))
    assert "topic_candidates" in compiled and "coalesce" in compiled.lower()
    print("ok:", compiled[:80], "...")


if __name__ == "__main__":
    demo()
