"""预处理 Celery 任务：RawInfo → InfoCluster。"""

import asyncio
import logging
from typing import Any, Dict

from celery import shared_task

from app.db.session import AsyncSessionLocal
from app.services.preprocess import preprocess_pipeline

logger = logging.getLogger(__name__)


async def _run(limit: int) -> Dict[str, Any]:
    async with AsyncSessionLocal() as db:
        return await preprocess_pipeline.run_batch(db, limit=limit)


@shared_task(bind=True, name="preprocess.run_batch")
def run_batch_task(self, limit: int = 100):
    """批处理：拉一批 pending RawInfo → 聚类 → 富集 → 落库。"""
    try:
        result = asyncio.run(_run(limit))
        return result
    except Exception as e:
        logger.error(f"preprocess 失败: {e}")
        self.retry(exc=e, countdown=120, max_retries=2)
