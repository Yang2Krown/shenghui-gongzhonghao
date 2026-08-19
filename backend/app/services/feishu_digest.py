"""把生产信息池、小红书热点和潜在商单写入飞书多维表格。"""

from __future__ import annotations

import json
import logging
import math
import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Iterable, Optional

import httpx
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.timezone import BJT, utcnow
from app.models.raw_info import RawInfo
from app.models.source_registry import SourceAccount, SourceRegistry
from app.models.xhs import XhsNote, XhsTopicBoard
from app.services.llm import get_llm_client
from app.services.llm.llm_client import ChatMessage, LLMClient, parse_json_loose

logger = logging.getLogger(__name__)

OPEN_HOST = "https://open.feishu.cn"
PUBLIC_XHS_STATUSES = ("ready", "ready_degraded", "synced")
CHINESE_CHAR_RE = re.compile(r"[\u4e00-\u9fff]")
LATIN_CHAR_RE = re.compile(r"[A-Za-z]")
URL_RE = re.compile(r"(?:https?://|www\.)\S+", re.IGNORECASE)

TRANSLATION_SYSTEM_PROMPT = """你是科技和 AI 资讯编辑。把输入中的英文标题和英文摘要翻译成简洁、自然、信息准确的中文。

要求：
1. 保留产品名、公司名、人名和常用技术缩写，如 OpenAI、Claude、GPT、MCP。
2. 标题用中文资讯标题的表达，不添加原文没有的判断。
3. 摘要保留关键事实，不追加分析或推荐。
4. 输入中的空字段仍输出空字符串。
5. 只输出严格 JSON，顺序和 id 与输入一致。

输出格式：
{"translations":[{"id":0,"title_zh":"...","summary_zh":"..."}]}
""".strip()


class FeishuDigestError(RuntimeError):
    """日报生成或飞书写入失败。"""


@dataclass(frozen=True)
class DigestWindow:
    wave: str
    start: datetime
    end: datetime
    batch_time: datetime
    batch_key: str
    label: str


def digest_window(wave: str, run_at: Optional[datetime] = None) -> DigestWindow:
    """上午覆盖昨天下午之后，下午覆盖今天上午之后。"""
    now = (run_at or utcnow()).replace(tzinfo=None)
    if wave == "morning":
        start = (now - timedelta(days=1)).replace(hour=14, minute=30, second=0, microsecond=0)
        batch_time = now.replace(hour=9, minute=30, second=0, microsecond=0)
        label = "上午简报"
        suffix = "am"
    elif wave == "afternoon":
        start = now.replace(hour=9, minute=30, second=0, microsecond=0)
        batch_time = now.replace(hour=14, minute=30, second=0, microsecond=0)
        label = "下午简报"
        suffix = "pm"
    else:
        raise ValueError("wave 必须是 morning 或 afternoon")
    return DigestWindow(
        wave=wave,
        start=start,
        end=now,
        batch_time=batch_time,
        batch_key=f"{now:%Y%m%d}-{suffix}",
        label=label,
    )


SOURCE_GROUPS = {
    "rss": "专业媒体 / RSS",
    "web": "网站与产品动态",
    "github": "GitHub 开源",
    "hackernews": "海外技术社区",
    "reddit": "海外技术社区",
    "v2ex": "中文技术社区",
    "tophub": "全网热榜",
    "gzh_explosive": "公众号低粉爆款",
    "exa_wechat": "微信公众号",
    "sogou_wechat": "微信公众号",
    "dajiala_wechat": "重点公众号",
    "x": "X / Twitter",
    "xhs": "小红书",
    "xhs_daily": "小红书",
}


def source_group(source_type: str) -> str:
    return SOURCE_GROUPS.get((source_type or "").lower(), "其他信息源")


def _text(value: Any, limit: int = 1200) -> str:
    text = " ".join(str(value or "").split())
    return text[:limit]


