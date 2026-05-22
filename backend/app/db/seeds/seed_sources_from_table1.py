"""Seed: AI选题信息源.xlsx → SourceRegistry。

只导 06_信息源链接 sheet（站点级 URL 入口，23 条）。
01_信息源总表 是 7 层分类描述（多源合并文本），不适合作为单条记录。
"""

import asyncio
import logging
from pathlib import Path
from typing import Optional

import openpyxl
from sqlalchemy import select

from app.db.seeds import TABLE1_PATH
from app.db.session import AsyncSessionLocal
from app.models.source_registry import (
    SourceRegistry,
    SOURCE_TYPE_RSS,
    SOURCE_TYPE_WEB,
    SOURCE_TYPE_GITHUB,
    SOURCE_TYPE_HACKERNEWS,
)

logger = logging.getLogger(__name__)


# 表 1 "类型" 字段 → 内部 source_type
TYPE_MAP_BY_NAME = {
    "TopHub 科技榜": SOURCE_TYPE_WEB,
    "TopHub 新闻榜": SOURCE_TYPE_WEB,
    "GitHub Trending": SOURCE_TYPE_GITHUB,
    "Hacker News": SOURCE_TYPE_HACKERNEWS,
}

# 表 1 "类型" 列 → tier（对应 01_信息源总表 的层级）
TIER_BY_TYPE = {
    "热榜": 1,
    "科技媒体": 1,
    "工具媒体": 1,
    "官方源": 2,
    "开发者社区": 5,
    "产品社区": 5,
    "聚合/爆文池": 4,
    "内容平台": 6,
    "财经源": 7,
}


def _infer_source_type(name: str, url: str) -> str:
    if name in TYPE_MAP_BY_NAME:
        return TYPE_MAP_BY_NAME[name]
    lower = url.lower()
    if any(s in lower for s in ("/feed", "/rss", ".xml")):
        return SOURCE_TYPE_RSS
    if "github.com" in lower:
        return SOURCE_TYPE_GITHUB
    if "ycombinator" in lower:
        return SOURCE_TYPE_HACKERNEWS
    return SOURCE_TYPE_WEB


def _slug_platform(name: str) -> str:
    """生成 platform 字段（snake_case，便于 adapter 匹配）。"""
    mapping = {
        "TopHub 科技榜": "tophub_tech",
        "TopHub 新闻榜": "tophub_news",
        "36氪": "36kr",
        "量子位": "qbitai",
        "机器之心": "jiqizhixin",
        "IT之家": "ithome",
        "虎嗅": "huxiu",
        "少数派": "sspai",
        "APPSO": "appso",
        "OpenAI": "openai_blog",
        "Anthropic": "anthropic_blog",
        "Google DeepMind": "deepmind_blog",
        "Runway": "runway_blog",
        "GitHub Trending": "github_trending",
        "Product Hunt": "producthunt",
        "Hacker News": "hackernews",
        "AIHOT": "aihot",
        "知乎": "zhihu",
        "小红书": "xiaohongshu",
        "微博热搜": "weibo_hot",
        "百度热搜": "baidu_hot",
        "新浪财经": "sina_finance",
        "东方财富": "eastmoney",
    }
    return mapping.get(name, name.lower().replace(" ", "_"))


async def _upsert(db, *, name: str, url: str, source_type: str, tier: Optional[int],
                  description: str, requires_auth: bool, enabled: bool) -> str:
    platform = _slug_platform(name)
    existing = (await db.execute(
        select(SourceRegistry).where(SourceRegistry.platform == platform)
    )).scalar_one_or_none()

    if existing:
        existing.name = name
        existing.url = url
        existing.source_type = source_type
        existing.tier = tier
        existing.description = description
        existing.requires_auth = requires_auth
        existing.enabled = enabled
        return "updated"

    db.add(SourceRegistry(
        name=name,
        platform=platform,
        source_type=source_type,
        url=url,
        tier=tier,
        direction_tags=[],
        weight=5,
        requires_auth=requires_auth,
        auth_status="missing" if requires_auth else "ok",
        fetch_strategy="cron",
        fetch_config={},
        enabled=enabled,
        description=description,
    ))
    return "created"


async def run(db) -> dict:
    if not Path(TABLE1_PATH).exists():
        raise FileNotFoundError(f"Seed file missing: {TABLE1_PATH}")

    wb = openpyxl.load_workbook(TABLE1_PATH, data_only=True)
    ws = wb["06_信息源链接"]
    stats = {"created": 0, "updated": 0, "skipped": 0}

    for row in ws.iter_rows(min_row=5, values_only=True):
        name, url, purpose, type_label = (row + (None, None, None, None))[:4]
        if not name or not url:
            stats["skipped"] += 1
            continue

        source_type = _infer_source_type(str(name), str(url))
        tier = TIER_BY_TYPE.get(str(type_label).strip() if type_label else "", None)

        # P1 类需要 cookie 的源先停用（保留记录，等 P1 阶段再启用）
        requires_auth = type_label in ("内容平台",) and name in ("小红书", "微博热搜")
        enabled = not requires_auth

        outcome = await _upsert(
            db,
            name=str(name).strip(),
            url=str(url).strip(),
            source_type=source_type,
            tier=tier,
            description=f"{type_label or ''} | {purpose or ''}".strip(" |"),
            requires_auth=requires_auth,
            enabled=enabled,
        )
        stats[outcome] += 1

    await db.commit()
    logger.info(f"seed_sources_from_table1: {stats}")
    return stats


async def _main():
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    async with AsyncSessionLocal() as db:
        result = await run(db)
    print(f"Done: {result}")


if __name__ == "__main__":
    asyncio.run(_main())
