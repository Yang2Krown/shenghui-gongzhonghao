"""TopHub（榜眼数据）API adapter。

文档：https://www.tophubdata.com/documentation
直接调 GET /nodes/{hashid} 拿榜单 items，免去解析 HTML。

SourceRegistry.fetch_config:
- hashid: 必填（TopHub 榜单 ID）
- limit: 可选，截取前 N 条（默认全量）
"""

import logging
from datetime import datetime
from typing import List, Optional

import httpx

from app.core.config import settings
from app.models.source_registry import SourceRegistry, SourceAccount, SOURCE_TYPE_TOPHUB
from app.services.scraping.base import FetchedItem, SourceAdapter

logger = logging.getLogger(__name__)


class TopHubAdapter(SourceAdapter):
    source_type = SOURCE_TYPE_TOPHUB
    TIMEOUT = 15

    async def fetch(
        self,
        source: SourceRegistry,
        *,
        accounts: Optional[List[SourceAccount]] = None,
        since: Optional[datetime] = None,
    ) -> List[FetchedItem]:
        if not settings.TOPHUB_API_KEY:
            logger.error("TOPHUB_API_KEY 未配置")
            return []

        cfg = source.fetch_config or {}
        hashid = cfg.get("hashid")
        if not hashid:
            logger.warning(f"TopHub source {source.platform} 缺少 hashid")
            return []

        limit = int(cfg.get("limit", 50))
        url = f"{settings.TOPHUB_API_BASE}/nodes/{hashid}"

        async with httpx.AsyncClient(timeout=self.TIMEOUT) as client:
            try:
                resp = await client.get(
                    url,
                    headers={"Authorization": settings.TOPHUB_API_KEY},
                )
                resp.raise_for_status()
                data = resp.json()
            except Exception as e:
                logger.error(f"TopHub [{source.platform}] 请求失败: {e}")
                return []

        if data.get("error"):
            logger.error(f"TopHub [{source.platform}] API 错误: {data}")
            return []

        node = data.get("data", {})
        items_raw = node.get("items", [])

        items: List[FetchedItem] = []
        for it in items_raw[:limit]:
            url_field = (it.get("url") or "").strip()
            title = (it.get("title") or "").strip()
            if not url_field or not title:
                continue

            # extra 是热度文本（"455 万热度"），把它放进 engagement
            extra = it.get("extra")
            engagement = {"extra_label": extra} if extra else {}

            items.append(FetchedItem(
                title=title,
                url=url_field,
                summary=(it.get("description") or "").strip()[:500] or None,
                published_at=None,  # /nodes/{hashid} 不返回时间，需要 /historys 才有
                engagement=engagement,
                extras={
                    "tophub_hashid": hashid,
                    "tophub_node_name": node.get("name"),
                    "tophub_display": node.get("display"),
                    "thumbnail": it.get("thumbnail"),
                },
            ))

        logger.info(f"TopHub [{source.platform}] 拉回 {len(items)} 条 (hashid={hashid})")
        return items