def needs_chinese_translation(value: Any) -> bool:
    """只识别以英文句子为主的内容。

    短产品名或技术缩写（如 GPT-5、MCP）保留原文，避免过度翻译。
    """
    text = URL_RE.sub("", _text(value, 4000))
    if not text:
        return False
    latin_count = len(LATIN_CHAR_RE.findall(text))
    chinese_count = len(CHINESE_CHAR_RE.findall(text))
    # 四个及以上汉字已足以表明这是中文句子，其中的英文多为产品名或技术缩写。
    if chinese_count >= 4:
        return False
    return latin_count >= 12 and latin_count >= max(1, chinese_count * 3)


def _usable_chinese_translation(value: Any) -> str:
    translated = _text(value, 2000)
    return translated if CHINESE_CHAR_RE.search(translated) else ""


async def translate_digest_records(
    records: list[dict[str, Any]],
    *,
    llm_client: Optional[LLMClient] = None,
    batch_size: Optional[int] = None,
) -> dict[str, int]:
    """在写入飞书前批量翻译英文标题/摘要，中文内容和原文链接不变。

    翻译是非阻断增强：单个批次失败时保留原文，不影响日报入库。
    """
    candidates: list[tuple[int, bool, bool]] = []
    for index, record in enumerate(records):
        translate_title = needs_chinese_translation(record.get("title"))
        translate_summary = needs_chinese_translation(record.get("summary"))
        if translate_title or translate_summary:
            candidates.append((index, translate_title, translate_summary))

    stats = {
        "candidate_records": len(candidates),
        "translated_records": 0,
        "translated_titles": 0,
        "translated_summaries": 0,
        "failed_batches": 0,
    }
    if not candidates:
        return stats

    try:
        client = llm_client or get_llm_client()
    except Exception as exc:
        logger.warning("飞书日报翻译客户端不可用，已保留原文: %s", exc)
        stats["failed_batches"] = 1
        return stats

    size = max(1, batch_size or settings.FEISHU_DIGEST_TRANSLATION_BATCH_SIZE)
    for start in range(0, len(candidates), size):
        batch = candidates[start:start + size]
        items = []
        for local_id, (record_index, translate_title, translate_summary) in enumerate(batch):
            record = records[record_index]
            items.append({
                "id": local_id,
                "title": _text(record.get("title"), 500) if translate_title else "",
                "summary": _text(record.get("summary"), 1200) if translate_summary else "",
            })
        try:
            result = await client.chat(
                messages=[
                    ChatMessage(role="system", content=TRANSLATION_SYSTEM_PROMPT),
                    ChatMessage(
                        role="user",
                        content="请翻译以下条目：\n" + json.dumps(items, ensure_ascii=False),
                    ),
                ],
                temperature=0.2,
                max_tokens=8000,
                json_mode=True,
            )
            parsed = result.parsed or parse_json_loose(result.text)
            translations = parsed.get("translations") if isinstance(parsed, dict) else None
            if not isinstance(translations, list):
                raise ValueError("翻译响应缺少 translations 数组")
        except Exception as exc:
            stats["failed_batches"] += 1
            logger.warning("飞书日报翻译批次失败，已保留原文: start=%s error=%s", start, exc)
            continue

        by_id = {
            item.get("id"): item
            for item in translations
            if isinstance(item, dict) and isinstance(item.get("id"), int)
        }
        for local_id, (record_index, translate_title, translate_summary) in enumerate(batch):
            translated = by_id.get(local_id)
            if not translated:
                continue
            record = records[record_index]
            changed = False
            if translate_title:
                title_zh = _usable_chinese_translation(translated.get("title_zh"))
                if title_zh:
                    record["title"] = title_zh[:500]
                    stats["translated_titles"] += 1
                    changed = True
            if translate_summary:
                summary_zh = _usable_chinese_translation(translated.get("summary_zh"))
                if summary_zh:
                    record["summary"] = summary_zh[:1800]
                    stats["translated_summaries"] += 1
                    changed = True
            if changed:
                stats["translated_records"] += 1

    return stats


def _engagement_total(payload: Any) -> int:
    if not isinstance(payload, dict):
        return 0
    total = 0
    for key in ("read", "view", "like", "likes", "collect", "comment", "share", "hot"):
        value = payload.get(key)
        if isinstance(value, (int, float)):
            total += max(0, int(value))
    return total


