"""Jina Reader：抓任意网页/教程全文，返回干净文本。

r.jina.ai/<url> 免费可用；配了 JINA_API_KEY 限额更高、更稳。
用于实操类研究：把教程页全文抓回来，供 deepseek 提炼操作步骤。
"""

import asyncio
import logging
from typing import List

import httpx

from app.core.config import settings
from app.core.url_security import validate_public_http_url

logger = logging.getLogger(__name__)


async def jina_read(url: str, max_chars: int = 3000, timeout: int = 25) -> str:
    """抓单个 url 的正文，截断到 max_chars。失败返回空串（绝不抛）。"""
    if not url:
        return ""
    headers = {"X-Return-Format": "text"}
    if settings.JINA_API_KEY:
        headers["Authorization"] = f"Bearer {settings.JINA_API_KEY}"
    try:
        safe_url = validate_public_http_url(url)
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=False) as c:
            r = await c.get(f"https://r.jina.ai/{safe_url}", headers=headers)
            r.raise_for_status()
            return r.text[:max_chars]
    except Exception as e:
        logger.info(f"[Jina] 抓取失败 {url}: {type(e).__name__}: {e}")
        return ""


async def jina_read_many(urls: List[str], max_chars: int = 3000, concurrency: int = 3) -> dict:
    """并发抓多个 url，返回 {url: 正文}（抓失败的不收录）。"""
    sem = asyncio.Semaphore(concurrency)

    async def _one(u: str):
        async with sem:
            return u, await jina_read(u, max_chars)

    pairs = await asyncio.gather(*[_one(u) for u in urls])
    return {u: t for u, t in pairs if t}
