"""AI HOT 独立 adapter：抓 aihot.virxact.com 三个 RSS feed，不依赖通用 RSSAdapter。

三个 feed：
  - 精选  https://aihot.virxact.com/feed.xml       （每日精编候选池，最新 50 条）
  - 全部  https://aihot.virxact.com/feed/all.xml    （全部 AI 行业内容流）
  - 日报  https://aihot.virxact.com/feed/daily.xml  （每日汇总）
"""

import asyncio
import hashlib
import logging
import re
from datetime import datetime
from app.core.timezone import utcnow
from email.utils import parsedate_to_datetime
from typing import Any, Dict, List, Optional

import feedparser
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.raw_info import RawInfo, RAW_STATE_PENDING
from app.models.source_registry import SourceRegistry

logger = logging.getLogger(__name__)

AIHOT_FEEDS = {
    "selected": {
        "url": "https://aihot.virxact.com/feed.xml",
        "name": "AI HOT 精选",
        "platform": "aihot_selected",
    },
    "all": {
        "url": "https://aihot.virxact.com/feed/all.xml",
        "name": "AI HOT 全部",
        "platform": "aihot_all",
    },
    "daily": {
        "url": "https://aihot.virxact.com/feed/daily.xml",
        "name": "AI HOT 日报",
        "platform": "aihot_daily",
    },
}

AIHOT_SOURCE_TYPE = "aihot"


def _clean_html(text: str) -> str:
    text = re.sub(r"<[^>]+>", "", text or "")
    text = re.sub(r"\s+", " ", text).strip()
    return text[:500]


def _parse_dt(value: Any) -> Optional[datetime]:
    if not value:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo is None else value.replace(tzinfo=None)
    if isinstance(value, str):
        for parser in (
            lambda s: datetime.fromisoformat(s.replace("Z", "+00:00")),
            parsedate_to_datetime,
        ):
            try:
                dt = parser(value)
                return dt if dt.tzinfo is None else dt.replace(tzinfo=None)
            except Exception:
                continue
    return None


def _dedup_hash(url: str, title: str) -> str:
    base = (url or "").strip().rstrip("/").lower()
    if not base:
        base = (title or "").strip().lower()
    return hashlib.sha256(base.encode("utf-8")).hexdigest()[:16]


async def _ensure_source_registry(db: AsyncSession, feed_key: str) -> SourceRegistry:
    """确保指定 feed 在 source_registry 中有记录。"""
    feed_conf = AIHOT_FEEDS[feed_key]
    platform = feed_conf["platform"]

    existing = (await db.execute(
        select(SourceRegistry).where(SourceRegistry.platform == platform)
    )).scalar_one_or_none()
    if existing:
        return existing

    source = SourceRegistry(
        name=feed_conf["name"],
        platform=platform,
        source_type=AIHOT_SOURCE_TYPE,
        url=feed_conf["url"],
        weight=7,
        direction_tags=["AI"],
        enabled=True,
        description=f"{feed_conf['name']} — {feed_conf['url']}",
    )
    db.add(source)
    await db.flush()
    logger.info(f"自动创建 source_registry: {platform} id={source.id}")
    return source


async def fetch_aihot(
    db: AsyncSession,
    feed_key: str = "selected",
    limit: int = 50,
) -> Dict[str, Any]:
    """抓取指定 AI HOT feed 并写入 raw_infos。

    feed_key: "selected" | "all" | "daily"
    """
    if feed_key not in AIHOT_FEEDS:
        return {"status": "error", "error": f"未知 feed_key: {feed_key}，可选: {list(AIHOT_FEEDS.keys())}"}

    feed_conf = AIHOT_FEEDS[feed_key]
    source = await _ensure_source_registry(db, feed_key)

    def _parse():
        return feedparser.parse(feed_conf["url"])

    feed = await asyncio.to_thread(_parse)
    if feed.bozo and not feed.entries:
        msg = f"AI HOT [{feed_key}] RSS 解析失败: bozo={feed.bozo_exception}"
        logger.warning(msg)
        return {"status": "error", "error": msg, "new": 0, "duplicate": 0}

    new_count = 0
    dup_count = 0

    for entry in feed.entries[:limit]:
        url = getattr(entry, "link", "").strip()
        if not url:
            continue

        existing = (await db.execute(
            select(RawInfo).where(RawInfo.url == url)
        )).scalar_one_or_none()
        if existing:
            dup_count += 1
            continue

        title = (getattr(entry, "title", "") or url).strip()
        db.add(RawInfo(
            source_registry_id=source.id,
            title=title[:500],
            url=url[:1000],
            author=(getattr(entry, "author", None) or "")[:200] or None,
            summary=_clean_html(
                getattr(entry, "summary", "") or getattr(entry, "description", "")
            ),
            published_at=_parse_dt(
                getattr(entry, "published", None) or getattr(entry, "updated", None)
            ),
            scraped_at=utcnow(),
            engagement={},
            extras={"feed_platform": feed_conf["platform"], "feed_key": feed_key},
            state=RAW_STATE_PENDING,
            dedup_hash=_dedup_hash(url, title),
        ))
        new_count += 1

    await db.flush()
    source.last_fetched_at = utcnow().isoformat()
    await db.commit()

    logger.info(f"AI HOT [{feed_key}] 完成: new={new_count} dup={dup_count}")
    return {
        "status": "ok",
        "feed_key": feed_key,
        "new": new_count,
        "duplicate": dup_count,
        "total_entries": len(feed.entries),
    }


async def fetch_aihot_all_feeds(db: AsyncSession) -> Dict[str, Any]:
    """一次性抓取全部三个 feed。"""
    results = {}
    for key in AIHOT_FEEDS:
        results[key] = await fetch_aihot(db, feed_key=key)
    return results

#精选抓取代码
# cd /www/wwwroot/gzh && docker compose -f docker-compose.prod.yml --env-file backend/.env.production exec backend python -c "
# import asyncio
# from app.services.scraping.adapters.aihot_adapter import fetch_aihot
# from app.db.session import AsyncSessionLocal

# async def run():
#     async with AsyncSessionLocal() as db:
#         r = await fetch_aihot(db, feed_key='selected')
#         print('精选:', r)

# asyncio.run(run())
# "

#测试全部动态 feed：
# cd /www/wwwroot/gzh && docker compose -f docker-compose.prod.yml --env-file backend/.env.production exec backend python -c "
# import asyncio
# from app.services.scraping.adapters.aihot_adapter import fetch_aihot
# from app.db.session import AsyncSessionLocal

# async def run():
#     async with AsyncSessionLocal() as db:
#         r = await fetch_aihot(db, feed_key='all')
#         print('全部:', r)

# asyncio.run(run())
# "

# 测试日报 feed：
# cd /www/wwwroot/gzh && docker compose -f docker-compose.prod.yml --env-file backend/.env.production exec backend python -c "
# import asyncio
# from app.services.scraping.adapters.aihot_adapter import fetch_aihot
# from app.db.session import AsyncSessionLocal

# async def run():
#     async with AsyncSessionLocal() as db:
#         r = await fetch_aihot(db, feed_key='daily')
#         print('日报:', r)

# asyncio.run(run())
# "
