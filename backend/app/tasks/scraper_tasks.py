"""数据抓取 Celery 任务：调 ScrapingOrchestrator。

旧的 scraper_service.fetch_and_save_topics() 仍可用（写到旧 topics 表），
但新主流程一律走 orchestrator → RawInfo，再由下游 preprocess pipeline 消费。
"""

import asyncio
import logging
from typing import Any, Dict, List, Optional

from celery import shared_task

from app.db.session import AsyncSessionLocal, engine
from app.services.scraping.adapters import register_adapters
from app.services.scraping.orchestrator import orchestrator

logger = logging.getLogger(__name__)


# 模块导入时把 5 个 P0 adapter 注册进 orchestrator（幂等）
register_adapters()


async def _run_orchestrator(
    *,
    source_types: Optional[List[str]] = None,
    platforms: Optional[List[str]] = None,
) -> Dict[str, Any]:
    try:
        async with AsyncSessionLocal() as db:
            return await orchestrator.fetch_all(
                db,
                source_types=source_types,
                platforms=platforms,
            )
    finally:
        await engine.dispose()


@shared_task(bind=True, name="scraper.fetch_all_sources")
def fetch_all_sources_task(
    self,
    source_types: Optional[List[str]] = None,
    platforms: Optional[List[str]] = None,
):
    """全量抓取（按 source_type / platform 过滤）。手动触发时用。"""
    try:
        logger.info(f"orchestrator 启动：source_types={source_types} platforms={platforms}")
        result = asyncio.run(_run_orchestrator(source_types=source_types, platforms=platforms))
        logger.info(f"orchestrator 完成：new={result.get('items_new')} dup={result.get('items_duplicate')}")
        return result
    except Exception as e:
        logger.error(f"抓取任务失败: {e}")
        self.retry(exc=e, countdown=60, max_retries=3)


@shared_task(bind=True, name="scraper.fetch_source_type")
def fetch_source_type_task(self, source_type: str):
    """按单个 source_type 抓取，定时任务调用。失败不影响其他类型。"""
    try:
        logger.info(f"[{source_type}] 抓取启动")
        result = asyncio.run(_run_orchestrator(source_types=[source_type]))
        logger.info(f"[{source_type}] 完成：new={result.get('items_new')} dup={result.get('items_duplicate')}")
        return result
    except Exception as e:
        logger.error(f"[{source_type}] 抓取失败: {e}")
        self.retry(exc=e, countdown=60, max_retries=2)


@shared_task(bind=True, name="scraper.fetch_rss_only")
def fetch_rss_only_task(self):
    """只跑 RSS 源（最便宜、最稳定，可以高频跑）。"""
    try:
        result = asyncio.run(_run_orchestrator(source_types=["rss"]))
        return result
    except Exception as e:
        logger.error(f"RSS 抓取失败: {e}")
        self.retry(exc=e, countdown=30, max_retries=3)


@shared_task(bind=True, name="scraper.fetch_wechat_search")
def fetch_wechat_search_task(self):
    """只跑公众号关键词搜索流（依赖 Exa，频率不宜过高）。"""
    try:
        result = asyncio.run(_run_orchestrator(source_types=["exa_wechat"]))
        return result
    except Exception as e:
        logger.error(f"公众号搜索抓取失败: {e}")
        self.retry(exc=e, countdown=120, max_retries=2)


@shared_task(bind=True, name="scraper.fetch_platform")
def fetch_platform_task(self, platform: str):
    """按 platform 单独抓（调试/补抓时用）。"""
    try:
        result = asyncio.run(_run_orchestrator(platforms=[platform]))
        return result
    except Exception as e:
        logger.error(f"[{platform}] 抓取失败: {e}")
        self.retry(exc=e, countdown=60, max_retries=2)


# ── AI HOT 独立任务（与通用 RSS 解耦）──────────────────────

async def _run_aihot(feed_key: str = "selected") -> dict:
    from app.services.scraping.adapters.aihot_adapter import fetch_aihot
    try:
        async with AsyncSessionLocal() as db:
            return await fetch_aihot(db, feed_key=feed_key)
    finally:
        await engine.dispose()


async def _run_aihot_all() -> dict:
    from app.services.scraping.adapters.aihot_adapter import fetch_aihot_all_feeds
    try:
        async with AsyncSessionLocal() as db:
            return await fetch_aihot_all_feeds(db)
    finally:
        await engine.dispose()


@shared_task(bind=True, name="scraper.fetch_aihot")
def fetch_aihot_task(self, feed_key: str = "selected"):
    """抓取 AI HOT 单个 feed。feed_key: selected / all / daily"""
    try:
        logger.info(f"AI HOT [{feed_key}] 抓取启动")
        result = asyncio.run(_run_aihot(feed_key))
        logger.info(f"AI HOT [{feed_key}] 完成: new={result.get('new')} dup={result.get('duplicate')}")
        return result
    except Exception as e:
        logger.error(f"AI HOT [{feed_key}] 抓取失败: {e}")
        self.retry(exc=e, countdown=30, max_retries=3)


@shared_task(bind=True, name="scraper.fetch_aihot_all")
def fetch_aihot_all_task(self):
    """一次性抓取 AI HOT 全部三个 feed（精选 + 全部 + 日报）。"""
    try:
        logger.info("AI HOT 全量抓取启动")
        result = asyncio.run(_run_aihot_all())
        logger.info(f"AI HOT 全量完成: {result}")
        return result
    except Exception as e:
        logger.error(f"AI HOT 全量抓取失败: {e}")
        self.retry(exc=e, countdown=30, max_retries=3)
