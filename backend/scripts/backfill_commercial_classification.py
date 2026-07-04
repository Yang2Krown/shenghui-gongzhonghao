"""回填脚本：为已有的商单数据补上 brand / category。

在服务器 docker 容器中运行：
  docker compose -f docker-compose.prod.yml --env-file backend/.env.production \
    exec backend python -m scripts.backfill_commercial_classification

逻辑：
1. 查询所有 commercial_level in ('suspected', 'likely') 且 brand/category 为空的记录
2. 使用规则匹配 + LLM 兜底，填充 commercial_brand 和 commercial_category
3. 逐条更新，打印进度
"""

import asyncio
import sys

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import AsyncSessionLocal, engine
from app.models.raw_info import RawInfo
from app.services.commercial_classification import classify_commercial


async def backfill():
    async with AsyncSessionLocal() as db:
        query = (
            select(RawInfo)
            .where(RawInfo.commercial_level.in_(["suspected", "likely"]))
            .where(
                (RawInfo.commercial_brand.is_(None))
                | (RawInfo.commercial_brand == "")
                | (RawInfo.commercial_category.is_(None))
                | (RawInfo.commercial_category == "")
            )
            .order_by(RawInfo.id)
        )
        rows = (await db.execute(query)).scalars().all()
        total = len(rows)
        print(f"找到 {total} 条待回填的商单记录")

        if total == 0:
            print("无需回填")
            return

        updated = 0
        for i, raw in enumerate(rows):
            meta = raw.commercial_meta or {}
            product = meta.get("product") or ""

            cls = await classify_commercial(
                title=raw.title or "",
                content=raw.content or "",
                product=product,
            )

            changed = False
            if cls.brand and not raw.commercial_brand:
                raw.commercial_brand = cls.brand
                changed = True
            if cls.category and not raw.commercial_category:
                raw.commercial_category = cls.category
                changed = True

            if changed:
                await db.commit()
                updated += 1

            status = "✓" if changed else "-"
            print(
                f"[{i+1}/{total}] {status} id={raw.id} "
                f"brand={cls.brand or '(none)'} cat={cls.category or '(none)'} "
                f"title={raw.title[:30]}"
            )

        print(f"\n回填完成：共 {total} 条，更新 {updated} 条")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(backfill())
