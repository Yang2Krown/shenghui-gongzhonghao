"""数据清理工具：把"不该进来"的 raw_info 标 SKIPPED，清理空 cluster。

3 步：
1. 标记：来自 enabled=false 源的 raw_info → SKIPPED
2. 标记：is_ai_related() 判定为非 AI 的 raw_info → SKIPPED
3. 重算每个 cluster 的实际 source_count（统计该 cluster 下非 SKIPPED 的 raw_info），
   source_count=0 的 cluster 直接删除。
"""

import logging
from typing import Dict

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.info_cluster import InfoCluster
from app.models.raw_info import RawInfo, RAW_STATE_SKIPPED, RAW_STATE_CLUSTERED
from app.models.source_registry import SourceRegistry
from app.services.preprocess.rules import is_ai_related

logger = logging.getLogger(__name__)


async def cleanup_polluted_data(db: AsyncSession) -> Dict[str, int]:
    """主入口。返回清理统计。"""
    stats: Dict[str, int] = {}

    # ---- Step 1：来自已禁用源的 raw_info → SKIPPED ----
    disabled_source_ids = [
        sid for (sid,) in (await db.execute(
            select(SourceRegistry.id).where(SourceRegistry.enabled.is_(False))
        )).all()
    ]
    if disabled_source_ids:
        result = await db.execute(
            update(RawInfo)
            .where(
                RawInfo.source_registry_id.in_(disabled_source_ids),
                RawInfo.state != RAW_STATE_SKIPPED,
            )
            .values(state=RAW_STATE_SKIPPED, info_cluster_id=None)
        )
        stats["skipped_by_disabled_source"] = result.rowcount
        logger.info(f"Step 1: 禁用源 raw_info 标 SKIPPED: {result.rowcount}")
    else:
        stats["skipped_by_disabled_source"] = 0

    await db.flush()

    # ---- Step 2：is_ai_related = False 的 raw_info → SKIPPED ----
    # 只扫还在 clustered 状态的（已经 SKIPPED 的不重复扫）
    raws = (await db.execute(
        select(RawInfo).where(RawInfo.state == RAW_STATE_CLUSTERED)
    )).scalars().all()

    non_ai_count = 0
    for r in raws:
        if not is_ai_related(r.title or "", r.summary or ""):
            r.state = RAW_STATE_SKIPPED
            r.info_cluster_id = None
            non_ai_count += 1
    stats["skipped_by_keyword_filter"] = non_ai_count
    logger.info(f"Step 2: is_ai_related=False 的 raw_info 标 SKIPPED: {non_ai_count}")

    await db.flush()

    # ---- Step 3：重算每个 cluster 的真实 source_count，删空 cluster ----
    # 拉所有 cluster 和它们的 clustered raw_info 数
    rows = await db.execute(
        select(InfoCluster.id, func.count(RawInfo.id))
        .outerjoin(RawInfo, (RawInfo.info_cluster_id == InfoCluster.id) & (RawInfo.state == RAW_STATE_CLUSTERED))
        .group_by(InfoCluster.id)
    )
    deleted_clusters = 0
    updated_clusters = 0

    for cluster_id, actual_count in rows.all():
        cluster = await db.get(InfoCluster, cluster_id)
        if not cluster:
            continue

        if actual_count == 0:
            await db.delete(cluster)
            deleted_clusters += 1
        elif cluster.source_count != actual_count:
            cluster.source_count = actual_count
            # 重新生成 source_urls 列表
            urls = [
                u for (u,) in (await db.execute(
                    select(RawInfo.url).where(
                        RawInfo.info_cluster_id == cluster_id,
                        RawInfo.state == RAW_STATE_CLUSTERED,
                    )
                )).all()
            ]
            cluster.source_urls = urls
            updated_clusters += 1

    stats["deleted_clusters"] = deleted_clusters
    stats["updated_clusters"] = updated_clusters
    logger.info(f"Step 3: 删空 cluster: {deleted_clusters}，更新 source_count: {updated_clusters}")

    await db.commit()
    return stats
