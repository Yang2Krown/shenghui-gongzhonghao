"""Celery 任务中心的数据采集。"""

import asyncio
from datetime import timedelta
from typing import Dict

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.celery_app import celery_app
from app.core.celery_monitor import task_category
from app.core.timezone import utcnow
from app.models.celery_task_run import CeleryTaskRun


QUEUE_NAMES = ("default", "scraping", "ai", "publish")


def _inspect_celery() -> dict:
    inspector = celery_app.control.inspect(timeout=2)
    return {
        "active": inspector.active() or {},
        "reserved": inspector.reserved() or {},
        "scheduled": inspector.scheduled() or {},
        "active_queues": inspector.active_queues() or {},
        "stats": inspector.stats() or {},
    }


def _queue_from_task(item: dict) -> str:
    delivery = item.get("delivery_info") or {}
    return delivery.get("routing_key") or delivery.get("queue") or task_category(item.get("name", ""))


def _build_queue_stats(snapshot: dict) -> list:
    queues = {
        name: {
            "queue": name,
            "active": 0,
            "waiting": 0,
            "scheduled": 0,
            "workers": 0,
        }
        for name in QUEUE_NAMES
    }

    for worker, tasks in (snapshot.get("active") or {}).items():
        for task in tasks or []:
            queue = _queue_from_task(task)
            queues.setdefault(queue, {"queue": queue, "active": 0, "waiting": 0, "scheduled": 0, "workers": 0})
            queues[queue]["active"] += 1

    for worker, tasks in (snapshot.get("reserved") or {}).items():
        for task in tasks or []:
            queue = _queue_from_task(task)
            queues.setdefault(queue, {"queue": queue, "active": 0, "waiting": 0, "scheduled": 0, "workers": 0})
            queues[queue]["waiting"] += 1

    for worker, tasks in (snapshot.get("scheduled") or {}).items():
        for item in tasks or []:
            task = item.get("request") or item
            queue = _queue_from_task(task)
            queues.setdefault(queue, {"queue": queue, "active": 0, "waiting": 0, "scheduled": 0, "workers": 0})
            queues[queue]["scheduled"] += 1

    for worker, bindings in (snapshot.get("active_queues") or {}).items():
        for binding in bindings or []:
            queue = binding.get("name") or binding.get("routing_key") or "default"
            queues.setdefault(queue, {"queue": queue, "active": 0, "waiting": 0, "scheduled": 0, "workers": 0})
            queues[queue]["workers"] += 1

    # 老版本/异常 Worker 可能没有 active_queues 响应，至少保留在线 Worker 数。
    if not snapshot.get("active_queues"):
        queues["default"]["workers"] = len(snapshot.get("stats") or {})

    return list(queues.values())


async def collect_celery_overview(db: AsyncSession) -> dict:
    try:
        snapshot = await asyncio.to_thread(_inspect_celery)
        inspect_error = None
    except Exception as exc:
        snapshot = {"active": {}, "reserved": {}, "scheduled": {}, "stats": {}}
        inspect_error = str(exc)[:300]

    cutoff = utcnow() - timedelta(hours=24)
    rows = (await db.execute(
        select(CeleryTaskRun.status, CeleryTaskRun.category, func.count(CeleryTaskRun.id))
        .where(CeleryTaskRun.created_at >= cutoff)
        .group_by(CeleryTaskRun.status, CeleryTaskRun.category)
    )).all()
    counts: Dict[str, int] = {}
    category_counts: Dict[str, Dict[str, int]] = {}
    for status, category, count in rows:
        counts[status] = counts.get(status, 0) + int(count)
        category_counts.setdefault(category, {})[status] = int(count)

    worker_names = set((snapshot.get("stats") or {}).keys())
    worker_names.update((snapshot.get("active") or {}).keys())
    worker_names.update((snapshot.get("reserved") or {}).keys())

    return {
        "period": "24h",
        "counts": counts,
        "category_counts": category_counts,
        "queues": _build_queue_stats(snapshot),
        "workers": [{"name": name, "online": True} for name in sorted(worker_names)],
        "inspect_error": inspect_error,
        "generated_at": utcnow().isoformat(),
    }