def _info_score(raw: RawInfo, source: SourceRegistry) -> float:
    heat = _engagement_total(raw.engagement)
    tier_bonus = max(0, 8 - int(source.tier or 8)) * 0.8
    return float(source.weight or 0) + tier_bonus + math.log10(heat + 1)


def _priority(score: float, *, likely: bool = False) -> str:
    if likely or score >= 10:
        return "高"
    if score >= 6:
        return "中"
    return "低"


def _base_record(
    *,
    category: str,
    title: str,
    summary: str,
    source_name: str,
    source_category: str,
    url: str,
    value: str,
    source_time: Optional[datetime],
    window: DigestWindow,
    entity_key: str,
    metrics: str = "",
    brand: str = "",
    product: str = "",
    evidence: str = "",
    recommendation: str = "",
    angle: str = "",
    heat_score: float = 0,
    commercial_grade: str = "无",
) -> dict[str, Any]:
    push_batch = "上午 09:30" if window.wave == "morning" else "下午 14:30"
    note_parts = [
        f"品牌：{brand}" if brand else "",
        f"产品：{product}" if product else "",
        evidence,
        metrics,
    ]
    return {
        "title": _text(title, 500) or "未命名资讯",
        "collected_at": window.batch_time,
        "source_time": source_time,
        "category": category,
        "source_name": _text(f"{source_category}｜{source_name}", 300),
        "source_category": source_category,
        "summary": _text(summary, 1800),
        "value": value,
        "url": url or "",
        "wave": window.label,
        "push_batch": push_batch,
        "batch": window.batch_key,
        "metrics": _text(metrics, 500),
        "heat_score": max(0, min(100, round(float(heat_score or 0), 1))),
        "brand": _text(brand, 100),
        "product": _text(product, 150),
        "evidence": _text(evidence, 1000),
        "recommendation": _text(recommendation or metrics or evidence or summary, 500),
        "angle": _text(angle or source_category, 500),
        "commercial_grade": commercial_grade,
        "status": "待查看",
        "note": _text("；".join(part for part in note_parts if part), 1800),
        "dedupe_key": f"{window.batch_key}:{category}:{entity_key}",
    }


async def _collect_information(db: AsyncSession, window: DigestWindow, limit: int) -> list[dict[str, Any]]:
    rows = (await db.execute(
        select(
            RawInfo,
            SourceRegistry,
            SourceAccount.display_name.label("account_name"),
        )
        .join(SourceRegistry, SourceRegistry.id == RawInfo.source_registry_id)
        .outerjoin(SourceAccount, SourceAccount.id == RawInfo.source_account_id)
        .where(
            RawInfo.scraped_at >= window.start,
            RawInfo.scraped_at < window.end,
            ~RawInfo.commercial_level.in_(("suspected", "likely")),
            ~SourceRegistry.source_type.in_(("xhs", "xhs_daily")),
        )
        .order_by(desc(RawInfo.scraped_at), desc(RawInfo.id))
        .limit(max(limit * 6, limit))
    )).all()

    candidates: list[tuple[str, float, dict[str, Any]]] = []
    for raw, source, account_name in rows:
        score = _info_score(raw, source)
        group = source_group(source.source_type)
        display_source = account_name or source.name or source.platform
        heat = _engagement_total(raw.engagement)
        metrics = f"来源权重 {source.weight or 0}"
        if heat:
            metrics += f"；互动量 {heat}"
        item = _base_record(
            category="信息选题",
            title=raw.title,
            summary=raw.summary or raw.content or "",
            source_name=display_source,
            source_category=group,
            url=raw.url,
            value=_priority(score),
            source_time=raw.published_at or raw.scraped_at,
            window=window,
            entity_key=f"raw-{raw.id}",
            metrics=metrics,
            recommendation=f"{group}本时段新收录，综合来源权重与互动表现评估为{_priority(score)}价值。",
            angle=" / ".join(str(tag) for tag in (source.direction_tags or [])[:5]) or group,
            heat_score=score * 8,
        )
        source_key = f"{source.id}:{raw.source_account_id or 0}"
        candidates.append((source_key, score, item))

    # 先保证每个本时段有新增内容的信息源至少入选一条，再按价值补齐。
    candidates.sort(key=lambda row: row[1], reverse=True)
    selected: list[dict[str, Any]] = []
    used_sources: set[str] = set()
    used_keys: set[str] = set()
    for source_key, _, item in candidates:
        if source_key in used_sources or item["dedupe_key"] in used_keys:
            continue
        used_sources.add(source_key)
        used_keys.add(item["dedupe_key"])
        selected.append(item)
        if len(selected) >= limit:
            return selected
    for _, _, item in candidates:
        if item["dedupe_key"] in used_keys:
            continue
        used_keys.add(item["dedupe_key"])
        selected.append(item)
        if len(selected) >= limit:
            break
    return selected


