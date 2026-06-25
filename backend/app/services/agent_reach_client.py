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

    def _client_kwargs(self, **extra: Any) -> Dict[str, Any]:
        """构造 httpx.AsyncClient 参数，统一处理代理与 httpx 版本差异。

        仅在配了代理时才传该参数：httpx>=0.26 用 proxy=、更早用 proxies=，
        且两版本传 None 都会报错——所以不配代理就干脆不传这个 key。
        """
        kwargs: Dict[str, Any] = {"timeout": self.request_timeout, **extra}
        proxy = self._get_proxy()
        if proxy:
            _ver = tuple(int(x) for x in httpx.__version__.split(".")[:2])
            kwargs["proxy" if _ver >= (0, 26) else "proxies"] = proxy
        return kwargs

    async def read_url(self, url: str) -> str:
        """通过 Jina Reader 读取任意网页，返回 Markdown 正文。"""
        target = f"{self.JINA_READER_BASE}{url}"
        async with httpx.AsyncClient(**self._client_kwargs()) as client:
            resp = await client.get(target)
            resp.raise_for_status()
            return resp.text

    async def search_web(
        self,
        query: str,
        num_results: int = 10,
        include_domains: Optional[List[str]] = None,
        text_chars: Optional[int] = None,
        start_published_date: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Exa 全网语义搜索（HTTP API）。返回 [{title, url, published, author, snippet}]。

        计费坑：contents 是按「返回条数」逐条收费的（约 $0.001/条），所以 num_results
        要按真实需要给，别盲目放大；highlights / text 都算内容费。
        text_chars 给定时返回正文（maxCharacters=text_chars），可直接当正文用、省一次 /contents；
        否则只取 highlights 片段（便宜的预览，用于排序/筛选）。
        start_published_date：ISO 8601 时间，只要该时间之后发布的内容（如只要近一个月）。
        """
        if not settings.EXA_API_KEY:
            raise RuntimeError("EXA_API_KEY 未配置")

        contents = {"text": {"maxCharacters": text_chars}} if text_chars else {"highlights": True}
        payload: Dict[str, Any] = {
            "query": query,
            "numResults": num_results,
            "type": "auto",
            "contents": contents,
        }
        if include_domains:
            payload["includeDomains"] = include_domains
        if start_published_date:
            payload["startPublishedDate"] = start_published_date

        async with httpx.AsyncClient(**self._client_kwargs()) as client:
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
            if text_chars:
                snippet = r.get("text") or ""
            else:
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

    async def search_wechat(
        self,
        keyword: str,
        num_results: int = 10,
        text_chars: Optional[int] = None,
        start_published_date: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """微信公众号搜索：限定 mp.weixin.qq.com 域名。

        includeDomains 已保证结果都是公众号，不再 ×N 过量请求（每多一条都按内容费收钱）。
        text_chars 给定时连正文一并搜回，省掉后续 crawl_wechat 的额外 /contents 调用。
        start_published_date：只要该时间之后发布的爆文（如只要近一个月）。
        """
        candidates = await self.search_web(
            query=keyword,
            num_results=num_results,
            include_domains=["mp.weixin.qq.com"],
            text_chars=text_chars,
            start_published_date=start_published_date,
        )
        wechat = [r for r in candidates if "mp.weixin.qq.com" in (r.get("url") or "")]
        return wechat[:num_results]

    async def crawl_wechat(self, urls: List[str], max_characters: int = 10000) -> str:
        """通过 Exa 抓取微信公众号文章全文。"""
        if not settings.EXA_API_KEY:
            raise RuntimeError("EXA_API_KEY 未配置")

        async with httpx.AsyncClient(**self._client_kwargs()) as client:
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
        """解析 RSS/Atom feed，返回标准化条目列表。

        先用 httpx 带超时下载内容，再交给 feedparser 解析。
        关键：feedparser.parse(url) 自带的 urllib 无超时，被墙/卡死的源会无限挂起，
        把整批采集拖到 Celery 超时被杀、commit 丢失。必须用带超时的 httpx 拉取。
        """
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0 Safari/537.36"
            )
        }
        try:
            async with httpx.AsyncClient(
                **self._client_kwargs(follow_redirects=True, headers=headers)
            ) as client:
                resp = await client.get(feed_url)
                resp.raise_for_status()
                content = resp.content
        except Exception as e:
            logger.warning(f"RSS 下载失败: {feed_url} {type(e).__name__}: {e}")
            return []

        feed = await asyncio.to_thread(feedparser.parse, content)
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
