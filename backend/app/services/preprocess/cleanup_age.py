"""按时效清理：把超过 N 天的老 raw_info 标 SKIPPED，删除全是老内容的 cluster。"""

import logging
from datetime import datetime, timedelta
from app.core.timezone import utcnow
from typing import Dict

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.info_cluster import InfoCluster
from app.models.raw_info import RawInfo, RAW_STATE_CLUSTERED, RAW_STATE_SKIPPED
from app.services.preprocess.cleanup import cleanup_polluted_data
from app.services.preprocess.rules import MAX_CONTENT_AGE_DAYS

logger = logging.getLogger(__name__)


async def cleanup_by_age(db: AsyncSession, max_days: int = MAX_CONTENT_AGE_DAYS) -> Dict[str, int]:
    """把所有 published_at 早于 now - max_days 的 raw_info 标 SKIPPED + 删空簇。

    保留 published_at IS NULL 的（不知道时间但 scraped_at 是近期的，可能是新内容）。
    """
    cutoff = utcnow() - timedelta(days=max_days)

    # 标记 raw_info
    raws = (await db.execute(
        select(RawInfo).where(
            RawInfo.state == RAW_STATE_CLUSTERED,
            RawInfo.published_at.is_not(None),
            RawInfo.published_at < cutoff,
        )
    )).scalars().all()

    skipped = 0
    for r in raws:
        r.state = RAW_STATE_SKIPPED
        r.info_cluster_id = None
        skipped += 1

    await db.flush()

    # 同时也删除 cluster 自身 published_at 太老的（防止只有 NULL raw_info 漏过）
    old_clusters = (await db.execute(
        select(InfoCluster).where(
            InfoCluster.published_at.is_not(None),
            InfoCluster.published_at < cutoff,
        )
    )).scalars().all()
    cluster_skipped = 0
    for c in old_clusters:
        # 该 cluster 下所有 raw_info 解绑 + 标 SKIPPED
        raws_in_c = (await db.execute(
            select(RawInfo).where(RawInfo.info_cluster_id == c.id)
        )).scalars().all()
        for r in raws_in_c:
            r.state = RAW_STATE_SKIPPED
            r.info_cluster_id = None
            cluster_skipped += 1

    await db.flush()
    logger.info(f"cleanup_by_age: 标 SKIPPED {skipped + cluster_skipped} 条 raw_info")

    # 复用现有清理逻辑刷 source_count + 删空 cluster
    rest = await cleanup_polluted_data(db)

    return {
        "max_days": max_days,
        "cutoff": cutoff.isoformat(),
        "skipped_by_age": skipped + cluster_skipped,
        **{k: v for k, v in rest.items() if k.startswith("deleted") or k.startswith("updated")},
    }
