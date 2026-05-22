"""数据抓取 Celery 任务：调 ScrapingOrchestrator。

旧的 scraper_service.fetch_and_save_topics() 仍可用（写到旧 topics 表），
但新主流程一律走 orchestrator → RawInfo，再由下游 preprocess pipeline 消费。
"""

import asyncio
import logging
from typing import Any, Dict, List, Optional

from celery import shared_task

from app.db.session import AsyncSessionLocal
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
    async with AsyncSessionLocal() as db:
        return await orchestrator.fetch_all(
            db,
            source_types=source_types,
            platforms=platforms,
        )


@shared_task(bind=True, name="scraper.fetch_all_sources")
def fetch_all_sources_task(
    self,
    source_types: Optional[List[str]] = None,
    platforms: Optional[List[str]] = None,
):
    """全量抓取（按 source_type / platform 过滤）。"""
    try:
        logger.info(f"orchestrator 启动：source_types={source_types} platforms={platforms}")
        result = asyncio.run(_run_orchestrator(source_types=source_types, platforms=platforms))
        logger.info(f"orchestrator 完成：new={result.get('items_new')} dup={result.get('items_duplicate')}")
        return result
    except Exception as e:
        logger.error(f"抓取任务失败: {e}")
        self.retry(exc=e, countdown=60, max_retries=3)


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
