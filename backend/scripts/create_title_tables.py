"""一次性建表：补齐标题生成流水线所缺的 agent_logs 等表。

用法： python -m scripts.create_title_tables
"""

import asyncio
import logging

logging.basicConfig(level=logging.INFO)


async def main() -> None:
    from app.db.session import engine as async_engine
    from app.db.base import Base
    from app.models import agent as _agent  # noqa: F401  -- 触发模型注册
    from app.models import title as _title  # noqa: F401
    from app.models import task as _task    # noqa: F401

    tables = [
        Base.metadata.tables[name]
        for name in ("agent_logs",)
        if name in Base.metadata.tables
    ]
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all, tables=tables)
    logging.info(f"建表完成: {[t.name for t in tables]}")


if __name__ == "__main__":
    asyncio.run(main())
