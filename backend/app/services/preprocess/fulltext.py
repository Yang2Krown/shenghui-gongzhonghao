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
FETCH_CONCURRENCY = 6
# 单篇硬超时（秒）：Jina Reader 不可达时快速失败，不等满 30s
PER_FETCH_TIMEOUT = 12
# 单批最多抓多少篇：积压很多时也不会无限拉长（防止拖垮预处理软超时 1500s）
MAX_TOTAL_TARGETS = 60
# 整个全文抓取步骤的总时间预算（秒）：超了就放弃剩余的，让预处理继续
OVERALL_BUDGET = 240


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

    # 积压很多时只抓前 N 篇，剩下的留正文空（enricher 回退用 summary），
    # 避免一批要抓几百篇、把预处理的时间预算耗光导致软超时崩溃。
    skipped = 0
    if len(targets) > MAX_TOTAL_TARGETS:
        skipped = len(targets) - MAX_TOTAL_TARGETS
        targets = targets[:MAX_TOTAL_TARGETS]

    sem = asyncio.Semaphore(FETCH_CONCURRENCY)

    async def _one(raw: RawInfo) -> bool:
        async with sem:
            try:
                # 单篇硬超时：Jina Reader 不可达时快速失败
                text = await asyncio.wait_for(
                    agent_reach_client.read_url(raw.url), timeout=PER_FETCH_TIMEOUT
                )
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

    # 整步加总预算护栏：超时就放弃剩余抓取，保住已成功的，让预处理继续往下走
    tasks = [asyncio.ensure_future(_one(r)) for r in targets]
    try:
        results = await asyncio.wait_for(
            asyncio.gather(*tasks, return_exceptions=True), timeout=OVERALL_BUDGET
        )
        success = sum(1 for r in results if r is True)
    except asyncio.TimeoutError:
        for t in tasks:
            t.cancel()
        success = sum(1 for t in tasks if t.done() and not t.cancelled() and t.result() is True)
        logger.warning(f"全文抓取超出总预算 {OVERALL_BUDGET}s，放弃剩余，已成功 {success} 条")

    await db.flush()
    msg = f"全文抓取: {success}/{len(targets)} 条成功"
    if skipped:
        msg += f"（另有 {skipped} 篇本批跳过，正文留空）"
    logger.info(msg)
    return success
