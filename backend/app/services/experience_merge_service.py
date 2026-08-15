"""经验库语义重合检测与合并。

设计原则：只做"找出重合 + 人工确认合并"，不做自动去重。
合并时保留一条正式经验作为合并后的版本，其余来源标记为 merged 并隐藏，
保留来源追溯，不删除任何记录。
"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.content_version import ExperienceCard
from app.services.experience_service import (
    build_card_payload,
    cosine_similarity,
    enqueue_embedding,
)
from app.services.llm.llm_client import (
    ChatMessage,
    LLMClient,
    get_llm_client,
    parse_json_loose,
)

logger = logging.getLogger(__name__)

# 重合检测阈值：高于此值的配对会被归入同一组。
OVERLAP_THRESHOLD = 0.78
# 单条经验"相似经验"面板的阈值。
SIMILAR_THRESHOLD = 0.5
# 一次最多扫描多少条正式经验，避免全库过大时 O(n^2) 失控。
OVERLAP_SCAN_LIMIT = 500
MAX_MERGE_SOURCES = 10
MAX_MERGE_SOURCE_CHARS = 4_000
MAX_MERGED_CONTENT_CHARS = 50_000


class ExperienceMergeError(RuntimeError):
    """合并流程中的可预期错误（参数不合法、状态不对等）。"""


_TOKEN_RE = re.compile(r"[\u4e00-\u9fff]{2,8}|[A-Za-z0-9][A-Za-z0-9_-]{2,}")


def _tokenize(card: ExperienceCard) -> set[str]:
    haystack = " ".join(
        value or "" for value in (card.title, card.content, card.category)
    ).casefold()
    return set(_TOKEN_RE.findall(haystack))


def _keyword_similarity(left: set[str], right: set[str]) -> float:
    if not left or not right:
        return 0.0
    return len(left & right) / len(left | right)


def _pair_similarity(left: ExperienceCard, right: ExperienceCard, left_tokens: set[str], right_tokens: set[str]) -> tuple[float, str]:
    """返回 (相似度, 方法)；优先用 embedding，缺失时降级关键词。"""

    if left.embedding and right.embedding:
        score = cosine_similarity(left.embedding, right.embedding)
        if score >= 0.01:
            return score, "semantic"
    keyword = _keyword_similarity(left_tokens, right_tokens)
    return keyword, "keyword_fallback"


class _UnionFind:
    def __init__(self, size: int) -> None:
        self.parent = list(range(size))

    def find(self, x: int) -> int:
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]
            x = self.parent[x]
        return x

    def union(self, a: int, b: int) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.parent[rb] = ra


async def _load_confirmed_cards(db: AsyncSession, limit: int) -> list[ExperienceCard]:
    result = await db.execute(
        select(ExperienceCard)
        .where(ExperienceCard.status == "confirmed")
        .options(
            selectinload(ExperienceCard.creator),
            selectinload(ExperienceCard.creation),
            selectinload(ExperienceCard.suggestion),
        )
        .order_by(ExperienceCard.created_at.desc(), ExperienceCard.id.desc())
        .limit(limit)
    )
    return list(result.scalars().all())


def _card_brief(card: ExperienceCard) -> dict[str, Any]:
    return {
        "id": card.id,
        "title": card.title,
        "category": card.category,
        "source_type": card.source_type,
        "content_preview": (card.content or "")[:120],
        "created_at": card.created_at.isoformat() if card.created_at else None,
    }


async def find_overlapping_cards(
    db: AsyncSession,
    *,
    threshold: float = OVERLAP_THRESHOLD,
    scan_limit: int = OVERLAP_SCAN_LIMIT,
) -> list[dict[str, Any]]:
    """扫描正式经验，按语义相似度返回重合分组（每组至少 2 条）。"""

    cards = await _load_confirmed_cards(db, scan_limit)
    if len(cards) < 2:
        return []

    tokens = [_tokenize(card) for card in cards]
    uf = _UnionFind(len(cards))
    pair_records: list[dict[str, Any]] = []

    for i in range(len(cards)):
        for j in range(i + 1, len(cards)):
            score, method = _pair_similarity(cards[i], cards[j], tokens[i], tokens[j])
            if score >= threshold:
                uf.union(i, j)
                pair_records.append(
                    {"a": cards[i].id, "b": cards[j].id, "similarity": round(score, 4), "method": method}
                )

    groups: dict[int, list[int]] = {}
    for idx in range(len(cards)):
        root = uf.find(idx)
        groups.setdefault(root, []).append(idx)

    result: list[dict[str, Any]] = []
    pair_by_key = {(p["a"], p["b"]): p for p in pair_records}
    for member_indexes in groups.values():
        if len(member_indexes) < 2:
            continue
        member_cards = [cards[i] for i in member_indexes]
        member_ids = {card.id for card in member_cards}
        group_pairs = [
            p for p in pair_records
            if p["a"] in member_ids and p["b"] in member_ids
        ]
        max_similarity = max((p["similarity"] for p in group_pairs), default=0.0)
        member_cards.sort(key=lambda c: (c.created_at or datetime.min, c.id), reverse=True)
        result.append(
            {
                "cards": [_card_brief(card) for card in member_cards],
                "pairs": group_pairs,
                "max_similarity": max_similarity,
            }
        )

    result.sort(key=lambda g: g["max_similarity"], reverse=True)
    return result


async def find_similar_cards(
    db: AsyncSession,
    card_id: int,
    *,
    limit: int = 6,
    threshold: float = SIMILAR_THRESHOLD,
) -> list[dict[str, Any]]:
    """为单条经验找相似的正式经验（详情面板用）。"""

    target = (
        await db.execute(
            select(ExperienceCard)
            .where(ExperienceCard.id == card_id)
            .options(
                selectinload(ExperienceCard.creator),
                selectinload(ExperienceCard.creation),
                selectinload(ExperienceCard.suggestion),
            )
        )
    ).scalar_one_or_none()
    if target is None:
        return []

    others = await _load_confirmed_cards(db, OVERLAP_SCAN_LIMIT)
    target_tokens = _tokenize(target)
    scored: list[tuple[ExperienceCard, float, str]] = []
    for card in others:
        if card.id == target.id:
            continue
        score, method = _pair_similarity(target, card, target_tokens, _tokenize(card))
        if score >= threshold:
            scored.append((card, score, method))

    scored.sort(key=lambda item: (item[1], item[0].created_at or datetime.min), reverse=True)
    return [
        {
            **build_card_payload(card, creator=card.creator, source_creation=card.creation, suggestion=card.suggestion),
            "similarity": round(score, 4),
            "match_method": method,
        }
        for card, score, method in scored[:limit]
    ]


async def _load_merge_sources(db: AsyncSession, source_ids: list[int]) -> list[ExperienceCard]:
    if len(source_ids) < 2:
        raise ExperienceMergeError("至少选择两条经验才能合并")
    if len(source_ids) > MAX_MERGE_SOURCES:
        raise ExperienceMergeError(f"一次最多合并 {MAX_MERGE_SOURCES} 条经验")

    rows = (
        await db.execute(
            select(ExperienceCard)
            .where(ExperienceCard.id.in_(source_ids))
            .options(
                selectinload(ExperienceCard.creator),
                selectinload(ExperienceCard.creation),
                selectinload(ExperienceCard.suggestion),
            )
        )
    ).scalars().all()
    by_id = {card.id: card for card in rows}
    missing = [sid for sid in source_ids if sid not in by_id]
    if missing:
        raise ExperienceMergeError(f"经验不存在：{', '.join(str(i) for i in missing)}")
    invalid = [card.id for card in rows if card.status != "confirmed"]
    if invalid:
        raise ExperienceMergeError("只有正式经验可以合并，待确认或已合并的经验请先处理")
    return [by_id[sid] for sid in source_ids]


def _build_merge_system_prompt() -> str:
    return """
