"""Hacker News adapter：走官方 firebase API，免费、无 cookie。

fetch_config:
- endpoint: "topstories" / "newstories" / "beststories" (默认 topstories)
- limit: int (默认 30)
"""

import asyncio
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

import httpx

from app.core.config import settings
from app.models.source_registry import SourceRegistry, SourceAccount, SOURCE_TYPE_HACKERNEWS
from app.services.scraping.base import FetchedItem, SourceAdapter

logger = logging.getLogger(__name__)


BASE = "https://hacker-news.firebaseio.com/v0"


class HackerNewsAdapter(SourceAdapter):
    source_type = SOURCE_TYPE_HACKERNEWS

    DEFAULT_LIMIT = 30
    TIMEOUT = 15

    async def fetch(
        self,
        source: SourceRegistry,
        *,
        accounts: Optional[List[SourceAccount]] = None,
        since: Optional[datetime] = None,
    ) -> List[FetchedItem]:
        cfg = source.fetch_config or {}
        endpoint = cfg.get("endpoint", "topstories")
        limit = int(cfg.get("limit", self.DEFAULT_LIMIT))

        async with httpx.AsyncClient(timeout=self.TIMEOUT, proxy=settings.HTTP_PROXY or None) as client:
            try:
                resp = await client.get(f"{BASE}/{endpoint}.json")
                resp.raise_for_status()
                ids: List[int] = resp.json()[:limit]
            except Exception as e:
                logger.error(f"HN {endpoint} 列表拉取失败: {e}")
                return []

            stories = await asyncio.gather(
                *[_fetch_story(client, sid) for sid in ids],
                return_exceptions=True,
            )

        items: List[FetchedItem] = []
        for s in stories:
            if isinstance(s, Exception) or not s:
                continue
            title = s.get("title") or ""
            url = s.get("url") or f"https://news.ycombinator.com/item?id={s.get('id')}"
            if not title:
                continue
            published_at = datetime.utcfromtimestamp(s["time"]) if s.get("time") else None
            items.append(FetchedItem(
                title=title,
                url=url,
                author=s.get("by"),
                summary=None,
                published_at=published_at,
                engagement={
                    "score": s.get("score", 0),
                    "comments": s.get("descendants", 0),
                },
                extras={"hn_id": s.get("id"), "hn_type": s.get("type")},
            ))
        return items


async def _fetch_story(client: httpx.AsyncClient, story_id: int) -> Optional[Dict[str, Any]]:
    try:
        r = await client.get(f"{BASE}/item/{story_id}.json")
        r.raise_for_status()
        return r.json()
    except Exception as e:
        logger.warning(f"HN item {story_id} 拉取失败: {e}")
        return None
