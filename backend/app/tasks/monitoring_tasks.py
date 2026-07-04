"""后台监测 Celery 任务。"""

import asyncio
import logging
from datetime import timedelta
from typing import Any, Dict

from celery import shared_task
from sqlalchemy import delete

from app.db.session import AsyncSessionLocal, engine
from app.core.timezone import utcnow
from app.models.api_request_log import ApiRequestLog
from app.models.llm_monitoring import LlmCallLog
from app.services.monitoring.checks import (
    collect_admin_monitoring,
    save_monitoring_snapshot,
    sync_monitoring_alerts,
)

logger = logging.getLogger(__name__)


async def _collect() -> Dict[str, Any]:
    try:
        async with AsyncSessionLocal() as db:
            result = await collect_admin_monitoring(db)
            snapshot = await save_monitoring_snapshot(db, result)
            open_alerts = await sync_monitoring_alerts(db, result)
            result["snapshot_id"] = snapshot.id
            result["open_alerts"] = len(open_alerts)
            return result
    finally:
        await engine.dispose()


@shared_task(bind=True, name="monitoring.system_check")
def system_check_task(self) -> Dict[str, Any]:
    """定时采集监测快照，同步告警并返回 Celery result。"""
    try:
        result = asyncio.run(_collect())
        logger.info("后台监测完成: %s", result.get("overall"))
        return result
    except Exception as exc:
        logger.exception("后台监测失败: %s", exc)
        self.retry(exc=exc, countdown=120, max_retries=2)


async def _cleanup_api_request_logs(days: int) -> Dict[str, Any]:
    cutoff = utcnow() - timedelta(days=days)
    try:
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                delete(ApiRequestLog).where(ApiRequestLog.created_at < cutoff)
            )
            await db.commit()
            return {"retention_days": days, "deleted": result.rowcount or 0}
    finally:
        await engine.dispose()


@shared_task(bind=True, name="monitoring.cleanup_api_request_logs")
def cleanup_api_request_logs_task(self, days: int = 30) -> Dict[str, Any]:
    """清理接口健康请求日志，避免生产库无限增长。"""
    try:
        result = asyncio.run(_cleanup_api_request_logs(days))
        logger.info("API 请求监测日志清理完成: %s", result)
        return result
    except Exception as exc:
        logger.exception("API 请求监测日志清理失败: %s", exc)
        self.retry(exc=exc, countdown=300, max_retries=2)


async def _cleanup_llm_call_logs(days: int) -> Dict[str, Any]:
    cutoff = utcnow() - timedelta(days=days)
    try:
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                delete(LlmCallLog).where(LlmCallLog.created_at < cutoff)
            )
            await db.commit()
            return {"retention_days": days, "deleted": result.rowcount or 0}
    finally:
        await engine.dispose()


@shared_task(bind=True, name="monitoring.cleanup_llm_call_logs")
def cleanup_llm_call_logs_task(self, days: int = 90) -> Dict[str, Any]:
    """清理 LLM 调用日志，保留足够成本趋势历史。"""
    try:
        result = asyncio.run(_cleanup_llm_call_logs(days))
        logger.info("LLM 调用成本日志清理完成: %s", result)
        return result
    except Exception as exc:
        logger.exception("LLM 调用成本日志清理失败: %s", exc)
        self.retry(exc=exc, countdown=300, max_retries=2)
