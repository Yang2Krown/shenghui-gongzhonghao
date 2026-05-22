import asyncio
import json
import logging
import re
from typing import Any, Dict, List, Optional

import feedparser
import httpx

logger = logging.getLogger(__name__)


class AgentReachClient:
    """Agent-Reach 工具集的 Python 封装。

    底层调用 mcporter / Jina Reader / feedparser，把外部 CLI / HTTP
    统一成可在后端 service 里直接 await 的方法。
    """

    JINA_READER_BASE = "https://r.jina.ai/"

    def __init__(self, mcporter_bin: str = "mcporter", request_timeout: int = 30):
        self.mcporter_bin = mcporter_bin
        self.request_timeout = request_timeout

    async def read_url(self, url: str) -> str:
        """通过 Jina Reader 读取任意网页，返回 Markdown 正文。"""
        target = f"{self.JINA_READER_BASE}{url}"
        async with httpx.AsyncClient(timeout=self.request_timeout) as client:
            resp = await client.get(target)
            resp.raise_for_status()
            return resp.text

    async def search_web(
        self,
        query: str,
        num_results: int = 10,
        include_domains: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """Exa 全网语义搜索。返回 [{title, url, published, author, snippet}]"""
        args: Dict[str, Any] = {"query": query, "numResults": num_results}
        if include_domains:
            args["includeDomains"] = include_domains
        raw = await self._mcporter_call("exa.web_search_exa", args)
        return self._parse_exa_search_text(raw)

    async def search_wechat(self, keyword: str, num_results: int = 10) -> List[Dict[str, Any]]:
        """微信公众号搜索：限定 mp.weixin.qq.com 域名（Exa 软过滤 + 后处理硬过滤）。"""
        candidates = await self.search_web(
            query=keyword,
            num_results=num_results * 3,
            include_domains=["mp.weixin.qq.com"],
        )
        wechat = [r for r in candidates if "mp.weixin.qq.com" in (r.get("url") or "")]
        return wechat[:num_results]

    async def crawl_wechat(self, urls: List[str], max_characters: int = 10000) -> str:
        """通过 Exa 抓取微信公众号文章全文。"""
        args = {"urls": urls, "maxCharacters": max_characters}
        return await self._mcporter_call("exa.crawling_exa", args)

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

    async def _mcporter_call(self, tool: str, args: Dict[str, Any]) -> str:
        """调用 mcporter call '<tool>(<args>)' 并返回原始 stdout。"""
        args_str = ", ".join(f"{k}: {json.dumps(v, ensure_ascii=False)}" for k, v in args.items())
        cmd_arg = f"{tool}({args_str})"
        proc = await asyncio.create_subprocess_exec(
            self.mcporter_bin, "call", cmd_arg,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=self.request_timeout * 2)
        except asyncio.TimeoutError:
            proc.kill()
            raise RuntimeError(f"mcporter call 超时: {tool}")

        if proc.returncode != 0:
            raise RuntimeError(f"mcporter call 失败 ({proc.returncode}): {stderr.decode('utf-8', 'ignore')[:500]}")
        return stdout.decode("utf-8", "ignore")

    @staticmethod
    def _parse_exa_search_text(raw: str) -> List[Dict[str, Any]]:
        """Exa mcporter 输出是 'Title:/URL:/Published:/...' 块的纯文本，按空行分块解析。"""
        results: List[Dict[str, Any]] = []
        blocks = re.split(r"\n\s*\n", raw.strip())
        for block in blocks:
            item: Dict[str, Any] = {}
            lines = block.splitlines()
            current_field = None
            for line in lines:
                m = re.match(r"^(Title|URL|Published|Author|Highlights|Content|Summary):\s*(.*)$", line)
                if m:
                    key = m.group(1).lower()
                    value = m.group(2).strip()
                    item[key] = value
                    current_field = key
                elif current_field and line.strip():
                    item[current_field] = (item.get(current_field, "") + "\n" + line.strip()).strip()
            if item.get("title") and item.get("url"):
                results.append({
                    "title": item.get("title", ""),
                    "url": item.get("url", ""),
                    "published": item.get("published"),
                    "author": item.get("author"),
                    "snippet": item.get("highlights") or item.get("content") or item.get("summary"),
                })
        return results

    @staticmethod
    def _clean_html(text: str) -> str:
        text = re.sub(r"<[^>]+>", "", text or "")
        text = re.sub(r"\s+", " ", text).strip()
        return text[:500]


agent_reach_client = AgentReachClient()
