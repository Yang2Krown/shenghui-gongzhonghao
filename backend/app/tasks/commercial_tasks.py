"""Commercial detection Celery tasks."""

import asyncio
import logging
from typing import Any, Dict, List, Optional

from celery import shared_task
from sqlalchemy import select

from app.db.session import AsyncSessionLocal, engine
from app.models.raw_info import RawInfo
from app.services.commercial_detection import detect_commercial_article

logger = logging.getLogger(__name__)


async def _detect_one(raw_info_id: int, *, force_llm: bool = False) -> Dict[str, Any]:
    try:
        async with AsyncSessionLocal() as db:
            raw = (
                await db.execute(select(RawInfo).where(RawInfo.id == raw_info_id))
            ).scalar_one_or_none()
            if not raw:
                return {"raw_info_id": raw_info_id, "status": "missing"}

            result = await detect_commercial_article(
                title=raw.title or "",
                summary=raw.summary or "",
                content=raw.content or "",
                force_llm=force_llm,
            )
            raw.commercial_level = result.level
            raw.commercial_meta = result.to_meta()
            await db.commit()

            logger.info(
                "商单检测完成 raw_info_id=%s level=%s product=%s",
                raw_info_id,
                result.level,
                result.product,
            )
            return {
                "raw_info_id": raw_info_id,
                "status": "ok",
                "commercial_level": result.level,
                "commercial_meta": result.to_meta(),
            }
    finally:
        await engine.dispose()


async def _detect_batch(raw_info_ids: List[int], *, force_llm: bool = False) -> Dict[str, Any]:
    results = []
    for raw_info_id in raw_info_ids:
        try:
            results.append(await _detect_one(raw_info_id, force_llm=force_llm))
        except Exception as exc:
            logger.exception("商单检测失败 raw_info_id=%s", raw_info_id)
            results.append({"raw_info_id": raw_info_id, "status": "failed", "error": str(exc)})
    return {
        "total": len(raw_info_ids),
        "ok": sum(1 for r in results if r.get("status") == "ok"),
        "failed": sum(1 for r in results if r.get("status") == "failed"),
        "missing": sum(1 for r in results if r.get("status") == "missing"),
        "results": results,
    }


@shared_task(bind=True, name="commercial.detect_raw_info")
def detect_commercial_task(self, raw_info_id: int, force_llm: bool = False):
    """Detect commercial signals for a single RawInfo row."""
    try:
        return asyncio.run(_detect_one(raw_info_id, force_llm=force_llm))
    except Exception as exc:
        logger.error("商单检测任务失败 raw_info_id=%s: %s", raw_info_id, exc)
        self.retry(exc=exc, countdown=60, max_retries=2)


@shared_task(bind=True, name="commercial.detect_raw_infos")
def detect_commercial_batch_task(
    self,
    raw_info_ids: Optional[List[int]] = None,
    force_llm: bool = False,
):
    """Detect commercial signals for a batch of RawInfo rows."""
    try:
        return asyncio.run(_detect_batch(raw_info_ids or [], force_llm=force_llm))
    except Exception as exc:
        logger.error("商单批量检测任务失败: %s", exc)
        self.retry(exc=exc, countdown=60, max_retries=2)