def _topic_summary(topic: dict[str, Any]) -> str:
    summary = topic.get("ai_highlight") or topic.get("summary")
    if summary:
        return str(summary)
    evidence = topic.get("evidence") or []
    return "；".join(str(item) for item in evidence[:3])


async def _collect_xhs(db: AsyncSession, window: DigestWindow, limit: int) -> list[dict[str, Any]]:
    board = (await db.scalars(select(XhsTopicBoard).order_by(desc(XhsTopicBoard.id)).limit(1))).first()
    payload = board.payload if board and isinstance(board.payload, dict) else {}
    topics: list[tuple[str, dict[str, Any]]] = []
    seen: set[str] = set()
    for section, label in (("hot", "今日热点"), ("fermenting", "持续发酵")):
        for topic in payload.get(section) or []:
            key = str(topic.get("topic_id") or topic.get("keyword") or topic.get("topic") or "")
            if not key or key in seen:
                continue
            seen.add(key)
            topics.append((label, topic))

    records: list[dict[str, Any]] = []
    for label, topic in topics[:limit]:
        notes = topic.get("notes") or []
        first_note = notes[0] if notes else {}
        likes = int(topic.get("max_likes") or first_note.get("likes") or 0)
        new_notes = int(topic.get("new_notes_24h") or 0)
        records.append(_base_record(
            category="小红书热点",
            title=str(topic.get("topic") or topic.get("keyword") or first_note.get("title") or "小红书热点"),
            summary=_topic_summary(topic),
            source_name=label,
            source_category="小红书",
            url=str(first_note.get("original_url") or ""),
            value="高" if likes >= 1000 or new_notes >= 3 else "中",
            source_time=board.created_at if board else None,
            window=window,
            entity_key=f"topic-{topic.get('topic_id') or topic.get('keyword') or topic.get('topic')}",
            metrics=f"样本 {topic.get('sample_count') or len(notes)}；近24h新增 {new_notes}；最高赞 {likes}",
            evidence="；".join(str(item) for item in (topic.get("evidence") or [])[:3]),
            recommendation=f"{label}：近24小时新增 {new_notes} 篇，最高赞 {likes}。",
            angle="热点跟进 / 案例拆解 / 观点延展",
            heat_score=math.log10(likes + 1) * 20 + new_notes * 5,
        ))

    if records:
        return records

    # 热点快照为空时，以生产库最近一次实际采集时间为锚点兜底。这样本地采集节点
    # 暂停几天时不会整栏空白，同时在推荐理由里明确标出数据新鲜度。
    latest_discovered = await db.scalar(
        select(func.max(XhsNote.last_discovered_at)).where(XhsNote.quality_status.in_(PUBLIC_XHS_STATUSES))
    )
    if not latest_discovered:
        return records
    notes = (await db.scalars(
        select(XhsNote)
        .where(
            XhsNote.last_discovered_at >= latest_discovered - timedelta(days=7),
            XhsNote.quality_status.in_(PUBLIC_XHS_STATUSES),
        )
        .order_by(desc(XhsNote.comprehensive_score), desc(XhsNote.like_count), desc(XhsNote.last_discovered_at))
        .limit(limit)
    )).all()
    for note in notes:
        records.append(_base_record(
            category="小红书热点",
            title=note.title or "小红书热点笔记",
            summary=note.ai_summary or note.content or "",
            source_name=note.author_nickname or "热门笔记",
            source_category="小红书",
            url=note.latest_xsec_url or note.stable_url,
            value="高" if (note.like_count or 0) >= 1000 else "中",
            source_time=note.published_at or note.last_discovered_at,
            window=window,
            entity_key=f"note-{note.note_id}",
            metrics=f"赞 {note.like_count or 0}；藏 {note.collect_count or 0}；评 {note.comment_count or 0}",
            recommendation=f"最近一次小红书采集批次（{latest_discovered:%Y-%m-%d %H:%M}）中的高质量素材，当前获赞 {note.like_count or 0}。",
            angle="爆款结构 / 用户反馈 / 内容形式",
            heat_score=note.comprehensive_score or math.log10((note.like_count or 0) + 1) * 20,
        ))
    return records


