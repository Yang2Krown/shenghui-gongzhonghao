"""Commercial detection Celery tasks.

只对公众号(mp.weixin.qq.com)来源的文章执行商单检测。
检测命中后自动调用分类服务，填充 brand/category。
"""

import asyncio
import logging
from typing import Any, Dict, List, Optional

from celery import shared_task
from sqlalchemy import select

from app.db.session import AsyncSessionLocal, engine
from app.models.raw_info import RawInfo
from app.models.source_registry import SourceRegistry
from app.services.commercial_detection import detect_commercial_article
from app.services.commercial_classification import classify_commercial

logger = logging.getLogger(__name__)

# 只对这些平台的来源执行商单检测
ALLOWED_PLATFORMS = {"mp.weixin.qq.com"}


async def _detect_one(raw_info_id: int, *, force_llm: bool = False) -> Dict[str, Any]:
    try:
        async with AsyncSessionLocal() as db:
            raw = (
                await db.execute(
                    select(RawInfo)
                    .outerjoin(SourceRegistry, RawInfo.source_registry_id == SourceRegistry.id)
                    .where(RawInfo.id == raw_info_id)
                )
            ).scalar_one_or_none()
            if not raw:
                return {"raw_info_id": raw_info_id, "status": "missing"}

            # 仅公众号来源才执行检测
            source = raw.source
            platform = (source.platform or "").lower() if source else ""
            url_domain = ""
            try:
                from urllib.parse import urlparse
                url_domain = (urlparse(raw.url or "").netloc or "").lower().removeprefix("www.")
            except Exception:
                pass

            is_wechat = (
                platform in ALLOWED_PLATFORMS
                or "mp.weixin.qq.com" in url_domain
                or "weixin.qq.com" in url_domain
            )
            if not is_wechat and not force_llm:
                return {"raw_info_id": raw_info_id, "status": "skipped_non_wechat"}

            result = await detect_commercial_article(
                title=raw.title or "",
                summary=raw.summary or "",
                content=raw.content or "",
                force_llm=force_llm,
            )
            raw.commercial_level = result.level
            raw.commercial_meta = result.to_meta()

            # 命中商单 → 自动分类（甲方 + 功能方向）+ AI 摘要
            if result.level in ("suspected", "likely"):
                try:
                    cls = await classify_commercial(
                        title=raw.title or "",
                        content=raw.content or "",
                        product=result.product or "",
                    )
                    raw.commercial_brand = cls.brand or None
                    raw.commercial_category = cls.category or None
                    logger.info(
                        "商单分类完成 raw_info_id=%s brand=%s category=%s",
                        raw_info_id, cls.brand, cls.category,
                    )
                except Exception as exc:
                    logger.warning("商单分类失败 raw_info_id=%s: %s", raw_info_id, exc)

                # AI 摘要（有正文且还没摘要时才生成）
                if raw.content and not raw.summary:
                    try:
                        from app.services.ai_service import ai_service
                        text = f"标题：{raw.title or ''}\n\n正文：{(raw.content or '')[:3000]}"
                        summary = await ai_service.summarize_content(text)
                        if summary:
                            raw.summary = summary
                            logger.info("商单AI摘要完成 raw_info_id=%s", raw_info_id)
                    except Exception as exc:
                        logger.warning("商单AI摘要失败 raw_info_id=%s: %s", raw_info_id, exc)

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
                "commercial_brand": raw.commercial_brand,
                "commercial_category": raw.commercial_category,
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
        "skipped": sum(1 for r in results if r.get("status") == "skipped_non_wechat"),
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
