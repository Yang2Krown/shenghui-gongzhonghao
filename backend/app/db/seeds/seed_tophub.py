"""Seed: TopHub 榜眼数据 22 个精选 hashid → SourceRegistry。

按"对 AI 选题挖掘的价值"精选，去除重复（如 36 氪只留 24h热榜 + AI频道）。
"""

import asyncio
import logging
from typing import List

from sqlalchemy import select

from app.db.session import AsyncSessionLocal
from app.models.source_registry import SourceRegistry, SOURCE_TYPE_TOPHUB

logger = logging.getLogger(__name__)


# 精选清单：(hashid, 中文名, 平台 slug, weight, tags)
TOPHUB_NODES: List[tuple] = [
    # ── AI 专用 ──
    ("ENeYylkeY4", "AIbase AI日报",          "tophub_aibase",        10, ["AI"]),
    ("proPKWkeq6", "AI产品榜 每日AI早报",       "tophub_aiproduct",     10, ["AI"]),
    ("8Rv2NjnvLw", "AI工具集",                "tophub_aitools",       10, ["AI"]),
    ("x9oz2O1oXb", "36氪 AI频道",             "tophub_36kr_ai",       10, ["AI"]),
    ("MZd7azPorO", "量子位",                  "tophub_qbitai",        10, ["AI"]),
    ("DOvnNz1vEB", "机器之心",                "tophub_jiqizhixin",    10, ["AI"]),
    ("rYqoXz8dOD", "掘金 人工智能本周最热",      "tophub_juejin_ai",     9,  ["AI"]),

    # ── 科技综合榜 ──
    ("Q1Vd5Ko85R", "36氪 24小时热榜",          "tophub_36kr",          9,  ["科技"]),
    ("5VaobgvAj1", "虎嗅网 热文",              "tophub_huxiu",         9,  ["科技"]),
    ("74Kvx59dkx", "IT之家 日榜",              "tophub_ithome",        8,  ["科技"]),
    ("Y2KeDGQdNP", "少数派 热门文章",           "tophub_sspai",         8,  ["科技"]),
    ("NRrvWYDe5z", "极客公园 每日最新",         "tophub_geekpark",      8,  ["科技"]),
    ("mproPQlvq6", "PingWest品玩 实时要闻",     "tophub_pingwest",      8,  ["科技"]),
    ("KGoRlY5dl6", "晚点LatePost",            "tophub_latepost",      9,  ["科技"]),
    ("L4MdAA1dxD", "钛媒体 热门文章",           "tophub_tmtpost",       8,  ["科技"]),

    # ── 海外科技源 ──
    ("KMZd7jGvrO", "The Verge Today",        "tophub_theverge",      9,  ["科技"]),
    ("WYKd6mmvaP", "TechCrunch Today",       "tophub_techcrunch",    9,  ["科技"]),
    ("7GdabqLeQy", "MIT Technology Review",  "tophub_mit_tr",        10, ["AI"]),
    ("Ywv4aA9dPa", "麻省理工科技评论",          "tophub_mit_tr_zh",     10, ["AI"]),

    # ── 微信公众号 ──
    ("5PdMaaadmg", "微信‧科技 24h热文榜",       "tophub_wx_tech",       10, ["AI","微信公众号"]),

    # ── 知乎科技 ──
    ("mproPpoq6O", "知乎热榜",                 "tophub_zhihu_hot",     7,  ["综合"]),
    ("Dgey97qeZq", "知乎 数码热榜",             "tophub_zhihu_digital", 8,  ["科技"]),

    # ── 开发者源 ──
    ("rYqoXQ8vOD", "GitHub Trending Today",  "tophub_github_today",  9,  ["AI","开发者"]),
    ("qYwv4JxePa", "Hacker News",            "tophub_hn",            8,  ["AI","开发者"]),
    ("LBwdG0jePx", "Product Hunt 今日新产品", "tophub_producthunt",   8,  ["AI","产品"]),
]


# 同时禁用与 TopHub 重复的旧 web 源（避免一份内容抓两次）
DEPRECATE_WEB_PLATFORMS = [
    "36kr", "qbitai", "jiqizhixin", "ithome", "huxiu", "sspai",
    "appso", "github_trending", "producthunt",
    "tophub_tech", "tophub_news",  # 旧的 web 模式 TopHub 入口
]


async def _upsert(db, hashid: str, name: str, platform: str, weight: int, tags: list) -> str:
    existing = (await db.execute(
        select(SourceRegistry).where(SourceRegistry.platform == platform)
    )).scalar_one_or_none()

    is_wx = "微信公众号" in tags
    description = f"TopHub 榜单接入：{name}"
    fetch_config = {"hashid": hashid, "limit": 50}

    if existing:
        existing.name = name
        existing.source_type = SOURCE_TYPE_TOPHUB
        existing.url = None
        existing.direction_tags = tags
        existing.weight = weight
        existing.fetch_config = fetch_config
        existing.enabled = True
        existing.requires_auth = False
        existing.auth_status = "ok"
        existing.description = description
        existing.tier = 1 if is_wx else None
        return "updated"

    db.add(SourceRegistry(
        name=name,
        platform=platform,
        source_type=SOURCE_TYPE_TOPHUB,
        url=None,
        tier=1 if is_wx else None,
        direction_tags=tags,
        weight=weight,
        requires_auth=False,
        auth_status="ok",
        fetch_strategy="cron",
        fetch_config=fetch_config,
        enabled=True,
        description=description,
    ))
    return "created"


async def run(db) -> dict:
    stats = {"created": 0, "updated": 0, "deprecated": 0}
    for hashid, name, platform, weight, tags in TOPHUB_NODES:
        outcome = await _upsert(db, hashid, name, platform, weight, tags)
        stats[outcome] += 1

    # 禁用重复的 web 源
    if DEPRECATE_WEB_PLATFORMS:
        for plat in DEPRECATE_WEB_PLATFORMS:
            src = (await db.execute(
                select(SourceRegistry).where(SourceRegistry.platform == plat)
            )).scalar_one_or_none()
            if src and src.enabled:
                src.enabled = False
                src.description = (src.description or "") + " | TopHub 替代后弃用"
                stats["deprecated"] += 1

    await db.commit()
    logger.info(f"seed_tophub: {stats}")
    return stats


async def _main():
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    async with AsyncSessionLocal() as db:
        result = await run(db)
    print(f"Done: {result}")


if __name__ == "__main__":
    asyncio.run(_main())
