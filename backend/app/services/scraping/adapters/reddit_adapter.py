"""Reddit 公开 JSON API adapter（无需 cookie）。

任何 reddit 页面后面加 .json 就是免认证 JSON 输出。
- https://www.reddit.com/r/LocalLLaMA/hot.json?limit=25

SourceRegistry.fetch_config:
- subreddit: 必填（不带 r/ 前缀，如 "LocalLLaMA"）
- sort: hot / new / top / rising（默认 hot）
- time: hour / day / week / month / year / all（仅当 sort=top 时有效）
- limit: 默认 25，最大 100
- min_score: 可选，过滤低分帖（默认 5）
"""

import logging
from datetime import datetime
from typing import List, Optional

import httpx

from app.core.config import settings
from app.models.source_registry import SourceRegistry, SourceAccount, SOURCE_TYPE_REDDIT
from app.services.scraping.base import FetchedItem, SourceAdapter

logger = logging.getLogger(__name__)


class RedditAdapter(SourceAdapter):
    source_type = SOURCE_TYPE_REDDIT
    TIMEOUT = 20
    BASE = "https://www.reddit.com"
    # Reddit 要求 UA 包含 by/u/your_username 否则可能 429
    UA = "AIContentHub/1.0 (compatible; by /u/aicontent_bot)"

    async def fetch(
        self,
        source: SourceRegistry,
        *,
        accounts: Optional[List[SourceAccount]] = None,
        since: Optional[datetime] = None,
    ) -> List[FetchedItem]:
        cfg = source.fetch_config or {}
        sub = cfg.get("subreddit")
        if not sub:
            logger.warning(f"Reddit source {source.platform} 缺少 subreddit")
            return []

        sort = cfg.get("sort", "hot")
        limit = int(cfg.get("limit", 25))
        min_score = int(cfg.get("min_score", 5))

        url = f"{self.BASE}/r/{sub}/{sort}.json"
        params = {"limit": limit}
        if sort == "top" and cfg.get("time"):
            params["t"] = cfg["time"]

        async with httpx.AsyncClient(timeout=self.TIMEOUT, headers={"User-Agent": self.UA}, proxy=settings.HTTP_PROXY or None) as client:
            try:
                resp = await client.get(url, params=params)
                resp.raise_for_status()
                data = resp.json()
            except Exception as e:
                logger.error(f"Reddit [{source.platform}] 请求失败: {e}")
                return []

        posts = (data.get("data") or {}).get("children") or []
        items: List[FetchedItem] = []
        for p in posts:
            d = p.get("data") or {}
            title = (d.get("title") or "").strip()
            permalink = d.get("permalink") or ""
            external_url = d.get("url") or ""
            if not title:
                continue

            # 优先用 permalink（指向 reddit 讨论），否则用外链
            url_field = f"{self.BASE}{permalink}" if permalink else external_url
            if not url_field:
                continue

            score = d.get("score", 0) or 0
            if score < min_score:
                continue

            published_at = None
            if d.get("created_utc"):
                try:
                    published_at = datetime.utcfromtimestamp(int(d["created_utc"]))
                except Exception:
                    pass

            # selftext 优先做 summary（reddit 上的讨论文本）
            summary = (d.get("selftext") or "").strip()[:500] or None

            items.append(FetchedItem(
                title=title,
                url=url_field,
                summary=summary,
                author=d.get("author") or None,
                published_at=published_at,
                engagement={
                    "score": score,
                    "comments": d.get("num_comments", 0) or 0,
                    "upvote_ratio": d.get("upvote_ratio"),
                },
                extras={
                    "subreddit": d.get("subreddit"),
                    "post_id": d.get("id"),
                    "is_self": d.get("is_self"),
                    "external_url": external_url if external_url != url_field else None,
                    "flair": d.get("link_flair_text"),
                },
            ))

        logger.info(f"Reddit [{source.platform}] 抓回 {len(items)} 条 (r/{sub}/{sort})")
        return items
