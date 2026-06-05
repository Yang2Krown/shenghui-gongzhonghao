"""一次性 backfill：给现有 InfoCluster 重新生成"整合标题 + 整合简介"。

新逻辑（enricher）会在富集时分析簇内全部资讯，重写 core_title_zh / summary_zh。
但存量老簇是在旧逻辑下建的，大标题还是种子文章的标题。跑一次这个脚本即可整合。

用法（在后端容器内跑）：
  # 默认：整合最近 3 天、且还没有整合标题的簇
  docker compose -f docker-compose.prod.yml --env-file backend/.env.production \
    exec backend python -m scripts.backfill_integrated_titles

  # 整合最近 N 天的全部簇（含已有整合标题的，强制重写）
  ... python -m scripts.backfill_integrated_titles --days 7 --force

  # 不限天数，整合所有簇
  ... python -m scripts.backfill_integrated_titles --days 0
"""

import argparse
import asyncio
import os
import sys
from datetime import timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select, func
from app.core.timezone import utcnow
from app.db.session import AsyncSessionLocal
from app.models.info_cluster import InfoCluster
from app.models.raw_info import RawInfo
from app.services.preprocess.enricher import enrich_cluster
from app.services.llm import get_llm_client


async def main(days: int = 3, force: bool = False, limit: int = 0):
    async with AsyncSessionLocal() as db:
        # 只处理有关联 raw_info 的簇
        has_raw = (
            select(RawInfo.info_cluster_id)
            .where(RawInfo.info_cluster_id.isnot(None))
            .group_by(RawInfo.info_cluster_id)
        ).subquery()

        stmt = select(InfoCluster).where(InfoCluster.id.in_(select(has_raw.c.info_cluster_id)))
        if days > 0:
            cutoff = utcnow() - timedelta(days=days)
            stmt = stmt.where(InfoCluster.created_at >= cutoff)
        if not force:
            # 只补还没有整合标题的
            stmt = stmt.where(InfoCluster.core_title_zh.is_(None))
        stmt = stmt.order_by(InfoCluster.created_at.desc())
        if limit > 0:
            stmt = stmt.limit(limit)

        clusters = (await db.execute(stmt)).scalars().all()
        total = len(clusters)
        if not total:
            print("没有需要整合的簇（可能都已有整合标题，加 --force 强制重写）。")
            return

        print(f"准备整合 {total} 个簇（days={days} force={force}）\n")

        client = get_llm_client()
        ok = 0
        for i, c in enumerate(clusters, 1):
            old = c.core_title_zh or c.core_title
            success = await enrich_cluster(db, c, llm_client=client)
            if success:
                ok += 1
                print(f"[{i}/{total}] 簇{c.id}: 「{(old or '')[:30]}」 → 「{(c.core_title_zh or '')[:40]}」")
            else:
                print(f"[{i}/{total}] 簇{c.id}: 富集失败，跳过")
            # 每 20 个提交一次，避免长事务
            if i % 20 == 0:
                await db.commit()

        await db.commit()
        print(f"\n✅ 完成：{ok}/{total} 个簇已整合。")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--days", type=int, default=3, help="只处理最近 N 天的簇；0 表示不限")
    p.add_argument("--force", action="store_true", help="已有整合标题的也强制重写")
    p.add_argument("--limit", type=int, default=0, help="最多处理多少个（0 不限）")
    args = p.parse_args()
    asyncio.run(main(days=args.days, force=args.force, limit=args.limit))
