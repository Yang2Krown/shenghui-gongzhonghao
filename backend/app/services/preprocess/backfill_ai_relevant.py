"""一次性脚本：把 info_clusters 表里所有行按当前 is_ai_related 规则刷一遍 is_ai_relevant 列。

用法：
    cd backend && python -m app.services.preprocess.backfill_ai_relevant
"""

import asyncio
import logging

from sqlalchemy import select

from app.db.session import AsyncSessionLocal
from app.models.info_cluster import InfoCluster
from app.services.preprocess.rules import is_ai_related

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")


async def backfill():
    async with AsyncSessionLocal() as db:
        clusters = (await db.execute(select(InfoCluster))).scalars().all()
        total = len(clusters)
        relevant = 0
        flipped = 0

        for c in clusters:
            title = " ".join(filter(None, [c.core_title, c.core_title_zh]))
            summary = " ".join(filter(None, [c.summary, c.summary_zh]))
            new_val = is_ai_related(title, summary)
            if c.is_ai_relevant != new_val:
                c.is_ai_relevant = new_val
                flipped += 1
            if new_val:
                relevant += 1

        await db.commit()
        logger.info(
            f"扫描完成：{total} 条，AI 相关 {relevant} 条 ({relevant / max(total, 1) * 100:.1f}%)，"
            f"翻转 {flipped} 条标记"
        )


if __name__ == "__main__":
    asyncio.run(backfill())
