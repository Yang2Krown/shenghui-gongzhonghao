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
        logger.info(f"[{source_type}] 抓取启动 (type={type(source_type).__name__})")
        result = asyncio.run(_run_orchestrator(source_types=[source_type]))
        logger.info(f"[{source_type}] 完成：sources_total={result.get('sources_total')} new={result.get('items_new')} dup={result.get('items_duplicate')}")
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
    """按 platform 单独抓（每个源一个独立任务：失败/卡死只影响自己，独立 commit + 重试）。"""
    try:
        result = asyncio.run(_run_orchestrator(platforms=[platform]))
        logger.info(f"[{platform}] 完成：new={result.get('items_new')} dup={result.get('items_duplicate')}")
        return result
    except Exception as e:
        logger.error(f"[{platform}] 抓取失败: {e}")
        self.retry(exc=e, countdown=90, max_retries=2)


# 每个源派发的间隔（秒）：错峰拉长，避免一次性压一堆、也给每个源充足时间
DISPATCH_GAP_SECONDS = 120

# 派发顺序：轻量稳定的先跑，重量级（需 API / Playwright）的排后面
_TYPE_ORDER = {
    "rss": 0, "tophub": 1, "hackernews": 2, "v2ex": 3, "github": 4,
    "reddit": 5, "xhs_daily": 6, "gzh_explosive": 7, "web": 8,
    "sogou_wechat": 9, "exa_wechat": 10, "x_playwright": 11,
}


async def _list_enabled_platforms_ordered() -> List[Dict[str, str]]:
    """列出所有启用、且有对应 adapter 的源 platform，按类型优先级排序。

    排除 aihot（独立链路单独调度）和无 adapter 的类型。
    """
    from sqlalchemy import select
    from app.models.source_registry import SourceRegistry

    async with AsyncSessionLocal() as db:
        rows = (await db.execute(
            select(SourceRegistry.platform, SourceRegistry.source_type)
            .where(SourceRegistry.enabled.is_(True))
        )).all()

    sources = [
        {"platform": p, "source_type": t}
        for (p, t) in rows
        if t in _TYPE_ORDER
    ]
    sources.sort(key=lambda s: (_TYPE_ORDER.get(s["source_type"], 99), s["platform"]))
    return sources


@shared_task(bind=True, name="scraper.dispatch_fetch")
def dispatch_fetch_task(self, gap_seconds: int = DISPATCH_GAP_SECONDS):
    """采集派发器：把"全网采集"拆成每源一个独立任务，错峰排进上午。

    取代过去"一个大任务抓全部 RSS"的做法——过去任一源卡死就把整批拖到超时、
    commit 丢失。现在每个源独立任务、独立提交、独立重试，互不影响。
    """
    try:
        sources = asyncio.run(_list_enabled_platforms_ordered())
        for i, s in enumerate(sources):
            fetch_platform_task.apply_async(args=[s["platform"]], countdown=i * gap_seconds)
        last_eta_min = round((len(sources) - 1) * gap_seconds / 60, 1) if sources else 0
        logger.info(
            f"采集派发完成：{len(sources)} 个源，间隔 {gap_seconds}s，"
            f"最后一个约 {last_eta_min} 分钟后开始"
        )
        return {"dispatched": len(sources), "gap_seconds": gap_seconds, "last_eta_min": last_eta_min}
    except Exception as e:
        logger.error(f"采集派发失败: {e}")
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
