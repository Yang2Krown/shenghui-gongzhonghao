"""跨会议方法论的保守语义归并。

原始会议沉淀仍保存在 meeting_syntheses.methodology/checklist 中；本模块只维护
一个可重建的“主方法论簇 + 来源会议”投影，避免重复会议把首页汇总越堆越长。
"""

from __future__ import annotations

import hashlib
import json
import logging
import math
import re
from difflib import SequenceMatcher
from typing import Any, Iterable, Optional

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.meeting_methodology import (
    MeetingMethodologyCluster,
    MeetingMethodologySource,
)
from app.services.llm import embedding_service
from app.services.llm.llm_client import ChatMessage, get_llm_client, parse_json_loose
from app.services.meeting_synthesis import classify_methodology_category

logger = logging.getLogger(__name__)

METHODOLOGY_SECTION = "methodology"
CHECKLIST_SECTION = "checklist"
DEDUP_SECTIONS = (METHODOLOGY_SECTION, CHECKLIST_SECTION)

# 这是保守的起始阈值，不把相近主题直接合并。真实数据积累后仍可调参。
AUTO_MERGE_SIMILARITY = 0.90
LLM_REVIEW_SIMILARITY = 0.82
MAX_EMBED_TEXT_LENGTH = 1800


def _value(value: Any) -> str:
    if value is None or isinstance(value, (dict, list)):
        return ""
    return re.sub(r"\s+", " ", str(value)).strip()


def methodology_item_text(item: dict, section: str) -> str:
    """构造 embedding 文本；只放原则本身和上下文，不放会议编号等噪声。"""
    if section == METHODOLOGY_SECTION:
        fields = (
            ("标题", item.get("title")),
            ("规则", item.get("rule")),
            ("原因", item.get("rationale")),
            ("场景", item.get("example")),
            ("依据", item.get("evidence")),
        )
    else:
        fields = (
            ("清单", item.get("item")),
            ("说明", item.get("description")),
            ("时机", item.get("when_to_use")),
        )
    text = "\n".join(f"{label}：{_value(value)}" for label, value in fields if _value(value))
    return text[:MAX_EMBED_TEXT_LENGTH]


def methodology_item_fingerprint(item: dict, section: str) -> str:
    normalized = methodology_item_text(item, section).lower()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


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


def lexical_similarity(left: str, right: str) -> float:
    """embedding 不可用时的保守兜底，不把它冒充成语义相似度。"""
    left = re.sub(r"[^\w\u4e00-\u9fff]", "", left.lower())
    right = re.sub(r"[^\w\u4e00-\u9fff]", "", right.lower())
    if not left or not right:
        return 0.0
    if left == right:
        return 1.0
    left_grams = {left[index:index + 2] for index in range(max(0, len(left) - 1))}
    right_grams = {right[index:index + 2] for index in range(max(0, len(right) - 1))}
    union = left_grams | right_grams
    jaccard = len(left_grams & right_grams) / len(union) if union else 0.0
    sequence = SequenceMatcher(None, left, right).ratio()
    return 0.65 * jaccard + 0.35 * sequence


def _cluster_item(cluster: MeetingMethodologyCluster) -> dict:
    if cluster.section == METHODOLOGY_SECTION:
        return {
            "title": cluster.title,
            "rule": cluster.rule,
            "rationale": cluster.rationale,
            "example": cluster.example,
            "evidence": cluster.evidence,
        }
    return {
        "item": cluster.title,
        "description": cluster.rule,
        "when_to_use": cluster.rationale,
    }


def _item_richness(item: dict, section: str) -> int:
    fields = (
        ("title", "rule", "rationale", "example", "evidence")
        if section == METHODOLOGY_SECTION
        else ("item", "description", "when_to_use")
    )
    return sum(len(_value(item.get(field))) for field in fields)


