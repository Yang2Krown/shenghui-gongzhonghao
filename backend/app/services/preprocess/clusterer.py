"""聚类：基于 pgvector cosine 相似度，给 RawInfo 找/建 InfoCluster。

策略：
1. 对每个待聚类 RawInfo（已有 embedding），用 cosine distance 查询近 7 天内的 InfoCluster
2. 若最近距离 < THRESHOLD（默认 0.22 ≈ 相似度 0.78），并入该簇
3. 否则新建簇（用此 RawInfo 作为种子）
4. 并入后增量更新 centroid（流式均值）
"""

import logging
from datetime import datetime, timedelta
from typing import List, Optional

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.info_cluster import InfoCluster
from app.models.raw_info import RawInfo, RAW_STATE_CLUSTERED

logger = logging.getLogger(__name__)


# cosine distance 阈值：< 此值视为同主题。0.22 是经验值，可调
DEFAULT_SIM_THRESHOLD = 0.22

# 只在最近 N 天的活跃簇里搜，避免无限制 KNN
RECENT_CLUSTER_DAYS = 3


async def find_or_create_cluster(
    db: AsyncSession,
    raw: RawInfo,
    *,
    threshold: float = DEFAULT_SIM_THRESHOLD,
) -> InfoCluster:
    """给 raw 找最近的簇；找不到就新建。"""
    if raw.embedding is None:
        raise ValueError(f"RawInfo {raw.id} 没有 embedding，无法聚类")

    # pgvector 的 cosine distance 操作：column.cosine_distance(vec)
    distance = InfoCluster.centroid.cosine_distance(raw.embedding)
    recent_cutoff = datetime.utcnow() - timedelta(days=RECENT_CLUSTER_DAYS)

    stmt = (
        select(InfoCluster, distance.label("dist"))
        .where(
            InfoCluster.centroid.is_not(None),
            InfoCluster.created_at >= recent_cutoff,
        )
        .order_by(distance)
        .limit(1)
    )
    row = (await db.execute(stmt)).first()

    if row and row.dist is not None and row.dist < threshold:
        cluster, dist = row
        # 额外检查：published_at 相差超过 3 天的不合并（避免 Claude 4.5 和 4.8 混在一起）
        if raw.published_at and cluster.published_at:
            gap = abs((raw.published_at - cluster.published_at).days)
            if gap > 3:
                logger.debug(
                    f"RawInfo {raw.id} 与 cluster {cluster.id} 时间差 {gap} 天，跳过合并"
                )
                cluster = InfoCluster(
                    core_title=(raw.title or "")[:500],
                    summary=raw.summary,
                    source_count=1,
                    source_urls=[raw.url] if raw.url else [],
                    published_at=raw.published_at,
                    centroid=raw.embedding,
                    mined=False,
                )
                db.add(cluster)
                await db.flush()
                raw.info_cluster_id = cluster.id
                raw.state = RAW_STATE_CLUSTERED
                logger.debug(f"RawInfo {raw.id} → 新簇 {cluster.id}（时间差过大）")
                return cluster
        await _attach_to_cluster(db, cluster, raw)
        logger.debug(f"RawInfo {raw.id} → cluster {cluster.id} (dist={dist:.3f})")
        return cluster

    # 新建簇
    cluster = InfoCluster(
        core_title=(raw.title or "")[:500],
        latest_title=(raw.title or "")[:500],
        summary=raw.summary,
        source_count=1,
        source_urls=[raw.url] if raw.url else [],
        published_at=raw.published_at,
        centroid=raw.embedding,
        mined=False,
    )
    db.add(cluster)
    await db.flush()
    raw.info_cluster_id = cluster.id
    raw.state = RAW_STATE_CLUSTERED
    logger.debug(f"RawInfo {raw.id} → 新簇 {cluster.id}")
    return cluster


async def _attach_to_cluster(db: AsyncSession, cluster: InfoCluster, raw: RawInfo) -> None:
    """把 raw 并入 cluster：更新 centroid / source_urls / source_count / published_at / latest_title。"""
    # 增量平均：new_centroid = (old * n + new) / (n+1)
    n = cluster.source_count or 1
    old = list(cluster.centroid) if cluster.centroid is not None else None
    if old is not None:
        new_centroid = [(o * n + v) / (n + 1) for o, v in zip(old, raw.embedding)]
        cluster.centroid = new_centroid

    cluster.source_count = n + 1

    urls = list(cluster.source_urls or [])
    if raw.url and raw.url not in urls:
        urls.append(raw.url)
    cluster.source_urls = urls

    # published_at 取最新
    if raw.published_at and (not cluster.published_at or raw.published_at > cluster.published_at):
        cluster.published_at = raw.published_at

    # latest_title 始终更新为最新 raw 的标题
    if raw.title:
        cluster.latest_title = raw.title[:500]

    raw.info_cluster_id = cluster.id
    raw.state = RAW_STATE_CLUSTERED
    # 簇有新成员加入，标记需要重新跑 LLM 富集
    cluster.mined = False


async def cluster_raw_batch(db: AsyncSession, raws: List[RawInfo]) -> List[InfoCluster]:
    """对一批已 embed 的 RawInfo 顺序聚类。返回被触达的簇（去重）。"""
    touched: dict[int, InfoCluster] = {}
    for raw in raws:
        if raw.embedding is None:
            logger.warning(f"RawInfo {raw.id} 跳过聚类：无 embedding")
            continue
        try:
            cluster = await find_or_create_cluster(db, raw)
            touched[cluster.id] = cluster
        except Exception as e:
            logger.error(f"RawInfo {raw.id} 聚类失败: {e}")
    await db.flush()
    return list(touched.values())