async def _collect_commercial(db: AsyncSession, window: DigestWindow, limit: int) -> list[dict[str, Any]]:
    rows = (await db.execute(
        select(
            RawInfo,
            SourceRegistry,
            SourceAccount.display_name.label("account_name"),
        )
        .join(SourceRegistry, SourceRegistry.id == RawInfo.source_registry_id)
        .outerjoin(SourceAccount, SourceAccount.id == RawInfo.source_account_id)
        .where(
            RawInfo.updated_at >= window.start,
            RawInfo.updated_at < window.end,
            RawInfo.commercial_level.in_(("suspected", "likely")),
            SourceRegistry.source_type.in_(("dajiala_wechat", "sogou_wechat", "exa_wechat")),
        )
        .order_by(desc(RawInfo.updated_at), desc(RawInfo.id))
        .limit(limit)
    )).all()

    records: list[dict[str, Any]] = []
    for raw, source, account_name in rows:
        meta = raw.commercial_meta if isinstance(raw.commercial_meta, dict) else {}
        evidence = meta.get("evidence") or meta.get("signals") or []
        if isinstance(evidence, dict):
            evidence = [f"{key}: {value}" for key, value in evidence.items()]
        if isinstance(evidence, str):
            evidence = [evidence]
        brand = raw.commercial_brand or meta.get("brand") or ""
        product = meta.get("product") or ""
        reason = meta.get("reason") or ""
        records.append(_base_record(
            category="潜在商单",
            title=raw.title,
            summary=raw.summary or reason or raw.content or "",
            source_name=account_name or source.name or source.platform,
            source_category="公众号商单",
            url=raw.url,
            value="高" if raw.commercial_level == "likely" else "中",
            source_time=raw.published_at or raw.updated_at,
            window=window,
            entity_key=f"commercial-{raw.id}",
            brand=str(brand),
            product=str(product),
            evidence="；".join(str(item) for item in evidence[:5]) or str(reason),
            metrics=f"判断级别 {raw.commercial_level}",
            recommendation=f"商单检测结果为 {raw.commercial_level}，建议核查品牌与产品合作可能性。",
            angle="商业合作观察 / 品牌投放 / 产品卖点",
            heat_score=85 if raw.commercial_level == "likely" else 65,
            commercial_grade="高潜" if raw.commercial_level == "likely" else "一般",
        ))
    return records


async def collect_digest_records(
    db: AsyncSession,
    wave: str,
    run_at: Optional[datetime] = None,
) -> tuple[DigestWindow, list[dict[str, Any]]]:
    window = digest_window(wave, run_at)
    info = await _collect_information(db, window, settings.FEISHU_DIGEST_MAX_INFO_ITEMS)
    xhs = await _collect_xhs(db, window, settings.FEISHU_DIGEST_MAX_XHS_ITEMS)
    commercial = await _collect_commercial(db, window, settings.FEISHU_DIGEST_MAX_COMMERCIAL_ITEMS)
    return window, [*info, *xhs, *commercial]


