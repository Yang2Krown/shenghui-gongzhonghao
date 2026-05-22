import asyncio
import logging
from datetime import datetime
from email.utils import parsedate_to_datetime
from typing import Any, Dict, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.crud.topic import topic as topic_crud
from app.schemas.topic import TopicCreate, TopicUpdate
from app.services.agent_reach_client import agent_reach_client

logger = logging.getLogger(__name__)


# 默认数据源配置。后续可以挪到数据库或 settings 里给运营在后台编辑。
DEFAULT_SOURCES: List[Dict[str, Any]] = [
    {
        "platform": "wechat",
        "kind": "wechat_search",
        "keywords": ["AI Agent", "大模型", "AI 公众号", "ChatGPT", "DeepSeek"],
        "limit_per_keyword": 5,
    },
    {
        "platform": "web_search",
        "kind": "web_search",
        "keywords": ["AI 最新进展", "AI Agent 框架", "大模型 应用"],
        "limit_per_keyword": 5,
    },
    {
        "platform": "36kr",
        "kind": "rss",
        "feed_url": "https://36kr.com/feed",
        "limit": 30,
    },
    {
        "platform": "ithome",
        "kind": "rss",
        "feed_url": "https://www.ithome.com/rss/",
        "limit": 30,
    },
]


class ScraperService:
    """数据抓取服务：基于 Agent-Reach 工具集拉取多源资讯。"""

    def __init__(self):
        self.scrape_timeout = settings.SCRAPE_TIMEOUT
        self.sources = DEFAULT_SOURCES

    async def fetch_and_save_topics(
        self,
        db: AsyncSession,
        *,
        platforms: Optional[List[str]] = None,
        days: int = 1,
    ) -> Dict[str, Any]:
        """抓取并入库。platforms 用于过滤 DEFAULT_SOURCES 里的 platform 字段。"""
        sources = self.sources
        if platforms:
            sources = [s for s in sources if s["platform"] in platforms]

        results = {
            "new_topics": 0,
            "updated_topics": 0,
            "failed_topics": 0,
            "platforms": {},
        }

        tasks = [self._fetch_source(source) for source in sources]
        per_source = await asyncio.gather(*tasks, return_exceptions=True)

        for source, outcome in zip(sources, per_source):
            platform = source["platform"]
            if isinstance(outcome, Exception):
                logger.error(f"数据源 {platform} 抓取失败: {outcome}")
                results["failed_topics"] += 1
                results["platforms"][platform] = {"status": "failed", "error": str(outcome)}
                continue

            items = outcome
            new_count, updated_count = await self._persist(db, platform, items)
            results["new_topics"] += new_count
            results["updated_topics"] += updated_count
            results["platforms"][platform] = {
                "status": "ok",
                "new_topics": new_count,
                "updated_topics": updated_count,
                "total_scraped": len(items),
            }

        logger.info(f"选题抓取完成: new={results['new_topics']} updated={results['updated_topics']} failed={results['failed_topics']}")
        return results

    async def _fetch_source(self, source: Dict[str, Any]) -> List[Dict[str, Any]]:
        kind = source["kind"]
        if kind == "wechat_search":
            return await self._fetch_search(source, channel="wechat")
        if kind == "web_search":
            return await self._fetch_search(source, channel="web")
        if kind == "rss":
            return await self._fetch_rss(source)
        logger.warning(f"未知数据源类型: {kind}")
        return []

    async def _fetch_search(self, source: Dict[str, Any], channel: str) -> List[Dict[str, Any]]:
        keywords: List[str] = source.get("keywords", [])
        limit = source.get("limit_per_keyword", 5)
        platform = source["platform"]
        seen_urls: set[str] = set()
        items: List[Dict[str, Any]] = []
        for kw in keywords:
            try:
                if channel == "wechat":
                    results = await agent_reach_client.search_wechat(kw, num_results=limit)
                else:
                    results = await agent_reach_client.search_web(kw, num_results=limit)
            except Exception as e:
                logger.warning(f"[{platform}] 关键词 '{kw}' 搜索失败: {e}")
                continue

            for r in results:
                url = r.get("url")
                if not url or url in seen_urls:
                    continue
                seen_urls.add(url)
                items.append({
                    "title": r.get("title") or url,
                    "source_url": url,
                    "content_summary": (r.get("snippet") or "")[:500] or None,
                    "author": r.get("author"),
                    "published_at": self._parse_dt(r.get("published")),
                    "keywords": [kw],
                })
        return items

    async def _fetch_rss(self, source: Dict[str, Any]) -> List[Dict[str, Any]]:
        feed_url = source["feed_url"]
        limit = source.get("limit", 30)
        try:
            entries = await agent_reach_client.fetch_rss(feed_url, limit=limit)
        except Exception as e:
            logger.warning(f"RSS 拉取失败 {feed_url}: {e}")
            return []

        items = []
        for e in entries:
            url = e.get("url")
            if not url:
                continue
            items.append({
                "title": e.get("title") or url,
                "source_url": url,
                "content_summary": e.get("summary") or None,
                "author": e.get("author"),
                "published_at": self._parse_dt(e.get("published")),
                "keywords": [],
            })
        return items

    async def _persist(self, db: AsyncSession, platform: str, items: List[Dict[str, Any]]) -> tuple[int, int]:
        new_count, updated_count = 0, 0
        for item in items:
            payload = {
                "title": item["title"][:500],
                "source_platform": platform,
                "source_url": item["source_url"][:1000],
                "content_summary": item.get("content_summary"),
                "author": (item.get("author") or "")[:200] or None,
                "published_at": item.get("published_at"),
                "keywords": item.get("keywords") or [],
            }
            existing = await topic_crud.get_by_source_url(db, source_url=payload["source_url"])
            if existing:
                update_data = TopicUpdate(
                    title=payload["title"],
                    content_summary=payload["content_summary"],
                    keywords=payload["keywords"],
                )
                await topic_crud.update(db, db_obj=existing, obj_in=update_data)
                updated_count += 1
            else:
                create_data = TopicCreate(**payload)
                await topic_crud.create(db, obj_in=create_data)
                new_count += 1
        return new_count, updated_count

    async def parse_content(self, url: str) -> str:
        """通过 Jina Reader 读取任意网页的正文（Markdown）。"""
        try:
            return await agent_reach_client.read_url(url)
        except Exception as e:
            logger.error(f"读取网页失败 {url}: {e}")
            raise

    @staticmethod
    def _parse_dt(value: Any) -> Optional[datetime]:
        if not value:
            return None
        if isinstance(value, datetime):
            return value
        if isinstance(value, str):
            for parser in (
                lambda s: datetime.fromisoformat(s.replace("Z", "+00:00")),
                parsedate_to_datetime,
            ):
                try:
                    dt = parser(value)
                    if dt.tzinfo is not None:
                        dt = dt.replace(tzinfo=None)
                    return dt
                except Exception:
                    continue
        return None


scraper_service = ScraperService()
