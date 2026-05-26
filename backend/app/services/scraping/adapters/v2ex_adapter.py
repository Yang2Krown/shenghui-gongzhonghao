"""V2EX 公开 API adapter（无需 cookie）。

文档：https://www.v2ex.com/p/7v9TEc53
端点：
- /api/topics/hot.json                    全站热门
- /api/topics/show.json?node_name=tech    指定节点

SourceRegistry.fetch_config:
- node_name: 必填（tech / python / programmer / qna / jobs ...）
- limit: 可选（默认 30）
"""

import logging
from datetime import datetime
from typing import List, Optional

import httpx

from app.core.config import settings
from app.models.source_registry import SourceRegistry, SourceAccount, SOURCE_TYPE_V2EX
from app.services.scraping.base import FetchedItem, SourceAdapter

logger = logging.getLogger(__name__)


class V2EXAdapter(SourceAdapter):
    source_type = SOURCE_TYPE_V2EX
    TIMEOUT = 15
    BASE = "https://www.v2ex.com/api"
    UA = "AIContentHub/1.0 (https://github.com/your-org)"

    async def fetch(
        self,
        source: SourceRegistry,
        *,
        accounts: Optional[List[SourceAccount]] = None,
        since: Optional[datetime] = None,
    ) -> List[FetchedItem]:
        cfg = source.fetch_config or {}
        node_name = cfg.get("node_name")
        limit = int(cfg.get("limit", 30))

        # node_name 缺失就拉全站热门
        if node_name:
            url = f"{self.BASE}/topics/show.json"
            params = {"node_name": node_name}
        else:
            url = f"{self.BASE}/topics/hot.json"
            params = {}

        async with httpx.AsyncClient(timeout=self.TIMEOUT, headers={"User-Agent": self.UA}, proxy=settings.HTTP_PROXY or None) as client:
            try:
                resp = await client.get(url, params=params)
                resp.raise_for_status()
                data = resp.json()
            except Exception as e:
                logger.error(f"V2EX [{source.platform}] 请求失败: {e}")
                return []

        items: List[FetchedItem] = []
        for t in (data or [])[:limit]:
            url_field = t.get("url") or ""
            title = (t.get("title") or "").strip()
            if not url_field or not title:
                continue

            published_at = None
            if t.get("created"):
                try:
                    published_at = datetime.utcfromtimestamp(int(t["created"]))
                except Exception:
                    pass

            items.append(FetchedItem(
                title=title,
                url=url_field,
                summary=(t.get("content_rendered") or t.get("content") or "").strip()[:500] or None,
                author=((t.get("member") or {}).get("username")) or None,
                published_at=published_at,
                engagement={
                    "score": t.get("replies", 0),
                    "comments": t.get("replies", 0),
                },
                extras={
                    "v2ex_node": (t.get("node") or {}).get("name"),
                    "v2ex_node_title": (t.get("node") or {}).get("title"),
                    "v2ex_id": t.get("id"),
                },
            ))

        logger.info(f"V2EX [{source.platform}] 抓回 {len(items)} 条 (node={node_name or 'hot'})")
        return items
