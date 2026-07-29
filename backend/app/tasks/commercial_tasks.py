"""Commercial detection Celery tasks.

只对公众号(mp.weixin.qq.com)来源的文章执行商单检测。
检测命中后自动调用分类服务，填充 brand/category。
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from celery import shared_task
from sqlalchemy.orm import joinedload

from app.db.session import SessionLocal, engine
from app.models.raw_info import RawInfo
from app.services.commercial_detection import detect_commercial_article
from app.services.commercial_classification import classify_commercial, normalize_commercial_label

logger = logging.getLogger(__name__)

# 只对这些平台的来源执行商单检测
ALLOWED_PLATFORMS = {"mp.weixin.qq.com", "sogou_wechat_cases"}


def _load_raw_context(raw_info_id: int) -> Optional[Dict[str, Any]]:
    """Load RawInfo fields with sync SQLAlchemy.

    Celery workers run these tasks through asyncio.run(), and asyncpg-backed
    lazy loads can raise MissingGreenlet when ORM attributes trigger IO outside
    SQLAlchemy's greenlet bridge. Keep DB access synchronous in this task and
    only await the LLM calls.
    """
    with SessionLocal() as db:
        raw = (
            db.query(RawInfo)
            .options(joinedload(RawInfo.source))
            .filter(RawInfo.id == raw_info_id)
            .one_or_none()
        )
        if not raw:
            return None
        source = raw.source
        return {
            "id": raw.id,
            "title": raw.title or "",
            "summary": raw.summary or "",
            "content": raw.content or "",
            "url": raw.url or "",
            "source_platform": (source.platform or "").lower() if source else "",
            "source_type": (source.source_type or "") if source else "",
        }


def _save_detection_result(
    raw_info_id: int,
    *,
    level: str,
    meta: Dict[str, Any],
    brand: Optional[str],
    category: Optional[str],
    summary: Optional[str],
) -> Dict[str, Any]:
    with SessionLocal() as db:
        raw = db.get(RawInfo, raw_info_id)
        if not raw:
            return {"raw_info_id": raw_info_id, "status": "missing"}
        raw.commercial_level = level
        raw.commercial_meta = meta
        raw.commercial_brand = brand or None
        raw.commercial_category = category or None
        if summary:
            raw.summary = summary
        db.commit()
        return {
            "raw_info_id": raw_info_id,
            "status": "ok",
            "commercial_level": level,
            "commercial_meta": meta,
            "commercial_brand": brand,
            "commercial_category": category,
        }


def _save_extracted_fulltext(raw_info_id: int, *, content: str, author: str = "") -> None:
    """Persist direct WeChat extraction before commercial analysis."""
    with SessionLocal() as db:
        raw = db.get(RawInfo, raw_info_id)
        if not raw:
            return
        raw.content = content
        if author and not raw.author:
            raw.author = author[:200]
        db.commit()


def _recent_wechat_raw_info_ids(
    limit: int = 200,
    *,
    levels: Optional[List[str]] = None,
    days: Optional[int] = None,
) -> List[int]:
    """Find recent WeChat RawInfo rows that need commercial detection."""
    from app.models.source_registry import SourceRegistry

    with SessionLocal() as db:
        filters = [
            SourceRegistry.source_type.in_(["dajiala_wechat", "sogou_wechat", "exa_wechat"]),
        ]
        if levels is not None:
            filters.append(RawInfo.commercial_level.in_(levels))
        if days:
            filters.append(RawInfo.scraped_at >= datetime.utcnow() - timedelta(days=max(1, int(days))))
        rows = (
            db.query(RawInfo.id)
            .join(SourceRegistry, RawInfo.source_registry_id == SourceRegistry.id)
            .filter(*filters)
            .order_by(RawInfo.id.desc())
            .limit(max(1, int(limit or 200)))
            .all()
        )
        return [int(row[0]) for row in rows]


async def _detect_one(raw_info_id: int, *, force_llm: bool = False) -> Dict[str, Any]:
    raw = _load_raw_context(raw_info_id)
    if not raw:
        return {"raw_info_id": raw_info_id, "status": "missing"}

    # 仅公众号来源才执行检测
    url_domain = ""
    try:
        from urllib.parse import urlparse
        url_domain = (urlparse(raw["url"] or "").netloc or "").lower().removeprefix("www.")
    except Exception:
        pass

    is_wechat = (
        raw["source_platform"] in ALLOWED_PLATFORMS
        or raw["source_type"] in {"dajiala_wechat", "sogou_wechat", "exa_wechat"}
        or "mp.weixin.qq.com" in url_domain
        or "weixin.qq.com" in url_domain
    )
    if not is_wechat and not force_llm:
        return {"raw_info_id": raw_info_id, "status": "skipped_non_wechat"}

    # 极致了只返回文章元数据。复用创作工具的公众号直连提取器，确保
    # DeepSeek 优先基于正文判断；提取失败时仍保留标题级降级能力。
    if raw["source_type"] == "dajiala_wechat" and not (raw["content"] or "").strip():
        try:
            from app.services.scraping.wechat_fulltext import extract_wechat_article

            extracted = await extract_wechat_article(raw["url"])
            if extracted:
                _save_extracted_fulltext(
                    raw_info_id,
                    content=extracted.content,
                    author=extracted.author,
                )
                raw["content"] = extracted.content
                logger.info(
                    "商单检测前正文补抓完成 raw_info_id=%s content_len=%s",
                    raw_info_id, len(extracted.content),
                )
        except Exception as exc:
            logger.warning("商单检测前正文补抓失败 raw_info_id=%s: %s", raw_info_id, exc)

    result = await detect_commercial_article(
        title=raw["title"],
        summary=raw["summary"],
        content=raw["content"],
        force_llm=force_llm or raw["source_type"] == "dajiala_wechat",
    )

    brand: Optional[str] = normalize_commercial_label(result.brand) or None
    category: Optional[str] = str(result.category or "").strip() or None
    summary: Optional[str] = None

    # 命中商单 → 自动分类（甲方 + 功能方向）+ AI 摘要
    if result.level in ("suspected", "likely"):
        try:
            if not brand or not category:
                cls = await classify_commercial(
                    title=raw["title"],
                    content=raw["content"],
                    product=result.product or "",
                )
                brand = brand or normalize_commercial_label(cls.brand) or None
                category = category or cls.category or None
                logger.info(
                    "商单分类完成 raw_info_id=%s brand=%s category=%s",
                    raw_info_id, brand, category,
                )
        except Exception as exc:
            logger.warning("商单分类失败 raw_info_id=%s: %s", raw_info_id, exc)

        # AI 摘要（有正文且还没摘要时才生成）
        if raw["content"] and not raw["summary"]:
            try:
                from app.services.ai_service import ai_service
                text = f"标题：{raw['title']}\n\n正文：{raw['content'][:3000]}"
                summary = await ai_service.summarize_content(text)
                if summary:
                    logger.info("商单AI摘要完成 raw_info_id=%s", raw_info_id)
            except Exception as exc:
                logger.warning("商单AI摘要失败 raw_info_id=%s: %s", raw_info_id, exc)

    meta = result.to_meta()
    if brand:
        meta["brand"] = brand
    if category:
        meta["category"] = category

    saved = _save_detection_result(
        raw_info_id,
        level=result.level,
        meta=meta,
        brand=brand,
        category=category,
        summary=summary,
    )
    logger.info(
        "商单检测完成 raw_info_id=%s level=%s product=%s",
        raw_info_id,
        result.level,
        result.product,
    )
    return saved


async def _detect_batch(
    raw_info_ids: Optional[List[int]] = None,
    *,
    force_llm: bool = False,
    limit: int = 200,
    days: Optional[int] = None,
) -> Dict[str, Any]:
    if raw_info_ids is None:
        # 普通批处理只补还没命中的 none；强制 DeepSeek 重判时，最近文章全部重扫，
        # 避免旧的 short_text/规则结果一直把前端卡成空列表。
        raw_info_ids = _recent_wechat_raw_info_ids(
            limit=limit,
            levels=None if force_llm else ["none"],
            days=days,
        )
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
        "skipped": sum(1 for r in results if r.get("status") == "skipped_non_wechat"),
        "failed": sum(1 for r in results if r.get("status") == "failed"),
        "missing": sum(1 for r in results if r.get("status") == "missing"),
        "results": results,
    }


async def _run_detect_one(raw_info_id: int, *, force_llm: bool = False) -> Dict[str, Any]:
    """Run one Celery coroutine and release loop-bound async DB connections."""
    try:
        return await _detect_one(raw_info_id, force_llm=force_llm)
    finally:
        await engine.dispose()


async def _run_detect_batch(
    raw_info_ids: Optional[List[int]] = None,
    *,
    force_llm: bool = False,
    limit: int = 200,
    days: Optional[int] = None,
) -> Dict[str, Any]:
    try:
        return await _detect_batch(
            raw_info_ids,
            force_llm=force_llm,
            limit=limit,
            days=days,
        )
    finally:
        await engine.dispose()


@shared_task(bind=True, name="commercial.detect_raw_info")
def detect_commercial_task(self, raw_info_id: int, force_llm: bool = False):
    """Detect commercial signals for a single RawInfo row."""
    try:
        return asyncio.run(_run_detect_one(raw_info_id, force_llm=force_llm))
    except Exception as exc:
        logger.error("商单检测任务失败 raw_info_id=%s: %s", raw_info_id, exc)
        self.retry(exc=exc, countdown=60, max_retries=2)


@shared_task(bind=True, name="commercial.detect_raw_infos")
def detect_commercial_batch_task(
    self,
    raw_info_ids: Optional[List[int]] = None,
    force_llm: bool = False,
    limit: int = 200,
    days: Optional[int] = None,
):
    """Detect commercial signals for a batch of RawInfo rows.

    If raw_info_ids is omitted, auto-pick recent WeChat rows whose
    commercial_level is still "none". This makes production rechecks easy after
    crawler/backfill tasks have already inserted rows.
    """
    try:
        return asyncio.run(_run_detect_batch(
            raw_info_ids,
            force_llm=force_llm,
            limit=limit,
            days=days,
        ))
    except Exception as exc:
        logger.error("商单批量检测任务失败: %s", exc)
        self.retry(exc=exc, countdown=60, max_retries=2)
