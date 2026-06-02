"""进度事件存储。

为 SSE 实时推送提供后端支持。每个生成任务（run）把事件**追加到一个列表**，
所有连接都从头重放该列表 + 跟随实时增量。

为什么不用单个 asyncio.Queue：
    Queue 的 get() 会把每个事件**只交给一个**消费者。一旦 EventSource 自动重连
    （生产网络抖动、代理 idle、切后台标签页都会触发），或同时有第二个连接，
    事件就会被"抢走/漏掉"，表现为进度卡住或乱跳。改成「事件列表 + 重放」后，
    每个连接各自维护读取游标，互不影响，重连也能补齐历史。
"""

import asyncio
import json
import logging
import time
import uuid
from typing import AsyncGenerator, Optional

logger = logging.getLogger(__name__)


class _RunState:
    """单个 run 的状态：事件列表 + 完成标记 + 通知条件。"""

    def __init__(self) -> None:
        self.events: list[dict] = []
        self.done: bool = False
        self.created_at: float = time.time()
        self.cond: asyncio.Condition = asyncio.Condition()


class ProgressStore:
    """内存进度事件存储（单例），可重放、多消费者。"""

    def __init__(self, ttl_seconds: int = 3600):
        self._runs: dict[str, _RunState] = {}
        self._ttl = ttl_seconds

    # ── 生命周期 ──────────────────────────────────────

    def create_run(self, run_id: Optional[str] = None) -> str:
        """创建一个新的进度流，返回 run_id。"""
        run_id = run_id or str(uuid.uuid4())
        self._runs[run_id] = _RunState()
        logger.info(f"[ProgressStore] 创建 run: {run_id}")
        return run_id

    def cleanup(self, run_id: str) -> None:
        """清理已完成的 run。"""
        self._runs.pop(run_id, None)
        logger.info(f"[ProgressStore] 清理 run: {run_id}")

    def exists(self, run_id: str) -> bool:
        return run_id in self._runs

    def snapshot(self, run_id: str) -> Optional[dict]:
        """返回某个 run 的当前进度快照（供轮询接口用，绕开 SSE）。

        从事件列表里推导出：最近一个 step_start 的步骤/Agent 信息、是否完成、
        result / error。run 不存在（未创建或已清理）返回 None。
        """
        run = self._runs.get(run_id)
        if run is None:
            return None

        step_map: dict[int, dict] = {}
        done_steps: set[int] = set()
        result = None
        error = None
        for ev in run.events:
            et = ev.get("event")
            data = ev.get("data", {}) or {}
            if et == "step_start":
                s = data.get("step", 0)
                step_map[s] = {
                    "step": s,
                    "agent": data.get("agent"),
                    "action": data.get("action"),
                    "avatar": data.get("avatar"),
                }
            elif et in ("step_done", "complete"):
                done_steps.add(data.get("step", 0))
            elif et == "result":
                result = data
            elif et == "error":
                error = data.get("message")

        steps = [step_map[k] for k in sorted(step_map)]
        current = max(step_map) if step_map else 0
        cur_info = step_map.get(current, {})

        return {
            "exists": True,
            "done": run.done,
            "steps": steps,                 # 全部步骤（创作页渲染步骤列表用）
            "current_step": current,        # 1 基
            "done_steps": sorted(done_steps),
            "result": result,
            "error": error,
            # 兼容扁平字段（话题挖掘页轮询用）
            "step": current,
            "agent": cur_info.get("agent"),
            "action": cur_info.get("action"),
            "avatar": cur_info.get("avatar"),
        }

    # ── 写入 ──────────────────────────────────────────

    async def push(self, run_id: str, event: dict) -> None:
        """向指定 run 追加一个进度事件，并通知所有等待的消费者。"""
        run = self._runs.get(run_id)
        if run is None:
            logger.warning(f"[ProgressStore] push 到不存在的 run: {run_id}")
            return
        async with run.cond:
            run.events.append(event)
            if event.get("event") in ("result", "error"):
                run.done = True
            run.cond.notify_all()

    # ── 读取（SSE 流） ────────────────────────────────

    async def stream(self, run_id: str) -> AsyncGenerator[str, None]:
        """异步生成器，yield SSE 格式的事件字符串。

        每个连接都从头重放已有事件，再跟随实时增量；收到 ``result`` / ``error``
        后结束。多个连接 / 重连互不影响（各自维护读取游标 idx）。
        """
        run = self._runs.get(run_id)
        if run is None:
            yield _sse_format({"event": "error", "data": {"message": f"run {run_id} 不存在"}})
            return

        # 2KB 填充注释，强制 CDN / 反向代理冲刷缓冲区
        yield ":" + " " * 2048 + "\n\n"
        yield _sse_format({"event": "connected", "data": {"run_id": run_id}})

        idx = 0
        heartbeat_interval = 15
        try:
            while True:
                new_events: list[dict] = []
                async with run.cond:
                    if idx >= len(run.events):
                        if run.done:
                            # 历史已全部送达且任务结束
                            return
                        # 等新事件，超时则发心跳
                        try:
                            await asyncio.wait_for(run.cond.wait(), timeout=heartbeat_interval)
                        except asyncio.TimeoutError:
                            pass
                    new_events = run.events[idx:]
                    idx = len(run.events)

                if not new_events:
                    yield ":heartbeat\n\n"
                    continue

                for event in new_events:
                    yield _sse_format(event)
                    if event.get("event") in ("result", "error"):
                        return
        finally:
            # 延迟清理：给重连 / 其它消费者留出补齐历史的窗口
            try:
                asyncio.get_event_loop().call_later(30.0, self.cleanup, run_id)
            except RuntimeError:
                pass

    # ── 自动清理过期 run ──────────────────────────────

    async def cleanup_expired(self) -> int:
        """清理所有过期的 run，返回清理数量。"""
        now = time.time()
        expired = [
            rid for rid, run in self._runs.items()
            if now - run.created_at > self._ttl
        ]
        for rid in expired:
            self.cleanup(rid)
        return len(expired)


def _sse_format(event: dict) -> str:
    """将事件字典格式化为 SSE 文本。

    每个事件前加 8KB 注释填充，强制代理层冲刷缓冲区。
    """
    event_type = event.get("event", "message")
    data = event.get("data", {})
    padding = ":" + " " * 8192 + "\n"
    return f"{padding}event:{event_type}\ndata:{json.dumps(data, ensure_ascii=False)}\n\n"


# 全局单例
progress_store = ProgressStore()
