"""进度快照存储。

每个生成任务（run）把进度事件追加到一个列表，轮询接口从事件列表推导当前快照。
事件列表仍然保留，因为它同时承载步骤、结果和错误状态。
"""

import logging
import time
import uuid
from typing import Optional

logger = logging.getLogger(__name__)


class _RunState:
    """单个 run 的状态：事件列表 + 完成标记。"""

    def __init__(self, user_id: Optional[int] = None) -> None:
        self.user_id = user_id
        self.events: list[dict] = []
        self.done: bool = False
        self.created_at: float = time.time()


class ProgressStore:
    """内存进度事件存储（单例）。"""

    def __init__(self, ttl_seconds: int = 3600):
        self._runs: dict[str, _RunState] = {}
        self._ttl = ttl_seconds

    # ── 生命周期 ──────────────────────────────────────

    def create_run(self, run_id: Optional[str] = None, user_id: Optional[int] = None) -> str:
        """创建一个新的进度任务，返回 run_id。"""
        run_id = run_id or str(uuid.uuid4())
        self._runs[run_id] = _RunState(user_id=user_id)
        logger.info(f"[ProgressStore] 创建 run: {run_id} user_id={user_id}")
        return run_id

    def cleanup(self, run_id: str) -> None:
        """清理已完成的 run。"""
        self._runs.pop(run_id, None)
        logger.info(f"[ProgressStore] 清理 run: {run_id}")

    def exists(self, run_id: str) -> bool:
        return run_id in self._runs

    def can_access(self, run_id: str, user_id: Optional[int]) -> bool:
        """Return whether the user owns the run.

        Legacy runs without owner are treated as inaccessible to avoid cross-user reads.
        """
        run = self._runs.get(run_id)
        return run is not None and run.user_id is not None and run.user_id == user_id

    def snapshot(self, run_id: str, user_id: Optional[int] = None) -> Optional[dict]:
        """返回某个 run 的当前进度快照（供轮询接口使用）。

        从事件列表里推导出：最近一个 step_start 的步骤/Agent 信息、是否完成、
        result / error。run 不存在（未创建或已清理）返回 None。
        """
        run = self._runs.get(run_id)
        if run is None or run.user_id is None or run.user_id != user_id:
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
        """向指定 run 追加一个进度事件。"""
        run = self._runs.get(run_id)
        if run is None:
            logger.warning(f"[ProgressStore] push 到不存在的 run: {run_id}")
            return
        run.events.append(event)
        if event.get("event") in ("result", "error"):
            run.done = True

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


# 全局单例
progress_store = ProgressStore()
