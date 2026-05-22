"""GitHub Trending adapter：Jina Reader 读 trending 页 → 提取 owner/repo。

fetch_config 可选：
- language: "python" / "typescript" / "" (all)
- since: "daily" / "weekly" / "monthly"
- limit: int
"""

import logging
import re
from datetime import datetime
from typing import List, Optional

from app.models.source_registry import SourceRegistry, SourceAccount, SOURCE_TYPE_GITHUB
from app.services.scraping.agent_reach_runner import agent_reach_client
from app.services.scraping.base import FetchedItem, SourceAdapter

logger = logging.getLogger(__name__)


# 匹配 GitHub repo URL：https://github.com/owner/repo （path 段恰好 2 段）
REPO_RE = re.compile(r"https?://github\.com/([\w.-]+)/([\w.-]+)(?:[/?#]|$)")


class GitHubTrendingAdapter(SourceAdapter):
    source_type = SOURCE_TYPE_GITHUB

    DEFAULT_LIMIT = 25

    async def fetch(
        self,
        source: SourceRegistry,
        *,
        accounts: Optional[List[SourceAccount]] = None,
        since: Optional[datetime] = None,
    ) -> List[FetchedItem]:
        cfg = source.fetch_config or {}
        language = cfg.get("language", "")
        period = cfg.get("since", "daily")
        limit = int(cfg.get("limit", self.DEFAULT_LIMIT))

        url = "https://github.com/trending"
        if language:
            url += f"/{language}"
        url += f"?since={period}"

        try:
            markdown = await agent_reach_client.read_url(url)
        except Exception as e:
            logger.error(f"GitHub Trending 读取失败 {url}: {e}")
            return []

        return _extract_repos(markdown, limit=limit)


def _extract_repos(markdown: str, *, limit: int) -> List[FetchedItem]:
    seen: set[str] = set()
    items: List[FetchedItem] = []

    for m in REPO_RE.finditer(markdown or ""):
        owner, repo = m.group(1), m.group(2)
        # 过滤 GitHub 自身的导航路径
        if owner in {"trending", "topics", "marketplace", "explore", "settings",
                      "login", "join", "features", "pricing", "about", "site",
                      "events", "search", "notifications"}:
            continue
        slug = f"{owner}/{repo}"
        if slug in seen:
            continue
        seen.add(slug)
        items.append(FetchedItem(
            title=slug,
            url=f"https://github.com/{slug}",
            summary=None,
            extras={"owner": owner, "repo": repo, "source": "github_trending"},
        ))
        if len(items) >= limit:
            break
    return items