def _merge_richer_content(
    cluster: MeetingMethodologyCluster,
    item: dict,
    section: str,
) -> None:
    """补充更完整的上下文；主簇被人工编辑后不再自动改写。"""
    if cluster.is_manually_edited:
        return
    current = _cluster_item(cluster)
    if _item_richness(item, section) <= _item_richness(current, section):
        return
    if section == METHODOLOGY_SECTION:
        if len(_value(item.get("rule"))) > len(_value(cluster.rule)):
            cluster.rule = _value(item.get("rule"))
        for field in ("rationale", "example", "evidence"):
            if not _value(getattr(cluster, field)) and _value(item.get(field)):
                setattr(cluster, field, _value(item.get(field)))
    else:
        if len(_value(item.get("description"))) > len(_value(cluster.rule)):
            cluster.rule = _value(item.get("description"))
        if not _value(cluster.rationale) and _value(item.get("when_to_use")):
            cluster.rationale = _value(item.get("when_to_use"))


def _average_vector(
    old: Optional[Iterable[float]],
    new: Optional[Iterable[float]],
    count: int,
) -> Optional[list[float]]:
    if new is None:
        return list(old) if old is not None else None
    new_values = list(new)
    if old is None:
        return new_values
    old_values = list(old)
    if len(old_values) != len(new_values):
        return old_values
    divisor = max(1, count)
    return [((value * divisor) + incoming) / (divisor + 1) for value, incoming in zip(old_values, new_values)]


async def _embed(texts: list[str], embedder: Any = None) -> list[Optional[list[float]]]:
    if not texts:
        return []
    service = embedder or embedding_service
    try:
        values = await service.embed_batch(texts)
        return [list(value) if value else None for value in values]
    except Exception as exc:
        # embedding 失败不能让会议整理失败；后续仍保留原始沉淀并走保守兜底。
        logger.warning("会议方法论 embedding 失败，降级为文本相似度：%s", exc)
        return [None] * len(texts)


async def _llm_judge(
    item: dict,
    section: str,
    cluster: MeetingMethodologyCluster,
    *,
    llm_client: Any = None,
) -> tuple[bool, float]:
    """只判断边界候选是否为同一原则，不让 LLM 重写原始方法论。"""
    system = (
        "你是内部方法论去重审核员。只判断两条内容是否表达同一个可复用原则。"
        "不要因为它们属于同一大类、共享一个关键词或一个是另一个的例子就判定重复。"
        "如果范围、前置条件、使用时机或结论不同，应判定为不同。只输出 JSON。"
    )
    user = {
        "new_item": {"section": section, **item},
        "existing_item": {"section": cluster.section, **_cluster_item(cluster)},
        "output": {
            "same_principle": "boolean",
            "confidence": "0-1 number",
        },
    }
    try:
        client = llm_client or get_llm_client()
        result = await client.chat(
            [
                ChatMessage(role="system", content=system),
                ChatMessage(role="user", content=json.dumps(user, ensure_ascii=False)),
            ],
            temperature=0.0,
            max_tokens=220,
            json_mode=True,
        )
        parsed = result.parsed if isinstance(result.parsed, dict) else parse_json_loose(result.text or "")
        if not isinstance(parsed, dict):
            return False, 0.0
        same = parsed.get("same_principle") is True
        confidence = float(parsed.get("confidence") or 0.0)
        return same and confidence >= 0.75, max(0.0, min(confidence, 1.0))
    except Exception as exc:
        logger.info("方法论边界去重未调用 LLM 或调用失败：%s", exc)
        return False, 0.0


def _source_seen(
    sources: list[MeetingMethodologySource],
    meeting_id: int,
    section: str,
) -> set[tuple[str, str]]:
    return {
        (source.section, source.source_fingerprint)
        for source in sources
        if source.meeting_id == meeting_id and source.section == section
    }


