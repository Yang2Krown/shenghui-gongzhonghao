"""通用网页 adapter：Jina Reader 读首页 → 提取文章链接。

适合没有 RSS 的内容站点（如 AIHOT、各官方博客索引页等）。
策略：抓 markdown → 正则提 `[title](url)` → 过滤同域 + 启发式判断"像文章"。
"""

import logging
import re
from datetime import datetime
from typing import List, Optional
from urllib.parse import urlparse

from app.models.source_registry import SourceRegistry, SourceAccount, SOURCE_TYPE_WEB
from app.services.scraping.agent_reach_runner import agent_reach_client
from app.services.scraping.base import FetchedItem, SourceAdapter

logger = logging.getLogger(__name__)


# Markdown link 抓取：[title](url)
LINK_RE = re.compile(r"\[([^\]]{4,200})\]\((https?://[^\s)]+)\)")

# "像文章"的 URL 路径 hint
ARTICLE_HINTS = re.compile(r"/(article|articles|news|post|p|story|stories|blog|read|2024|2025|2026)/", re.IGNORECASE)


class WebAdapter(SourceAdapter):
    source_type = SOURCE_TYPE_WEB

    DEFAULT_LIMIT = 30

    async def fetch(
        self,
        source: SourceRegistry,
        *,
        accounts: Optional[List[SourceAccount]] = None,
        since: Optional[datetime] = None,
    ) -> List[FetchedItem]:
        if not source.url:
            logger.warning(f"Web source {source.platform} 缺少 url")
            return []

        limit = int((source.fetch_config or {}).get("limit", self.DEFAULT_LIMIT))
        try:
            markdown = await agent_reach_client.read_url(source.url)
        except Exception as e:
            logger.error(f"Jina Reader 读取失败 {source.url}: {e}")
            return []

        items = _extract_article_links(markdown, base_url=source.url, limit=limit, platform=source.platform)
        logger.info(f"[{source.platform}] web_adapter 抽出 {len(items)} 条链接")
        return items


def _extract_article_links(markdown: str, *, base_url: str, limit: int, platform: str) -> List[FetchedItem]:
    base_host = urlparse(base_url).netloc.lower()
    seen: set[str] = set()
    items: List[FetchedItem] = []

    for m in LINK_RE.finditer(markdown or ""):
        title, url = m.group(1).strip(), m.group(2).strip()
        if not title or url in seen:
            continue

        parsed = urlparse(url)
        host = parsed.netloc.lower()

        # 同域 或 文章路径 hint
        same_domain = host.endswith(base_host) or base_host.endswith(host)
        looks_like_article = bool(ARTICLE_HINTS.search(parsed.path or ""))
        if not (same_domain and (looks_like_article or len(parsed.path) > 10)):
            continue

        # 过滤明显非文章
        if any(x in url for x in ("#", "javascript:", "mailto:")):
            continue
        if parsed.path in ("", "/"):
            continue

        seen.add(url)
        items.append(FetchedItem(
            title=title,
            url=url,
            extras={"discovered_from": base_url, "platform": platform},
        ))
        if len(items) >= limit:
            break
    return items
