"""Celery 生命周期监控。

Celery worker 和 Web 进程都会加载这些 signal。所有写入失败都被吞掉，不能
因为监控数据库异常影响真实任务投递或执行。
"""

import logging
from typing import Any, Optional

from celery.signals import after_task_publish, task_failure, task_postrun, task_prerun, task_retry
from sqlalchemy.exc import IntegrityError

from app.core.timezone import utcnow
from app.db.session import SessionLocal
from app.models.celery_task_run import CeleryTaskRun

logger = logging.getLogger(__name__)
_SENSITIVE_KEYS = ("token", "secret", "password", "api_key", "cookie", "authorization")


def task_category(task_name: str) -> str:
    name = (task_name or "").lower()
    if name.startswith("scraper."):
        return "scraping"
    if name.startswith(("preprocess.", "mining.", "commercial.", "ai.", "content.", "title.", "outline.", "versions.", "experience.")):
        return "ai"
    if name.startswith(("publish.", "xhs.")):
        return "publish"
    return "default"


def task_queue(task_name: str, routing_key: Optional[str] = None) -> str:
    return routing_key or task_category(task_name)


def _now() -> str:
    return utcnow().isoformat()


def _json_safe(value: Any, depth: int = 0) -> Any:
    if depth > 4:
        return "[truncated]"
    if value is None or isinstance(value, (str, int, float, bool)):
        if isinstance(value, str) and len(value) > 10000:
            return value[:10000] + "...[truncated]"
        return value
    if isinstance(value, dict):
        safe = {}
        for key, item in value.items():
            key_text = str(key)
            safe[key_text] = "[redacted]" if any(word in key_text.lower() for word in _SENSITIVE_KEYS) else _json_safe(item, depth + 1)
        return safe
    if isinstance(value, (list, tuple)):
        return [_json_safe(v, depth + 1) for v in value[:100]]
    return str(value)[:1000]


def _body_args_kwargs(body: Any) -> tuple:
    if isinstance(body, dict):
        return body.get("args", []), body.get("kwargs", {})
    if isinstance(body, (list, tuple)):
        return (body[0] if len(body) > 0 else []), (body[1] if len(body) > 1 else {})
    return [], {}


def _upsert(task_id: str, **values: Any) -> None:
    if not task_id:
        return
    # Beat 发布和 Worker 开始信号可能在不同进程同时创建同一 task_id。
    # 唯一键竞争时重读已由另一进程创建的行，再更新当前状态。
    for attempt in range(2):
        db = SessionLocal()
        try:
            row = db.query(CeleryTaskRun).filter(CeleryTaskRun.task_id == task_id).first()
            if row is None:
                row = CeleryTaskRun(
                    task_id=task_id,
                    task_name=values.get("task_name", "unknown"),
                    category=values.get("category", "default"),
                    queue=values.get("queue", "default"),
                )
                db.add(row)
            for key, value in values.items():
                if hasattr(row, key):
                    setattr(row, key, value)
            db.commit()
            return
        except IntegrityError:
            db.rollback()
            if attempt:
                logger.warning("写入 Celery 任务监控记录失败", exc_info=True)
        except Exception:
            db.rollback()
            logger.warning("写入 Celery 任务监控记录失败", exc_info=True)
            return
        finally:
            db.close()


@after_task_publish.connect(weak=False)
def record_task_published(sender=None, headers=None, body=None, exchange=None, routing_key=None, **kwargs):
    headers = headers or {}
    task_name = sender or headers.get("task") or "unknown"
    task_id = headers.get("id")
    args, task_kwargs = _body_args_kwargs(body)
    queue = task_queue(task_name, routing_key)
    _upsert(
        task_id,
        task_name=task_name,
        category=task_category(task_name),
        queue=queue,
        status="waiting",
        args_json=_json_safe(args),
        kwargs_json=_json_safe(task_kwargs),
        last_seen_at=_now(),
    )


@task_prerun.connect(weak=False)
def record_task_started(task_id=None, task=None, args=None, kwargs=None, **signal_kwargs):
    request = getattr(task, "request", None)
    delivery = getattr(request, "delivery_info", {}) or {}
    task_name = getattr(task, "name", None) or signal_kwargs.get("sender") or "unknown"
    _upsert(
        task_id,
        task_name=task_name,
        category=task_category(task_name),
        queue=task_queue(task_name, delivery.get("routing_key") or delivery.get("queue")),
        status="running",
        worker=getattr(request, "hostname", None),
        started_at=_now(),
        last_seen_at=_now(),
        args_json=_json_safe(args),
        kwargs_json=_json_safe(kwargs),
    )


@task_retry.connect(weak=False)
def record_task_retry(request=None, reason=None, einfo=None, **kwargs):
    task_id = getattr(request, "id", None)
    retry_count = int(getattr(request, "retries", 0) or 0) + 1
    _upsert(
        task_id,
        status="retrying",
        retry_count=retry_count,
        error_message=str(reason or einfo or "任务正在重试")[:4000],
        last_seen_at=_now(),
        is_dead_letter=False,
    )


@task_failure.connect(weak=False)
def record_task_failure(task_id=None, exception=None, traceback=None, sender=None, **kwargs):
    task_name = getattr(sender, "name", None) or "unknown"
    _upsert(
        task_id,
        task_name=task_name,
        category=task_category(task_name),
        status="dead_letter",
        error_message=str(exception or "任务失败")[:4000],
        finished_at=_now(),
        last_seen_at=_now(),
        is_dead_letter=True,
    )


@task_postrun.connect(weak=False)
def record_task_finished(task_id=None, task=None, state=None, retval=None, **kwargs):
    if state == "RETRY":
        return
    task_name = getattr(task, "name", None) or "unknown"
    if state == "SUCCESS":
        result = _json_safe(retval)
        _upsert(
            task_id,
            task_name=task_name,
            category=task_category(task_name),
            status="success",
            result_json=result if isinstance(result, (dict, list, str, int, float, bool)) else {"value": str(result)},
            finished_at=_now(),
            last_seen_at=_now(),
            is_dead_letter=False,
        )
    elif state == "FAILURE":
        # task_failure signal 已经把记录标记为死信，这里只更新时间，不覆盖状态。
        _upsert(task_id, last_seen_at=_now())