FIELD_KEYS = {
    "标题": "title",
    "采集时间": "collected_at",
    "原始发布时间": "source_time",
    "内容时间": "source_time",
    "发布时间": "source_time",
    "内容分类": "category",
    "信息源名称": "source_name",
    "来源名称": "source_name",
    "信息源分类": "source_category",
    "来源分类": "source_category",
    "内容摘要": "summary",
    "摘要": "summary",
    "选题价值": "value",
    "优先级": "value",
    "原文链接": "url",
    "内容链接": "url",
    "链接": "url",
    "简报时段": "wave",
    "推送批次": "push_batch",
    "简报批次": "batch",
    "批次": "batch",
    "热度数据": "metrics",
    "互动数据": "metrics",
    "热度分": "heat_score",
    "商单品牌": "brand",
    "品牌": "brand",
    "产品": "product",
    "判断依据": "evidence",
    "商单依据": "evidence",
    "推荐理由": "recommendation",
    "选题角度": "angle",
    "商单等级": "commercial_grade",
    "处理状态": "status",
    "备注": "note",
    "去重键": "dedupe_key",
}


def _option_names(field: dict[str, Any]) -> list[str]:
    prop = field.get("property") if isinstance(field.get("property"), dict) else {}
    return [str(item.get("name")) for item in (prop.get("options") or []) if item.get("name")]


def _select_value(field_name: str, desired: str, options: list[str]) -> Optional[str]:
    if not options or desired in options:
        return desired
    aliases = {
        "高": ("高价值", "高优先级", "高"),
        "中": ("中价值", "中优先级", "中"),
        "低": ("低价值", "低优先级", "低"),
        "上午简报": ("上午简报", "上午", "AM"),
        "下午简报": ("下午简报", "下午", "PM"),
    }
    for alias in aliases.get(desired, (desired,)):
        if alias in options:
            return alias
    logger.warning("飞书字段 %s 没有选项 %s，已跳过该格", field_name, desired)
    return None


