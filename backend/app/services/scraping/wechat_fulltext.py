"""Shared WeChat article full-text extraction for background pipelines.

The creation tool already has a reliable direct extractor for permanent
mp.weixin.qq.com links.  Keep the background commercial pipeline on the same
implementation and validation rules so error messages are never persisted as
article content.
"""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlparse

from app.services.scraping.link_extractor import extract_link_content


MAX_WECHAT_CONTENT_CHARS = 12_000
_FAILURE_PREFIXES = (
    "请输入有效的",
    "请求失败",
    "提取失败",
    "文章已失效",
    "暂不支持",
)


@dataclass(frozen=True)
class ExtractedWechatArticle:
    title: str
    content: str
    author: str


def _is_wechat_url(url: str) -> bool:
    hostname = (urlparse(url or "").hostname or "").rstrip(".").lower()
    return hostname in {"mp.weixin.qq.com", "weixin.qq.com"}


async def extract_wechat_article(url: str) -> ExtractedWechatArticle | None:
    """Extract validated text from a permanent official WeChat article URL."""
    if not _is_wechat_url(url):
        return None

    result = await extract_link_content(url)
    if result.get("platform") != "gzh":
        return None

    content = str(result.get("content") or "").strip()
    if not content or content.startswith(_FAILURE_PREFIXES):
        return None

    return ExtractedWechatArticle(
        title=str(result.get("title") or "").strip(),
        content=content[:MAX_WECHAT_CONTENT_CHARS],
        author=str(result.get("author") or "").strip(),
    )
