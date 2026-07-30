"""异步批量写入 API 请求监测日志，避免请求链路逐条提交数据库事务。"""

import asyncio
import logging
import time
from typing import Any

from sqlalchemy import insert

from app.core.timezone import utcnow
from app.db.session import AsyncSessionLocal
from app.models.api_request_log import ApiRequestLog

logger = logging.getLogger(__name__)


class ApiRequestLogWriter:
    def __init__(self, *, batch_size: int = 100, flush_interval: float = 1.0, queue_size: int = 5000):
        self.batch_size = batch_size
        self.flush_interval = flush_interval
        self.queue_size = queue_size
        self._queue: asyncio.Queue[dict[str, Any] | None] | None = None
        self._task: asyncio.Task[None] | None = None

    async def start(self) -> None:
        if self._task and not self._task.done():
            return
        self._queue = asyncio.Queue(maxsize=self.queue_size)
        self._task = asyncio.create_task(self._run(), name="api-request-log-writer")

    async def stop(self) -> None:
        if not self._queue or not self._task:
            return
        await self._queue.put(None)
        await self._task
        self._queue = None
        self._task = None

    def enqueue(self, item: dict[str, Any]) -> None:
        if not self._queue:
            return
        item.setdefault("created_at", utcnow())
        try:
            self._queue.put_nowait(item)
        except asyncio.QueueFull:
            logger.warning("API 请求日志队列已满，丢弃一条监测日志")

    async def _run(self) -> None:
        assert self._queue is not None
        stopping = False
        while not stopping:
            first = await self._queue.get()
            if first is None:
                break

            batch = [first]
            deadline = time.monotonic() + self.flush_interval
            while len(batch) < self.batch_size:
                timeout = deadline - time.monotonic()
                if timeout <= 0:
                    break
                try:
                    item = await asyncio.wait_for(self._queue.get(), timeout=timeout)
                except asyncio.TimeoutError:
                    break
                if item is None:
                    stopping = True
                    break
                batch.append(item)

            try:
                async with AsyncSessionLocal() as db:
                    await db.execute(insert(ApiRequestLog), batch)
                    await db.commit()
            except Exception:
                logger.exception("批量写入 API 请求监测日志失败，丢弃 %s 条", len(batch))


api_request_log_writer = ApiRequestLogWriter()
