"""一次性修复脚本：把 published_at=NULL + freshness='expired' 的 InfoCluster
改为按 created_at 重算 freshness。

用法（在后端容器内跑）：
  python -m scripts.fix_freshness
或者：
  docker compose exec backend python -c "
import asyncio; from scripts.fix_freshness import main; asyncio.run(main())
"
"""

import asyncio
import sys
import os

# 让 import app.* 能找到
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select, update
from app.db.session import AsyncSessionLocal
from app.models.info_cluster import InfoCluster
from app.services.preprocess.rules import compute_freshness


async def main():
    async with AsyncSessionLocal() as db:
        # 找所有 published_at IS NULL 的 cluster
        stmt = select(InfoCluster).where(InfoCluster.published_at.is_(None))
        clusters = (await db.execute(stmt)).scalars().all()

        updated = 0
        for c in clusters:
            old = c.freshness
            new = compute_freshness(None, fallback_dt=c.created_at)
            if old != new:
                c.freshness = new
                updated += 1
                print(f"  cluster {c.id}: {old} -> {new} (created_at={c.created_at})")

        await db.commit()
        print(f"\n修复完成: 共 {len(clusters)} 条 published_at=NULL, 更新了 {updated} 条 freshness")


if __name__ == "__main__":
    asyncio.run(main())
