"""Layer 3 一次性清理：用 ai_centroid 语义过滤现有 raw_info。

放在独立模块是因为这是"补救"操作，不是日常流程（日常流程会在 pipeline 里直接拦截）。
"""

import logging
from typing import Dict

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.info_cluster import InfoCluster
from app.models.raw_info import RawInfo, RAW_STATE_CLUSTERED, RAW_STATE_SKIPPED
from app.services.preprocess.ai_centroid import cosine_distance, get_ai_centroid
from app.services.preprocess.cleanup import cleanup_polluted_data

logger = logging.getLogger(__name__)


async def cleanup_by_semantic_filter(
    db: AsyncSession,
    threshold: float = 0.55,
) -> Dict[str, int]:
    """对 clustered raw_info 跑语义过滤，把距离 >= threshold 的标 SKIPPED。"""
    centroid = await get_ai_centroid()

    raws = (await db.execute(
        select(RawInfo).where(
            RawInfo.state == RAW_STATE_CLUSTERED,
            RawInfo.embedding.is_not(None),
        )
    )).scalars().all()

    skipped = 0
    for r in raws:
        emb = list(r.embedding)
        dist = cosine_distance(emb, centroid)
        if dist >= threshold:
            r.state = RAW_STATE_SKIPPED
            r.info_cluster_id = None
            skipped += 1

    await db.flush()

    # 复用 Layer 2 的清理逻辑去刷 source_count 和删空 cluster
    rest_stats = await cleanup_polluted_data(db)

    return {
        "skipped_by_semantic_filter": skipped,
        **{k: v for k, v in rest_stats.items() if k not in ("skipped_by_disabled_source", "skipped_by_keyword_filter")},
    }