async def sync_methodology_clusters(
    db: AsyncSession,
    meeting_id: int,
    synthesis: dict,
    *,
    generate_embeddings: bool = True,
    judge_borderline: bool = True,
    embedder: Any = None,
    llm_client: Any = None,
) -> dict:
    """幂等地把一场会议的方法论/清单归入跨会议主簇。"""
    records: list[dict] = []
    for section in DEDUP_SECTIONS:
        for item in synthesis.get(section) or []:
            if not isinstance(item, dict):
                continue
            text = methodology_item_text(item, section)
            if not text:
                continue
            category = classify_methodology_category(item)["key"]
            records.append({
                "section": section,
                "category": category,
                "item": item,
                "text": text,
                "fingerprint": methodology_item_fingerprint(item, section),
            })

    # 同一轮模型输出里完全相同的条目只处理一次。
    unique_records: list[dict] = []
    seen_fingerprints: set[tuple[str, str]] = set()
    for record in records:
        key = (record["section"], record["fingerprint"])
        if key in seen_fingerprints:
            continue
        seen_fingerprints.add(key)
        unique_records.append(record)
    records = unique_records
    if not records:
        return {"source_count": 0, "new_clusters": 0, "merged": 0, "reviewed": 0}

    source_rows = (await db.scalars(
        select(MeetingMethodologySource).where(
            MeetingMethodologySource.meeting_id == meeting_id,
        )
    )).all()
    seen_sources = _source_seen(source_rows, meeting_id, METHODOLOGY_SECTION) | _source_seen(
        source_rows, meeting_id, CHECKLIST_SECTION
    )
    records = [
        record for record in records
        if (record["section"], record["fingerprint"]) not in seen_sources
    ]
    if not records:
        return {"source_count": 0, "new_clusters": 0, "merged": 0, "reviewed": 0}

    clusters = (await db.scalars(
        select(MeetingMethodologyCluster)
        .where(MeetingMethodologyCluster.status == "active")
        .options(selectinload(MeetingMethodologyCluster.sources))
        .order_by(MeetingMethodologyCluster.id)
    )).all()

    missing_cluster_embeddings = [
        cluster for cluster in clusters
        if not cluster.embedding and cluster.normalized_text
    ]
    embedding_texts = [record["text"] for record in records]
    if generate_embeddings:
        embedding_texts += [cluster.normalized_text for cluster in missing_cluster_embeddings]
    vectors = await _embed(embedding_texts, embedder=embedder) if generate_embeddings else [None] * len(embedding_texts)
    record_vectors = vectors[:len(records)]
    if generate_embeddings:
        for cluster, vector in zip(missing_cluster_embeddings, vectors[len(records):]):
            if vector:
                cluster.embedding = vector

    stats = {"source_count": 0, "new_clusters": 0, "merged": 0, "reviewed": 0}
    pending_clusters = list(clusters)
    for record, vector in zip(records, record_vectors):
        section = record["section"]
        category = record["category"]
        item = record["item"]
        candidates = [
            cluster for cluster in pending_clusters
            if cluster.section == section and cluster.category == category and cluster.status == "active"
        ]

        best_cluster: Optional[MeetingMethodologyCluster] = None
        best_score = 0.0
        best_kind = "lexical"
        for cluster in candidates:
            if cluster.canonical_fingerprint == record["fingerprint"]:
                best_cluster = cluster
                best_score = 1.0
                best_kind = "exact"
                break
            if vector and cluster.embedding:
                score = cosine_similarity(vector, cluster.embedding)
                kind = "embedding"
            else:
                score = lexical_similarity(record["text"], cluster.normalized_text)
                kind = "lexical"
            if score > best_score:
                best_cluster, best_score, best_kind = cluster, score, kind

        matched = False
        match_kind = best_kind
        if best_cluster is not None and best_score >= AUTO_MERGE_SIMILARITY:
            matched = True
        elif (
            best_cluster is not None
            and best_score >= LLM_REVIEW_SIMILARITY
            and judge_borderline
        ):
            matched, _ = await _llm_judge(
                item,
                section,
                best_cluster,
                llm_client=llm_client,
            )
            if matched:
                match_kind = "llm"
                stats["reviewed"] += 1

        if matched and best_cluster is not None:
            cluster = best_cluster
            _merge_richer_content(cluster, item, section)
            cluster.embedding = _average_vector(
                cluster.embedding,
                vector,
                cluster.source_count or 1,
            )
            source = MeetingMethodologySource(
                cluster=cluster,
                meeting_id=meeting_id,
                section=section,
                source_fingerprint=record["fingerprint"],
                item=item,
                similarity=best_score,
                match_kind=match_kind,
                is_primary=False,
            )
            db.add(source)
            cluster.source_count = (cluster.source_count or 0) + 1
            stats["merged"] += 1
        else:
            title = _value(item.get("title") if section == METHODOLOGY_SECTION else item.get("item"))
            rule = _value(item.get("rule") if section == METHODOLOGY_SECTION else item.get("description"))
            cluster = MeetingMethodologyCluster(
                section=section,
                category=category,
                title=title[:200] or "未命名方法",
                rule=rule or title or "未命名沉淀",
                rationale=_value(item.get("rationale") if section == METHODOLOGY_SECTION else item.get("when_to_use")) or None,
                example=_value(item.get("example")) or None,
                evidence=_value(item.get("evidence")) or None,
                normalized_text=record["text"],
                canonical_fingerprint=record["fingerprint"],
                embedding=vector,
                source_count=1,
                status="active",
            )
            db.add(cluster)
            db.add(MeetingMethodologySource(
                cluster=cluster,
                meeting_id=meeting_id,
                section=section,
                source_fingerprint=record["fingerprint"],
                item=item,
                similarity=1.0,
                match_kind="new",
                is_primary=True,
            ))
            pending_clusters.append(cluster)
            stats["new_clusters"] += 1
        stats["source_count"] += 1

    await db.flush()
    return stats