你是一个负责整理团队经验库的资深编辑。下面会给你 2 条或多条在语义上重合的经验，
你的任务是把它们合并成一条更完整、更可复用的经验，而不是简单拼接或去重。

要求：
1. 保留每条经验中真正不同、独有价值的判断和做法；互相重复的内容只保留一份最清楚的表述。
2. 不要编造原材料里没有的事实、案例或数据。
3. 合并后的正文用简洁的要点或短句，便于以后被检索和引用。
4. 标题用一句话概括这条合并后经验的核心判断，不超过 40 个字。
5. 分类从原分类里选一个最贴切的；如果都不合适可以留空。

只输出严格 JSON，不要 Markdown 或解释：
{"title": "...", "content": "...", "category": "..."}
""".strip()


async def preview_merge_experiences(
    db: AsyncSession,
    source_ids: list[int],
    *,
    llm_client: Optional[LLMClient] = None,
) -> dict[str, Any]:
    """调用 LLM 生成合并草稿，不写库。"""

    sources = await _load_merge_sources(db, source_ids)
    payload = [
        {
            "id": card.id,
            "title": card.title,
            "category": card.category,
            "content": (card.content or "")[:MAX_MERGE_SOURCE_CHARS],
        }
        for card in sources
    ]
    client = llm_client or get_llm_client()
    result = await client.chat(
        [
            ChatMessage(role="system", content=_build_merge_system_prompt()),
            ChatMessage(role="user", content=json.dumps(payload, ensure_ascii=False)),
        ],
        temperature=0.2,
        max_tokens=4_000,
        json_mode=True,
    )
    raw = result.text or ""
    parsed = result.parsed if isinstance(result.parsed, dict) else parse_json_loose(raw)
    if not isinstance(parsed, dict):
        raise ExperienceMergeError("模型没有返回有效的合并结果，请稍后重试或手动编辑")

    title = str(parsed.get("title") or "").strip()[:200]
    content = str(parsed.get("content") or "").strip()[:MAX_MERGED_CONTENT_CHARS]
    category = str(parsed.get("category") or "").strip()[:50] or None
    if not title or not content:
        raise ExperienceMergeError("模型生成的标题或正文为空，请手动编辑后再保存")

    return {
        "title": title,
        "content": content,
        "category": category,
        "source_ids": [card.id for card in sources],
        "source_count": len(sources),
    }


async def merge_experiences(
    db: AsyncSession,
    source_ids: list[int],
    *,
    surviving_id: Optional[int],
    title: str,
    content: str,
    category: Optional[str],
) -> ExperienceCard:
    """确认合并：更新保留卡为合并版本，其余来源标记为 merged。"""

    sources = await _load_merge_sources(db, source_ids)
    ordered_ids = [card.id for card in sources]
    if surviving_id is None or surviving_id not in ordered_ids:
        # 默认保留最近创建的一条。
        surviving_id = ordered_ids[0]

    survivor = next(card for card in sources if card.id == surviving_id)
    merged_away = [card for card in sources if card.id != surviving_id]

    merged_from = []
    now = datetime.now(timezone.utc).isoformat()
    for card in merged_away:
        meta = dict(card.source_meta or {})
        meta["merged_into"] = surviving_id
        meta["merged_at"] = now
        card.source_meta = meta
        card.status = "merged"
        merged_from.append(
            {
                "id": card.id,
                "title": card.title,
                "category": card.category,
                "source_type": card.source_type,
            }
        )

    survivor_meta = dict(survivor.source_meta or {})
    prior = survivor_meta.get("merged_from")
    if isinstance(prior, list):
        # 已经合并过的卡再次合并：把历史来源也带上，去重。
        seen = {item.get("id") for item in prior if isinstance(item, dict)}
        for item in merged_from:
            if item["id"] not in seen:
                prior.append(item)
        survivor_meta["merged_from"] = prior
    else:
        survivor_meta["merged_from"] = merged_from
    survivor_meta["merged_at"] = now

    survivor.title = title.strip()[:200]
    survivor.content = content.strip()[:MAX_MERGED_CONTENT_CHARS]
    survivor.category = (category.strip()[:50] or None) if category else None
    survivor.source_meta = survivor_meta
    survivor.embedding = None
    survivor.embedding_status = "pending"
    survivor.embedding_error = None
    survivor.embedding_task_id = None

    await db.commit()
    await db.refresh(survivor)
    await enqueue_embedding(survivor, db)
    return survivor
