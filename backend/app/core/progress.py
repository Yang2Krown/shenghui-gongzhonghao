"""生成任务进度存储。

Redis 是跨 API 进程 / Celery worker 的共享事实源，进程内字典保留为低延迟缓存和
Redis 不可用时的降级路径。事件列表仍然保留，因为它同时承载步骤、结果和错误状态。
"""

import json
import logging
import asyncio
import time
import uuid
from typing import Optional

import redis
import redis.asyncio as redis_async

from app.core.config import settings

logger = logging.getLogger(__name__)


class _RunState:
    """单个 run 的状态：事件列表 + 完成标记。"""

    def __init__(
        self,
        user_id: Optional[int] = None,
        *,
        created_at: Optional[float] = None,
    ) -> None:
        self.user_id = user_id
        self.events: list[dict] = []
        self.done: bool = False
        self.created_at: float = created_at or time.time()


class ProgressStore:
    """进度事件存储，支持 Redis 优先和内存降级。"""

    def __init__(
        self,
        ttl_seconds: int = 3600,
        *,
        redis_enabled: bool = False,
        redis_prefix: str = "progress",
    ) -> None:
        self._runs: dict[str, _RunState] = {}
        self._ttl = ttl_seconds
        self._redis_enabled = redis_enabled
        self._redis_prefix = redis_prefix.strip(":") or "progress"
        self._redis_retry_after = 0.0

    # ── Redis helpers ──────────────────────────────────────

    def _redis_can_try(self) -> bool:
        return self._redis_enabled and time.time() >= self._redis_retry_after

    def _mark_redis_failure(self, exc: Exception) -> None:
        # 短暂熔断，避免 Redis 故障时每个 token 都重复建立连接并刷屏。
        self._redis_retry_after = time.time() + 5
        logger.warning("[ProgressStore] Redis 不可用，降级到内存: %s", exc)

    def _meta_key(self, run_id: str) -> str:
        return f"{self._redis_prefix}:{run_id}:meta"

    def _events_key(self, run_id: str) -> str:
        return f"{self._redis_prefix}:{run_id}:events"

    def _redis_kwargs(self) -> dict:
        return {
            "host": settings.REDIS_HOST,
            "port": settings.REDIS_PORT,
            "db": settings.REDIS_DB,
            "password": settings.REDIS_PASSWORD,
            "decode_responses": True,
            "socket_connect_timeout": settings.REDIS_CONNECT_TIMEOUT_SECONDS,
            "socket_timeout": settings.REDIS_SOCKET_TIMEOUT_SECONDS,
        }

    def _persist_created_run(self, run_id: str, run: _RunState) -> None:
        if not self._redis_can_try():
            return
        client = redis.Redis(**self._redis_kwargs())
        try:
            pipe = client.pipeline()
            pipe.delete(self._events_key(run_id))
            pipe.hset(
                self._meta_key(run_id),
                mapping={
                    "user_id": str(run.user_id),
                    "created_at": str(run.created_at),
                    "done": "0",
                },
            )
            pipe.expire(self._meta_key(run_id), self._ttl)
            pipe.expire(self._events_key(run_id), self._ttl)
            pipe.execute()
        except Exception as exc:  # Redis 故障不能阻断生成任务本身
            self._mark_redis_failure(exc)
        finally:
            try:
                client.close()
            except Exception:
                pass

    async def _load_redis_run(self, run_id: str) -> Optional[_RunState]:
        if not self._redis_can_try():
            return None
        client = redis_async.Redis(**self._redis_kwargs())
        try:
            meta = await client.hgetall(self._meta_key(run_id))
            if not meta:
                return None
            try:
                raw_user_id = meta.get("user_id")
                user_id = int(raw_user_id) if raw_user_id not in (None, "", "None") else None
                created_at = float(meta.get("created_at"))
            except (TypeError, ValueError):
                logger.warning("[ProgressStore] Redis run 元数据损坏: %s", run_id)
                return None
            run = _RunState(user_id=user_id, created_at=created_at)
            raw_events = await client.lrange(self._events_key(run_id), 0, -1)
            for raw_event in raw_events:
                try:
                    event = json.loads(raw_event)
                except (TypeError, ValueError):
                    continue
                if isinstance(event, dict):
                    run.events.append(event)
            run.done = meta.get("done") == "1"
            return run
        except Exception as exc:
            self._mark_redis_failure(exc)
            return None
        finally:
            try:
                await client.aclose()
            except Exception:
                pass

    async def _persist_created_run_async(self, run_id: str, run: _RunState) -> None:
        """异步创建 Redis 元数据，避免在 FastAPI 请求线程里同步阻塞。"""
        if not self._redis_can_try():
            return
        client = redis_async.Redis(**self._redis_kwargs())
        try:
            pipe = client.pipeline()
            pipe.delete(self._events_key(run_id))
            pipe.hset(
                self._meta_key(run_id),
                mapping={
                    "user_id": str(run.user_id),
                    "created_at": str(run.created_at),
                    "done": "0",
                },
            )
            pipe.expire(self._meta_key(run_id), self._ttl)
            pipe.expire(self._events_key(run_id), self._ttl)
            await pipe.execute()
        except Exception as exc:
            self._mark_redis_failure(exc)
        finally:
            try:
                await client.aclose()
            except Exception:
                pass

    async def _persist_event(self, run_id: str, run: _RunState, event: dict) -> None:
        if not self._redis_can_try():
            return
        client = redis_async.Redis(**self._redis_kwargs())
        try:
            done = "1" if run.done else "0"
            pipe = client.pipeline()
            pipe.rpush(
                self._events_key(run_id),
                json.dumps(event, ensure_ascii=False, default=str),
            )
            pipe.hset(
                self._meta_key(run_id),
                mapping={
                    "user_id": str(run.user_id),
                    "created_at": str(run.created_at),
                    "done": done,
                },
            )
            pipe.expire(self._meta_key(run_id), self._ttl)
            pipe.expire(self._events_key(run_id), self._ttl)
            await pipe.execute()
        except Exception as exc:
            self._mark_redis_failure(exc)
        finally:
            try:
                await client.aclose()
            except Exception:
                pass

    # ── 生命周期 ──────────────────────────────────────

    def create_run(self, run_id: Optional[str] = None, user_id: Optional[int] = None) -> str:
        """创建一个新的进度任务，返回 run_id。"""
        run_id = run_id or str(uuid.uuid4())
        run = _RunState(user_id=user_id)
        self._runs[run_id] = run
        if self._redis_enabled:
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                # 同步脚本/测试没有事件循环时仍保留可用的同步路径。
                self._persist_created_run(run_id, run)
            else:
                loop.create_task(self._persist_created_run_async(run_id, run))
        logger.info("[ProgressStore] 创建 run: %s user_id=%s", run_id, user_id)
        return run_id

    def cleanup(self, run_id: str) -> None:
        """清理已完成的本地 run；Redis key 依靠 TTL 自动过期。"""
        self._runs.pop(run_id, None)
        logger.info("[ProgressStore] 清理 run: %s", run_id)

    def exists(self, run_id: str) -> bool:
        return run_id in self._runs

    def can_access(self, run_id: str, user_id: Optional[int]) -> bool:
        """判断用户是否拥有 run。未绑定用户的旧任务不可读取。"""
        run = self._runs.get(run_id)
        return run is not None and run.user_id is not None and run.user_id == user_id

    @staticmethod
    def _build_snapshot(run: _RunState, user_id: Optional[int]) -> Optional[dict]:
        if run.user_id is None or run.user_id != user_id:
            return None

        step_map: dict[int, dict] = {}
        done_steps: set[int] = set()
        result = None
        error = None
        partial_result = None
        last_event_id = 0
        current_stage = None
        current_message = None
        waiting_stage = None
        waiting_message = None
        for ev in run.events:
            try:
                last_event_id = max(last_event_id, int(ev.get("event_id", 0)))
            except (TypeError, ValueError):
                pass
            et = ev.get("event")
            data = ev.get("data", {}) or {}
            if et == "step_start":
                current_stage = data.get("stage") or current_stage
                current_message = data.get("action") or current_message
                waiting_stage = None
                waiting_message = None
                step = data.get("step", 0)
                step_map[step] = {
                    "step": step,
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
                current_message = error
            elif et == "partial_result":
                partial_result = data
                waiting_stage = None
                waiting_message = None
            elif et == "stage_waiting":
                waiting_stage = data.get("stage")
                waiting_message = data.get("message")

        steps = [step_map[key] for key in sorted(step_map)]
        current = max(step_map) if step_map else 0
        cur_info = step_map.get(current, {})
        return {
            "exists": True,
            "done": run.done,
            "steps": steps,
            "current_step": current,
            "done_steps": sorted(done_steps),
            "result": result,
            "error": error,
            "partial_result": partial_result,
            "step": current,
            "agent": cur_info.get("agent"),
            "avatar": cur_info.get("avatar"),
            "last_event_id": last_event_id,
            "stage": waiting_stage or current_stage,
            "stage_message": waiting_message,
            "action": waiting_message or current_message or cur_info.get("action"),
        }

    def snapshot(self, run_id: str, user_id: Optional[int] = None) -> Optional[dict]:
        """读取本地缓存快照，保留给同步调用方和单元测试。"""
        run = self._runs.get(run_id)
        if run is None:
            return None
        return self._build_snapshot(run, user_id)

    async def snapshot_async(
        self,
        run_id: str,
        user_id: Optional[int] = None,
    ) -> Optional[dict]:
        """优先读取 Redis，Redis 不可用时回退到本地缓存。"""
        redis_run = await self._load_redis_run(run_id)
        if redis_run is not None:
            # 缓存一份，Redis 短暂故障时仍能继续返回最近快照。
            self._runs[run_id] = redis_run
            return self._build_snapshot(redis_run, user_id)
        return self.snapshot(run_id, user_id=user_id)

    # ── 写入 ──────────────────────────────────────────

    async def push(self, run_id: str, event: dict) -> None:
        """向指定 run 追加事件；worker 进程可从 Redis 恢复 run 元数据。"""
        run = self._runs.get(run_id)
        if run is None:
            run = await self._load_redis_run(run_id)
            if run is not None:
                self._runs[run_id] = run
        if run is None:
            logger.warning("[ProgressStore] push 到不存在的 run: %s", run_id)
            return
        event = dict(event)
        event["event_id"] = len(run.events) + 1
        run.events.append(event)
        if event.get("event") in ("result", "error", "stage_waiting"):
            run.done = True
        elif event.get("event") not in {"keep_alive"}:
            # 同一个 run 在人工确认后会继续进入下游阶段；不要让上一个
            # stage_waiting 的终态阻止新的 SSE 连接读取后续事件。
            run.done = False
        await self._persist_event(run_id, run, event)

    # ── 自动清理过期 run ──────────────────────────────

    async def cleanup_expired(self) -> int:
        """清理本地过期 run，Redis 记录由 TTL 自动过期。"""
        now = time.time()
        expired = [
            run_id
            for run_id, run in self._runs.items()
            if now - run.created_at > self._ttl
        ]
        for run_id in expired:
            self.cleanup(run_id)
        return len(expired)


# 全局单例：生产环境 Redis 优先；Redis 短暂不可用时保持现有任务可用。
progress_store = ProgressStore(
    ttl_seconds=settings.PROGRESS_STORE_TTL_SECONDS,
    redis_enabled=settings.PROGRESS_STORE_REDIS_ENABLED,
    redis_prefix=settings.PROGRESS_STORE_REDIS_PREFIX,
)
