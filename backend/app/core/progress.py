"""进度事件存储。

为 SSE 实时推送提供后端支持。每个生成任务（run）关联一个 asyncio.Queue，
orchestrator 写入事件，SSE 端点读取并推送给前端。
"""

import asyncio
import json
import logging
import time
import uuid
from typing import AsyncGenerator, Optional

logger = logging.getLogger(__name__)


class ProgressStore:
    """内存进度事件存储（单例）。"""

    def __init__(self, ttl_seconds: int = 600):
        self._queues: dict[str, asyncio.Queue] = {}
        self._created_at: dict[str, float] = {}
        self._ttl = ttl_seconds

    # ── 生命周期 ──────────────────────────────────────

    def create_run(self, run_id: Optional[str] = None) -> str:
        """创建一个新的进度流，返回 run_id。"""
        run_id = run_id or str(uuid.uuid4())
        self._queues[run_id] = asyncio.Queue()
        self._created_at[run_id] = time.time()
        logger.info(f"[ProgressStore] 创建 run: {run_id}")
        return run_id

    def cleanup(self, run_id: str) -> None:
        """清理已完成的 run。"""
        self._queues.pop(run_id, None)
        self._created_at.pop(run_id, None)
        logger.info(f"[ProgressStore] 清理 run: {run_id}")

    def exists(self, run_id: str) -> bool:
        return run_id in self._queues

    # ── 写入 ──────────────────────────────────────────

    async def push(self, run_id: str, event: dict) -> None:
        """向指定 run 推送一个进度事件。"""
        queue = self._queues.get(run_id)
        if queue is None:
            logger.warning(f"[ProgressStore] push 到不存在的 run: {run_id}")
            return
        await queue.put(event)

    def push_sync(self, run_id: str, event: dict) -> None:
        """同步版本的 push（用于非 async 上下文，通过 ensure_future）。"""
        queue = self._queues.get(run_id)
        if queue is None:
            return
        asyncio.ensure_future(queue.put(event))

    # ── 读取（SSE 流） ────────────────────────────────

    async def stream(self, run_id: str) -> AsyncGenerator[str, None]:
        """异步生成器，yield SSE 格式的事件字符串。

        前端通过 EventSource 连接此流。
        收到 ``{"event": "done"}`` 后自动结束。
        """
        queue = self._queues.get(run_id)
        if queue is None:
            yield _sse_format({"event": "error", "data": {"message": f"run {run_id} 不存在"}})
            return

        try:
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=self._ttl)
                except asyncio.TimeoutError:
                    yield _sse_format({"event": "error", "data": {"message": "等待超时"}})
                    break

                yield _sse_format(event)

                # 收到结果或错误事件后结束流（result 在 complete 之后推送，必须等 result 到达再关闭）
                if event.get("event") in ("result", "error"):
                    break
        finally:
            # 延迟清理，给客户端一点时间接收最后的事件
            asyncio.get_event_loop().call_later(5.0, self.cleanup, run_id)

    # ── 自动清理过期 run ──────────────────────────────

    async def cleanup_expired(self) -> int:
        """清理所有过期的 run，返回清理数量。"""
        now = time.time()
        expired = [
            rid for rid, ts in self._created_at.items()
            if now - ts > self._ttl
        ]
        for rid in expired:
            self.cleanup(rid)
        return len(expired)


def _sse_format(event: dict) -> str:
    """将事件字典格式化为 SSE 文本。

    格式：
        event:{event_type}\n
        data:{json}\n\n
    """
    event_type = event.get("event", "message")
    data = event.get("data", {})
    return f"event:{event_type}\ndata:{json.dumps(data, ensure_ascii=False)}\n\n"


# 全局单例
progress_store = ProgressStore()