def record_to_feishu_fields(record: dict[str, Any], fields: Iterable[dict[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for field in fields:
        name = str(field.get("field_name") or "")
        key = FIELD_KEYS.get(name)
        if not key:
            continue
        value = record.get(key)
        if value in (None, "", []):
            continue
        field_type = int(field.get("type") or 0)
        if field_type == 5:  # 日期
            if not isinstance(value, datetime):
                continue
            result[name] = int(value.replace(tzinfo=BJT).timestamp() * 1000)
        elif field_type == 3:  # 单选
            selected = _select_value(name, str(value), _option_names(field))
            if selected is not None:
                result[name] = selected
        elif field_type == 4:  # 多选
            selected = _select_value(name, str(value), _option_names(field))
            if selected is not None:
                result[name] = [selected]
        elif field_type == 2:  # 数字
            if isinstance(value, (int, float)):
                result[name] = value
        elif field_type == 15:  # 超链接
            result[name] = {"link": str(value), "text": "查看原文"}
        elif field_type == 1:  # 文本（包括主字段）
            result[name] = _text(value, 2000)
    if not result.get("标题"):
        raise FeishuDigestError("目标表缺少可写的文本主字段“标题”")
    return result


def _cell_scalar(value: Any) -> str:
    if isinstance(value, dict):
        return str(value.get("link") or value.get("text") or "")
    if isinstance(value, list):
        return ",".join(_cell_scalar(item) for item in value)
    return str(value or "")


def _existing_signature(fields: dict[str, Any]) -> str:
    dedupe = _cell_scalar(fields.get("去重键"))
    if dedupe:
        return f"key:{dedupe}"
    category = _cell_scalar(fields.get("内容分类"))
    title = _cell_scalar(fields.get("标题"))
    collected = _cell_scalar(fields.get("采集时间"))
    return f"visible:{category}|{title}|{collected}"


def _new_signature(record: dict[str, Any], *, has_dedupe_field: bool) -> str:
    if has_dedupe_field:
        return f"key:{record['dedupe_key']}"
    collected = int(record["collected_at"].replace(tzinfo=BJT).timestamp() * 1000)
    return f"visible:{record['category']}|{record['title']}|{collected}"


class FeishuBaseClient:
    """仅使用独立日报应用的 tenant token，不接触用户 OAuth token。"""

    def __init__(self, client: Optional[httpx.AsyncClient] = None) -> None:
        self.app_id = settings.FEISHU_DIGEST_APP_ID
        self.app_secret = settings.FEISHU_DIGEST_APP_SECRET
        self.base_token = settings.FEISHU_DIGEST_BASE_TOKEN
        self.table_id = settings.FEISHU_DIGEST_TABLE_ID
        self._client = client

    def _require_config(self) -> None:
        if not self.app_id or not self.app_secret:
            raise FeishuDigestError("缺少 FEISHU_DIGEST_APP_ID / FEISHU_DIGEST_APP_SECRET")
        if not self.base_token or not self.table_id:
            raise FeishuDigestError("缺少 FEISHU_DIGEST_BASE_TOKEN / FEISHU_DIGEST_TABLE_ID")

    async def _json(self, response: httpx.Response, action: str) -> dict[str, Any]:
        try:
            data = response.json()
        except ValueError as exc:
            raise FeishuDigestError(f"飞书{action}返回了非 JSON 响应（HTTP {response.status_code}）") from exc
        if response.status_code >= 400 or data.get("code") not in (0, None):
            raise FeishuDigestError(
                f"飞书{action}失败（HTTP {response.status_code}, code={data.get('code')}, msg={data.get('msg') or 'unknown'}）"
            )
        return data

    async def _with_client(self):
        if self._client is not None:
            return self._client, False
        return httpx.AsyncClient(timeout=30), True

    async def tenant_token(self) -> str:
        self._require_config()
        client, owned = await self._with_client()
        try:
            response = await client.post(
                f"{OPEN_HOST}/open-apis/auth/v3/tenant_access_token/internal",
                json={"app_id": self.app_id, "app_secret": self.app_secret},
            )
            data = await self._json(response, "获取应用令牌")
            token = data.get("tenant_access_token")
            if not token:
                raise FeishuDigestError("飞书获取应用令牌失败：响应中没有 tenant_access_token")
            return str(token)
        finally:
            if owned:
                await client.aclose()

    def _headers(self, token: str) -> dict[str, str]:
        return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    async def list_fields(self, token: str) -> list[dict[str, Any]]:
        client, owned = await self._with_client()
        try:
            response = await client.get(
                f"{OPEN_HOST}/open-apis/bitable/v1/apps/{self.base_token}/tables/{self.table_id}/fields",
                params={"page_size": 100},
                headers=self._headers(token),
            )
            data = await self._json(response, "读取字段")
            return list((data.get("data") or {}).get("items") or [])
        finally:
            if owned:
                await client.aclose()

    async def existing_signatures(self, token: str, max_records: int = 5000) -> set[str]:
        client, owned = await self._with_client()
        signatures: set[str] = set()
        page_token: Optional[str] = None
        try:
            while len(signatures) < max_records:
                params: dict[str, Any] = {"page_size": 500}
                if page_token:
                    params["page_token"] = page_token
                response = await client.get(
                    f"{OPEN_HOST}/open-apis/bitable/v1/apps/{self.base_token}/tables/{self.table_id}/records",
                    params=params,
                    headers=self._headers(token),
                )
                data = await self._json(response, "读取已有记录")
                body = data.get("data") or {}
                for item in body.get("items") or []:
                    signatures.add(_existing_signature(item.get("fields") or {}))
                if not body.get("has_more"):
                    break
                page_token = body.get("page_token")
                if not page_token:
                    break
            return signatures
        finally:
            if owned:
                await client.aclose()

    async def list_records(self, token: str, max_records: int = 5000) -> list[dict[str, Any]]:
        client, owned = await self._with_client()
        records: list[dict[str, Any]] = []
        page_token: Optional[str] = None
        try:
            while len(records) < max_records:
                params: dict[str, Any] = {"page_size": 500}
                if page_token:
                    params["page_token"] = page_token
                response = await client.get(
                    f"{OPEN_HOST}/open-apis/bitable/v1/apps/{self.base_token}/tables/{self.table_id}/records",
                    params=params,
                    headers=self._headers(token),
                )
                data = await self._json(response, "读取记录")
                body = data.get("data") or {}
                records.extend(body.get("items") or [])
                if not body.get("has_more"):
                    break
                page_token = body.get("page_token")
                if not page_token:
                    break
            return records[:max_records]
        finally:
            if owned:
                await client.aclose()

    async def batch_create(self, token: str, records: list[dict[str, Any]]) -> int:
        client, owned = await self._with_client()
        created = 0
        try:
            for start in range(0, len(records), 200):
                chunk = records[start:start + 200]
                response = await client.post(
                    f"{OPEN_HOST}/open-apis/bitable/v1/apps/{self.base_token}/tables/{self.table_id}/records/batch_create",
                    json={"records": [{"fields": fields} for fields in chunk]},
                    headers=self._headers(token),
                )
                data = await self._json(response, "批量写入记录")
                created += len((data.get("data") or {}).get("records") or chunk)
            return created
        finally:
            if owned:
                await client.aclose()

    async def batch_update(self, token: str, records: list[dict[str, Any]]) -> int:
        client, owned = await self._with_client()
        updated = 0
        try:
            for start in range(0, len(records), 200):
                chunk = records[start:start + 200]
                response = await client.post(
                    f"{OPEN_HOST}/open-apis/bitable/v1/apps/{self.base_token}/tables/{self.table_id}/records/batch_update",
                    json={"records": chunk},
                    headers=self._headers(token),
                )
                data = await self._json(response, "批量更新记录")
                updated += len((data.get("data") or {}).get("records") or chunk)
            return updated
        finally:
            if owned:
                await client.aclose()


async def sync_digest_records(records: list[dict[str, Any]], client: Optional[FeishuBaseClient] = None) -> dict[str, Any]:
    base = client or FeishuBaseClient()
    token = await base.tenant_token()
    fields = await base.list_fields(token)
    has_dedupe = any(field.get("field_name") == "去重键" for field in fields)
    existing = await base.existing_signatures(token)
    pending: list[dict[str, Any]] = []
    seen = set(existing)
    for record in records:
        signature = _new_signature(record, has_dedupe_field=has_dedupe)
        if signature in seen:
            continue
        seen.add(signature)
        pending.append(record_to_feishu_fields(record, fields))
    created = await base.batch_create(token, pending) if pending else 0
    return {
        "selected": len(records),
        "created": created,
        "skipped_existing": len(records) - len(pending),
        "field_count": len(fields),
    }


async def backfill_existing_english_records(
    client: Optional[FeishuBaseClient] = None,
    *,
    llm_client: Optional[LLMClient] = None,
) -> dict[str, Any]:
    """把表内已有的英文标题/摘要回填为中文，仅更新这两个文本字段。"""
    base = client or FeishuBaseClient()
    token = await base.tenant_token()
    items = await base.list_records(token)
    candidates: list[dict[str, Any]] = []
    record_ids: list[str] = []
    originals: list[tuple[str, str]] = []
    for item in items:
        fields = item.get("fields") or {}
        title = _cell_scalar(fields.get("标题"))
        summary = _cell_scalar(fields.get("内容摘要"))
        if not (needs_chinese_translation(title) or needs_chinese_translation(summary)):
            continue
        record_id = str(item.get("record_id") or "")
        if not record_id:
            continue
        record_ids.append(record_id)
        originals.append((title, summary))
        candidates.append({"title": title, "summary": summary})

    translation = await translate_digest_records(candidates, llm_client=llm_client)
    updates: list[dict[str, Any]] = []
    for record_id, original, translated in zip(record_ids, originals, candidates):
        changed_fields: dict[str, str] = {}
        if translated["title"] != original[0]:
            changed_fields["标题"] = translated["title"]
        if translated["summary"] != original[1]:
            changed_fields["内容摘要"] = translated["summary"]
        if changed_fields:
            updates.append({"record_id": record_id, "fields": changed_fields})
    updated = await base.batch_update(token, updates) if updates else 0
    return {
        "records_checked": len(items),
        "records_needing_translation": len(candidates),
        "records_updated": updated,
        "translation": translation,
    }
