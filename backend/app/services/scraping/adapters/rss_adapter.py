"""RSS adapter：吃 SourceRegistry.url，调 feedparser，返回 FetchedItem 列表。"""

import logging
from datetime import datetime
from email.utils import parsedate_to_datetime
from typing import Any, List, Optional

from app.models.source_registry import SourceRegistry, SourceAccount, SOURCE_TYPE_RSS
from app.services.scraping.agent_reach_runner import agent_reach_client
from app.services.scraping.base import FetchedItem, SourceAdapter

logger = logging.getLogger(__name__)


class RSSAdapter(SourceAdapter):
    source_type = SOURCE_TYPE_RSS

    DEFAULT_LIMIT = 50  # 尽量取全一个源当天的条目，避免截断（下游会去重）

    async def fetch(
        self,
        source: SourceRegistry,
        *,
        accounts: Optional[List[SourceAccount]] = None,
        since: Optional[datetime] = None,
    ) -> List[FetchedItem]:
        if not source.url:
            logger.warning(f"RSS source {source.platform} 缺少 url")
            return []

        limit = int((source.fetch_config or {}).get("limit", self.DEFAULT_LIMIT))
        entries = await agent_reach_client.fetch_rss(source.url, limit=limit)

        items: List[FetchedItem] = []
        for e in entries:
            url = (e.get("url") or "").strip()
            if not url:
                continue
            items.append(FetchedItem(
                title=(e.get("title") or url).strip(),
                url=url,
                summary=e.get("summary"),
                author=e.get("author"),
                published_at=_parse_dt(e.get("published")),
                extras={"feed_platform": source.platform},
            ))
        return items


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