async def backfill_missing_methodology_clusters(
    db: AsyncSession,
    meetings: Iterable[Any],
) -> dict:
    """为 Phase 1b 已存在的 JSON 沉淀补建来源投影，不在 GET 请求中调用外部模型。"""
    stats = {"source_count": 0, "new_clusters": 0, "merged": 0, "reviewed": 0}
    changed = False
    for meeting in meetings:
        synthesis = getattr(meeting, "synthesis", None)
        if synthesis is None:
            continue
        result = await sync_methodology_clusters(
            db,
            meeting.id,
            {
                "methodology": synthesis.methodology or [],
                "checklist": synthesis.checklist or [],
            },
            generate_embeddings=False,
            judge_borderline=False,
        )
        for key, value in result.items():
            stats[key] += value
        changed = changed or bool(result["source_count"])
    if changed:
        await db.flush()
    return stats


async def prune_orphan_methodology_clusters(db: AsyncSession) -> int:
    """删除会议级联后不再有任何来源的主簇，并校正来源计数。"""
    rows = (await db.execute(
        select(
            MeetingMethodologyCluster.id,
            func.count(MeetingMethodologySource.id),
        )
        .outerjoin(
            MeetingMethodologySource,
            MeetingMethodologySource.cluster_id == MeetingMethodologyCluster.id,
        )
        .group_by(MeetingMethodologyCluster.id)
    )).all()
    deleted = 0
    for cluster_id, source_count in rows:
        if source_count == 0:
            await db.execute(
                delete(MeetingMethodologyCluster).where(
                    MeetingMethodologyCluster.id == cluster_id
                )
            )
            deleted += 1
        else:
            await db.execute(
                update(MeetingMethodologyCluster)
                .where(MeetingMethodologyCluster.id == cluster_id)
                .values(source_count=source_count)
            )
    if rows:
        await db.flush()
    return deleted
