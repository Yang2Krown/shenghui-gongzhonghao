"""一次运行所有 seed 脚本：先建表 → 再依次导 3 张表。"""

import asyncio
import logging

from app.db.base import Base
from app.db.session import engine, AsyncSessionLocal
from app.db.seeds import (
    seed_sources_from_table1,
    seed_accounts_from_table2,
    seed_rss_from_table3,
)
# 触发模型注册
from app.models import (  # noqa: F401
    source_registry, raw_info, info_cluster, topic_candidate, daily_topic_list,
    user, topic, creation, style,
)


async def main():
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    # 1. 建表（幂等）
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # 2. 顺序导入
    async with AsyncSessionLocal() as db:
        r1 = await seed_sources_from_table1.run(db)
        r2 = await seed_accounts_from_table2.run(db)
        r3 = await seed_rss_from_table3.run(db)

    print("=" * 60)
    print(f"  Table 1 (站点)   : {r1}")
    print(f"  Table 2 (博主账号): {r2}")
    print(f"  Table 3 (RSS)    : {r3}")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
