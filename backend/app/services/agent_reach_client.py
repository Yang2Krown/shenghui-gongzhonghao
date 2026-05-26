import asyncio
import json
import logging
import re
from typing import Any, Dict, List, Optional

import feedparser
import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


class AgentReachClient:
    """Agent-Reach 工具集的 Python 封装。

    底层调用 Exa HTTP API / Jina Reader / feedparser。
    """

    JINA_READER_BASE = "https://r.jina.ai/"
    EXA_API_BASE = "https://api.exa.ai"

    def __init__(self, request_timeout: int = 30):
        self.request_timeout = request_timeout

    def _get_proxy(self) -> Optional[str]:
        return settings.HTTP_PROXY or None

    async def read_url(self, url: str) -> str:
        """通过 Jina Reader 读取任意网页，返回 Markdown 正文。"""
        target = f"{self.JINA_READER_BASE}{url}"
        async with httpx.AsyncClient(timeout=self.request_timeout, proxy=self._get_proxy()) as client:
            resp = await client.get(target)
            resp.raise_for_status()
            return resp.text

    async def search_web(
        self,
        query: str,
        num_results: int = 10,
        include_domains: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """Exa 全网语义搜索（HTTP API）。返回 [{title, url, published, author, snippet}]"""
        if not settings.EXA_API_KEY:
            raise RuntimeError("EXA_API_KEY 未配置")

        payload: Dict[str, Any] = {
            "query": query,
            "numResults": num_results,
            "type": "auto",
            "contents": {"highlights": True},
        }
        if include_domains:
            payload["includeDomains"] = include_domains

        async with httpx.AsyncClient(timeout=self.request_timeout, proxy=self._get_proxy()) as client:
            resp = await client.post(
                f"{self.EXA_API_BASE}/search",
                json=payload,
                headers={
                    "x-api-key": settings.EXA_API_KEY,
                    "Content-Type": "application/json",
                },
            )
            resp.raise_for_status()
            data = resp.json()

        results = []
        for r in data.get("results", []):
            highlights = r.get("highlights") or []
            snippet = highlights[0] if highlights else r.get("text") or ""
            results.append({
                "title": r.get("title", ""),
                "url": r.get("url", ""),
                "published": r.get("publishedDate"),
                "author": r.get("author"),
                "snippet": snippet,
            })
        return results

    async def search_wechat(self, keyword: str, num_results: int = 10) -> List[Dict[str, Any]]:
        """微信公众号搜索：限定 mp.weixin.qq.com 域名。"""
        candidates = await self.search_web(
            query=keyword,
            num_results=num_results * 3,
            include_domains=["mp.weixin.qq.com"],
        )
        wechat = [r for r in candidates if "mp.weixin.qq.com" in (r.get("url") or "")]
        return wechat[:num_results]

    async def crawl_wechat(self, urls: List[str], max_characters: int = 10000) -> str:
        """通过 Exa 抓取微信公众号文章全文。"""
        if not settings.EXA_API_KEY:
            raise RuntimeError("EXA_API_KEY 未配置")

        async with httpx.AsyncClient(timeout=self.request_timeout, proxy=self._get_proxy()) as client:
            resp = await client.post(
                f"{self.EXA_API_BASE}/contents",
                json={"urls": urls, "text": {"maxCharacters": max_characters}},
                headers={
                    "x-api-key": settings.EXA_API_KEY,
                    "Content-Type": "application/json",
                },
            )
            resp.raise_for_status()
            data = resp.json()

        texts = []
        for r in data.get("results", []):
            texts.append(r.get("text", ""))
        return "\n\n".join(texts)

    async def fetch_rss(self, feed_url: str, limit: int = 30) -> List[Dict[str, Any]]:
        """解析 RSS/Atom feed，返回标准化条目列表。"""
        def _parse():
            return feedparser.parse(feed_url)

        feed = await asyncio.to_thread(_parse)
        if feed.bozo and not feed.entries:
            logger.warning(f"RSS 解析失败: {feed_url} bozo={feed.bozo_exception}")
            return []

        items = []
        for entry in feed.entries[:limit]:
            items.append({
                "title": getattr(entry, "title", "").strip(),
                "url": getattr(entry, "link", ""),
                "summary": self._clean_html(getattr(entry, "summary", "") or getattr(entry, "description", "")),
                "published": getattr(entry, "published", None) or getattr(entry, "updated", None),
                "author": getattr(entry, "author", None),
            })
        return items

    @staticmethod
    def _clean_html(text: str) -> str:
        text = re.sub(r"<[^>]+>", "", text or "")
        text = re.sub(r"\s+", " ", text).strip()
        return text[:500]


agent_reach_client = AgentReachClient()
