"""一次性清理脚本：删除标题完全相同的重复 RawInfo。

背景：早期入库去重只按精确 URL 匹配，同一篇文章换了 URL（微信跟踪参数等）会
重复入库，导致「原文来源」里出现两条一模一样的条目，并虚高 source_count / 热度分。

策略：
  1. 按 lower(trim(title)) 分组，找出同标题的 RawInfo
  2. 每组保留 id 最小的一条，其余删除
  3. 重算受影响 InfoCluster 的 source_count / source_urls

用法（在后端容器内跑）：
  docker compose -f docker-compose.prod.yml --env-file backend/.env.production \
    exec backend python -m scripts.dedup_raw_infos

加 --apply 才会真正删除；不加只打印将要删除的内容（dry-run）。
"""

import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select, func, delete
from app.db.session import AsyncSessionLocal
from app.models.raw_info import RawInfo
from app.models.info_cluster import InfoCluster


async def main(apply: bool = False):
    async with AsyncSessionLocal() as db:
        # 1. 找出有重复标题的归一化 key（出现 >1 次）
        norm_title = func.lower(func.trim(RawInfo.title))
        dup_stmt = (
            select(norm_title.label("nt"), func.count().label("cnt"))
            .where(RawInfo.title.isnot(None), func.trim(RawInfo.title) != "")
            .group_by(norm_title)
            .having(func.count() > 1)
        )
        dup_groups = (await db.execute(dup_stmt)).all()

        if not dup_groups:
            print("没有发现标题重复的 RawInfo，无需清理。")
            return

        print(f"发现 {len(dup_groups)} 组标题重复的内容\n")

        ids_to_delete: list[int] = []
        affected_cluster_ids: set[int] = set()

        for nt, cnt in dup_groups:
            rows = (await db.execute(
                select(RawInfo)
                .where(func.lower(func.trim(RawInfo.title)) == nt)
                .order_by(RawInfo.id)
            )).scalars().all()

            keep = rows[0]
            drop = rows[1:]
            print(f"  「{(keep.title or '')[:40]}」 共 {cnt} 条 → 保留 id={keep.id}，删除 {[r.id for r in drop]}")

            for r in drop:
                ids_to_delete.append(r.id)
                if r.info_cluster_id:
                    affected_cluster_ids.add(r.info_cluster_id)
            if keep.info_cluster_id:
                affected_cluster_ids.add(keep.info_cluster_id)

        print(f"\n合计将删除 {len(ids_to_delete)} 条重复 RawInfo，影响 {len(affected_cluster_ids)} 个簇")

        if not apply:
            print("\n[dry-run] 未做任何修改。确认无误后加 --apply 重新运行以真正删除。")
            return

        # 2. 删除重复行
        if ids_to_delete:
            await db.execute(delete(RawInfo).where(RawInfo.id.in_(ids_to_delete)))
            await db.flush()

        # 3. 重算受影响簇的 source_count / source_urls
        for cid in affected_cluster_ids:
            remaining = (await db.execute(
                select(RawInfo).where(RawInfo.info_cluster_id == cid)
            )).scalars().all()
            cluster = (await db.execute(
                select(InfoCluster).where(InfoCluster.id == cid)
            )).scalar_one_or_none()
            if not cluster:
                continue
            urls = []
            for r in remaining:
                if r.url and r.url not in urls:
                    urls.append(r.url)
            cluster.source_urls = urls
            cluster.source_count = len(remaining)

        await db.commit()
        print(f"\n✅ 清理完成：删除 {len(ids_to_delete)} 条，重算 {len(affected_cluster_ids)} 个簇。")


if __name__ == "__main__":
    apply = "--apply" in sys.argv
    asyncio.run(main(apply=apply))
