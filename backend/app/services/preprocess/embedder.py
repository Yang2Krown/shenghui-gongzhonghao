"""批量生成 RawInfo.embedding。"""

import logging
from typing import List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.raw_info import RawInfo
from app.services.llm import embedding_service

logger = logging.getLogger(__name__)


def _build_embed_text(raw: RawInfo) -> str:
    """构造用于 embedding 的文本：title + summary 截断到 1500 字。"""
    parts = []
    if raw.title:
        parts.append(raw.title.strip())
    if raw.summary:
        s = raw.summary.strip()
        if s and s.lower() != (raw.title or "").strip().lower():
            parts.append(s[:1200])
    return "\n".join(parts)[:1500]


async def embed_raw_infos(db: AsyncSession, raws: List[RawInfo]) -> int:
    """给一批 RawInfo 生成 embedding 并 flush。返回成功数。"""
    pending = [r for r in raws if r.embedding is None and (r.title or r.summary)]
    if not pending:
        return 0

    texts = [_build_embed_text(r) for r in pending]
    vectors = await embedding_service.embed_batch(texts)

    success = 0
    for raw, vec in zip(pending, vectors):
        if vec is not None:
            raw.embedding = vec
            success += 1
        else:
            logger.warning(f"RawInfo id={raw.id} embedding 失败，保留 None")

    await db.flush()
    logger.info(f"embed: {success}/{len(pending)} 成功")
    return success
