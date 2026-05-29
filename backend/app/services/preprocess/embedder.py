"""批量生成 RawInfo.embedding。

成本优化策略：
1. 跳过已有 embedding 的（幂等）
2. 跳过标题+摘要都为空的
3. 跳过标题过短（< 5 字）的低质量 raw
"""

import logging
from typing import List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.raw_info import RawInfo
from app.services.llm import embedding_service

logger = logging.getLogger(__name__)

# 标题最短长度：低于此值的 raw 不做 embedding（省钱）
MIN_TITLE_LENGTH = 5


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
    pending = []
    skipped_short = 0
    for r in raws:
        if r.embedding is not None:
            continue
        if not (r.title or r.summary):
            continue
        title = (r.title or "").strip()
        if len(title) < MIN_TITLE_LENGTH:
            skipped_short += 1
            continue
        pending.append(r)

    if skipped_short:
        logger.info(f"embed: 跳过 {skipped_short} 条标题过短的 raw")
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
