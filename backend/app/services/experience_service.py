"""经验卡片保存、语义检索和 embedding 调度。"""

from __future__ import annotations

import logging
import math
import uuid
from datetime import datetime
from typing import Any, Iterable, Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.content_version import ExperienceCard
from app.models.creation import ContentCreation
from app.models.meeting import MeetingSuggestion
from app.models.user import User
from app.services.llm import embedding_service

logger = logging.getLogger(__name__)


def cosine_similarity(left: Optional[Iterable[float]], right: Optional[Iterable[float]]) -> float:
    if left is None or right is None:
        return 0.0
    left_values = list(left)
    right_values = list(right)
    if not left_values or len(left_values) != len(right_values):
        return 0.0
    left_norm = math.sqrt(sum(value * value for value in left_values))
    right_norm = math.sqrt(sum(value * value for value in right_values))
    if not left_norm or not right_norm:
        return 0.0
    return sum(a * b for a, b in zip(left_values, right_values)) / (left_norm * right_norm)


def pair_matches(pair: Any, before_id: int, after_id: int) -> bool:
    if not isinstance(pair, dict):
        return False
    try:
        return (
            int(pair.get("before")) == int(before_id)
            and int(pair.get("after")) == int(after_id)
        )
    except (TypeError, ValueError):
        return False


def build_card_payload(
    card: ExperienceCard,
    *,
    source_creation: Optional[ContentCreation] = None,
    creator: Optional[User] = None,
    suggestion: Optional[MeetingSuggestion] = None,
    similarity: Optional[float] = None,
    match_method: str = "recent",
    source_accessible: Optional[bool] = None,
) -> dict:
    return {
        "id": card.id,
        "title": card.title,
        "content": card.content,
        "category": card.category,
        "source_type": card.source_type,
        "creation_id": card.creation_id,
        "version_pair": card.version_pair,
        "suggestion_id": card.suggestion_id,
        "created_by": card.created_by,
        "created_by_user": (
            {
                "id": creator.id,
                "username": creator.username,
                "full_name": creator.full_name,
            }
            if creator is not None
            else None
        ),
        "created_at": card.created_at.isoformat() if card.created_at else None,
        "updated_at": card.updated_at.isoformat() if card.updated_at else None,
        "embedding_status": card.embedding_status,
        "embedding_available": bool(card.embedding),
        "embedding_error": card.embedding_error,
        "source_creation": (
            {"id": source_creation.id, "title": source_creation.title}
            if source_creation is not None
            else None
        ),
        "source_accessible": source_accessible,
        "suggestion": (
            {
                "id": suggestion.id,
                "meeting_id": suggestion.meeting_id,
                "content": suggestion.content,
                "category": suggestion.category,
            }
            if suggestion is not None
            else None
        ),
        "similarity": round(similarity, 6) if similarity is not None else None,
        "match_method": match_method,
    }


async def create_experience_card(
    db: AsyncSession,
    *,
    title: str,
    content: str,
    source_type: str,
    created_by: int,
    category: Optional[str] = None,
    creation_id: Optional[int] = None,
    version_pair: Optional[dict] = None,
    suggestion_id: Optional[int] = None,
) -> ExperienceCard:
    card = ExperienceCard(
        title=title.strip(),
        content=content.strip(),
        source_type=source_type,
        created_by=created_by,
        category=category.strip() if category else None,
        creation_id=creation_id,
        version_pair=version_pair,
        suggestion_id=suggestion_id,
        embedding_status="pending",
    )
    db.add(card)
    await db.commit()
    await db.refresh(card)
    return card


async def enqueue_embedding(card: ExperienceCard, db: AsyncSession) -> dict:
    """提交 embedding 任务；提交失败只标记卡片失败，不回滚卡片。"""

    from app.tasks.experience_tasks import generate_experience_embedding_task

    task_id = str(uuid.uuid4())
    try:
        generate_experience_embedding_task.apply_async(
            args=[card.id],
            task_id=task_id,
        )
    except Exception as exc:
        card.embedding_status = "failed"
        card.embedding_error = str(exc)[:1000]
        card.embedding_task_id = task_id
        await db.commit()
        logger.warning("经验卡片 embedding 任务提交失败 card_id=%s: %s", card.id, exc)
        return {
            "status": "failed",
            "task_id": task_id,
            "error": str(exc)[:1000],
        }

    card.embedding_task_id = task_id
    await db.commit()
    return {"status": "queued", "task_id": task_id}


async def load_experience_cards(
    db: AsyncSession,
    *,
    q: Optional[str],
    category: Optional[str],
    page: int,
    page_size: int,
) -> tuple[list[tuple[ExperienceCard, Optional[float], str]], int, str, bool]:
    """返回按检索排序后的卡片、总数、搜索模式和 embedding 可用性。"""

    filters = []
    if category and category.strip():
        filters.append(ExperienceCard.category == category.strip())

    query_text = (q or "").strip()
    if not query_text:
        total = (await db.execute(
            select(func.count(ExperienceCard.id)).where(*filters)
        )).scalar_one()
        rows = (await db.execute(
            select(ExperienceCard)
            .where(*filters)
            .options(
                selectinload(ExperienceCard.creator),
                selectinload(ExperienceCard.creation),
                selectinload(ExperienceCard.suggestion),
            )
            .order_by(ExperienceCard.created_at.desc(), ExperienceCard.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )).scalars().all()
        return [(row, None, "recent") for row in rows], total, "recent", False

    # q 非空时优先尝试 embedding；没有 key、网络失败或返回空向量时只走
    # 本地关键词匹配，不让经验库请求失败。
    query_vector = None
    try:
        query_vector = await embedding_service.embed(query_text)
    except Exception as exc:
        logger.info("经验库 embedding 搜索不可用，降级关键词：%s", exc)

    rows = (await db.execute(
        select(ExperienceCard)
        .where(*filters)
        .options(
            selectinload(ExperienceCard.creator),
            selectinload(ExperienceCard.creation),
            selectinload(ExperienceCard.suggestion),
        )
    )).scalars().all()
    q_lower = query_text.casefold()
    matched: list[tuple[ExperienceCard, Optional[float], str, bool]] = []
    for row in rows:
        haystack = " ".join(
            value or ""
            for value in (row.title, row.content, row.category)
        ).casefold()
        keyword_match = q_lower in haystack
        similarity = cosine_similarity(query_vector, row.embedding) if query_vector and row.embedding else None
        # 0.15 只是召回下限，不把语义分数当成事实；关键词命中始终保留。
        semantic_match = similarity is not None and similarity >= 0.15
        if not keyword_match and not semantic_match:
            continue
        if similarity is not None and keyword_match:
            method = "semantic+keyword"
        elif similarity is not None:
            method = "semantic"
        else:
            method = "keyword_fallback"
        matched.append((row, similarity, method, keyword_match))

    matched.sort(
        key=lambda item: (
            item[1] if item[1] is not None else 0.0,
            1 if item[3] else 0,
            item[0].created_at or datetime.min,
            item[0].id,
        ),
        reverse=True,
    )
    total = len(matched)
    start = (page - 1) * page_size
    sliced = matched[start:start + page_size]
    mode = "semantic" if query_vector is not None else "keyword_fallback"
    return [(row, similarity, method) for row, similarity, method, _ in sliced], total, mode, query_vector is not None
