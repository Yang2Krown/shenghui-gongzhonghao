"""预处理：抓取 RawInfo 全文正文。

多数 adapter 只给短摘要片段（snippet/description），没有正文（RawInfo.content 为空）。
本模块对缺正文的 raw 用 Jina Reader（agent_reach_client.read_url）抓正文 Markdown，
写入 RawInfo.content，供 enricher 生成"正文级"事实摘要。

抓取对用户无感：全部在预处理 pipeline 后台进行。单篇抓取失败时静默降级
（content 留空），enricher 会自动回退用 summary 片段，不阻塞主流程。
"""

import asyncio
import logging
from typing import List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.info_cluster import InfoCluster
from app.models.raw_info import RawInfo
from app.services.scraping.agent_reach_runner import agent_reach_client

logger = logging.getLogger(__name__)

# 单篇正文入库截断上限（字符），控制存储与下游 token
MAX_CONTENT_CHARS = 8000
# 每个簇最多抓几篇（enricher 富集时用前 5 篇，但抓取较贵，取前 3 篇代表）
MAX_RAWS_PER_CLUSTER = 3
# 并发抓取上限（Jina Reader 是外部 HTTP，避免打太猛被限速）
FETCH_CONCURRENCY = 4


async def fetch_fulltext_for_clusters(
    db: AsyncSession,
    clusters: List[InfoCluster],
) -> int:
    """对待富集簇内、缺正文的 raw 抓全文，写入 RawInfo.content。

    Returns:
        成功抓取的条数。
    """
    if not clusters:
        return 0

    # 收集待抓 raw：簇内按时间倒序取前 N 篇，且 content 为空、有 url
    targets: List[RawInfo] = []
    for cluster in clusters:
        raws = (await db.execute(
            select(RawInfo).where(RawInfo.info_cluster_id == cluster.id)
        )).scalars().all()
        raws_sorted = sorted(
            raws,
            key=lambda r: r.published_at or r.created_at or 0,
            reverse=True,
        )
        for r in raws_sorted[:MAX_RAWS_PER_CLUSTER]:
            if not (r.content or "").strip() and (r.url or "").strip():
                targets.append(r)

    if not targets:
        return 0

    sem = asyncio.Semaphore(FETCH_CONCURRENCY)

    async def _one(raw: RawInfo) -> bool:
        async with sem:
            try:
                text = await agent_reach_client.read_url(raw.url)
            except Exception as e:
                logger.warning(
                    f"全文抓取失败 raw={raw.id} {(raw.url or '')[:80]}: "
                    f"{type(e).__name__}: {e}"
                )
                return False
            text = (text or "").strip()
            if not text:
                return False
            raw.content = text[:MAX_CONTENT_CHARS]
            return True

    results = await asyncio.gather(*[_one(r) for r in targets], return_exceptions=True)
    success = sum(1 for r in results if r is True)
    await db.flush()
    logger.info(f"全文抓取: {success}/{len(targets)} 条成功")
    return success
