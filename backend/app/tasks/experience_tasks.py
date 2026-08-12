"""经验卡片异步 embedding 任务。"""

import asyncio
import logging

from sqlalchemy import select

from app.core.celery_app import celery_app
from app.db.session import AsyncSessionLocal
from app.models.content_version import ExperienceCard
from app.services.llm import embedding_service

logger = logging.getLogger(__name__)


async def _run_experience_embedding(card_id: int) -> dict:
    async with AsyncSessionLocal() as db:
        card = (await db.execute(
            select(ExperienceCard).where(ExperienceCard.id == card_id)
        )).scalar_one_or_none()
        if card is None:
            return {"card_id": card_id, "status": "failed", "error": "经验卡片不存在"}
        if card.embedding:
            card.embedding_status = "ready"
            card.embedding_error = None
            await db.commit()
            return {"card_id": card_id, "status": "skipped"}

        card.embedding_status = "pending"
        await db.commit()
        try:
            vector = await embedding_service.embed(card.content)
            if not vector:
                raise RuntimeError("embedding 服务未返回向量")
            card.embedding = list(vector)
            card.embedding_status = "ready"
            card.embedding_error = None
            await db.commit()
            return {"card_id": card_id, "status": "ready"}
        except Exception as exc:
            await db.rollback()
            failed = (await db.execute(
                select(ExperienceCard).where(ExperienceCard.id == card_id)
            )).scalar_one_or_none()
            if failed is not None:
                failed.embedding_status = "failed"
                failed.embedding_error = str(exc)[:1000]
                await db.commit()
            logger.warning("经验卡片 embedding 失败 card_id=%s: %s", card_id, exc)
            return {"card_id": card_id, "status": "failed", "error": str(exc)[:1000]}


@celery_app.task(bind=True, name="experience.embed_card", max_retries=0)
def generate_experience_embedding_task(self, card_id: int) -> dict:
    return asyncio.run(_run_experience_embedding(card_id))
