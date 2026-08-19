"""飞书内容资讯日报 Celery 任务。"""

import asyncio
import logging

from celery import shared_task

from app.core.config import settings
from app.db.session import AsyncSessionLocal, engine
from app.services.feishu_digest import collect_digest_records, sync_digest_records, translate_digest_records

logger = logging.getLogger(__name__)


async def _publish(wave: str) -> dict:
    try:
        async with AsyncSessionLocal() as db:
            window, records = await collect_digest_records(db, wave)
        translation = (
            await translate_digest_records(records)
            if settings.FEISHU_DIGEST_TRANSLATE_ENGLISH
            else {"candidate_records": 0, "translated_records": 0, "disabled": 1}
        )
        result = await sync_digest_records(records)
        categories: dict[str, int] = {}
        for record in records:
            category = record["category"]
            categories[category] = categories.get(category, 0) + 1
        return {
            "status": "ok",
            "wave": wave,
            "batch": window.batch_key,
            "window_start": window.start.isoformat(),
            "window_end": window.end.isoformat(),
            "categories": categories,
            "translation": translation,
            **result,
        }
    finally:
        await engine.dispose()


@shared_task(bind=True, name="feishu_digest.publish")
def publish_feishu_digest_task(self, wave: str):
    if not settings.FEISHU_DIGEST_ENABLED:
        return {"status": "disabled", "wave": wave}
    try:
        result = asyncio.run(_publish(wave))
        logger.info("飞书资讯日报完成: %s", result)
        return result
    except Exception as exc:
        logger.exception("飞书资讯日报失败: wave=%s", wave)
        raise self.retry(exc=exc, countdown=60, max_retries=2)
