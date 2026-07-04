"""后台监测 Celery 任务。"""

import asyncio
import logging
from typing import Any, Dict

from celery import shared_task

from app.db.session import AsyncSessionLocal, engine
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
