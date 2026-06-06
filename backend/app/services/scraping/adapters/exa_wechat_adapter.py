"""微信公众号关键词搜索流 adapter（P0 方案 A）。

策略：
1. 对每个 SourceAccount.display_name 跑 Exa 搜索（限 mp.weixin.qq.com 域）
2. 额外把 SourceRegistry.fetch_config.keywords 加进搜索词
3. 命中的文章如果标题/正文包含公众号名 → 关联 source_account_id

不订阅、不长期监听——只能搜"最近被收录的"文章。够 P0 用。
"""

import asyncio
import logging
import re
from datetime import datetime
from email.utils import parsedate_to_datetime
from typing import Any, List, Optional

import httpx

from app.models.source_registry import SourceRegistry, SourceAccount, SOURCE_TYPE_EXA_WECHAT
from app.services.scraping.agent_reach_runner import agent_reach_client
from app.services.scraping.base import FetchedItem, SourceAdapter

logger = logging.getLogger(__name__)


# ── 微信临时签名链接 → 永久链接 ───────────────────────────────
# 搜索引擎返回的链接形如 s?src=11&timestamp=...&signature=...，signature 会过期
# （约数小时~1 天），过期后点击显示"链接已过期"。必须在抓取时（签名还有效）
# 请求一次，从文章页提取永久标识后存库。
_WECHAT_PERMALINK_RE = re.compile(r"https?://mp\.weixin\.qq\.com/s/[A-Za-z0-9_\-]+")
_OG_URL_RE = re.compile(r'<meta\s+property="og:url"\s+content="([^"]+)"')
_BIZ_RE = re.compile(r'var\s+biz\s*=\s*"([^"]+)"')
_MID_RE = re.compile(r'var\s+mid\s*=\s*"([^"]+)"')
_IDX_RE = re.compile(r'var\s+idx\s*=\s*"([^"]+)"')
_SN_RE = re.compile(r'var\s+sn\s*=\s*"([^"]+)"')
# 用微信客户端 UA：普通浏览器 UA 常被微信拦成"请在客户端打开"页（提取不到永久链接），
# MicroMessenger UA 会让微信返回真正的文章页（含 og:url / biz·mid·idx·sn），解析成功率高很多。
_BROWSER_UA = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Mobile/15E148 MicroMessenger/8.0.5(0x18000528) "
    "NetType/WIFI Language/zh_CN"
)


def _is_permanent_wechat_url(url: str) -> bool:
    """永久链接：/s/<token> 形式，或 __biz&mid&sn 齐全的形式。"""
    if "mp.weixin.qq.com" not in url:
        return False
    if "/s/" in url:
        return True
    return "__biz=" in url and "mid=" in url and "sn=" in url


async def resolve_wechat_permalink(url: str, *, timeout: float = 10.0) -> str:
    """把临时签名链接解析成永久链接。永久链接 / 非微信链接原样返回。"""
    if "mp.weixin.qq.com" not in url or _is_permanent_wechat_url(url):
        return url
    try:
        async with httpx.AsyncClient(
            follow_redirects=True, timeout=timeout,
            headers={"User-Agent": _BROWSER_UA},
        ) as client:
            resp = await client.get(url)
        # 1) 跟随 302 后已经是永久链接
        if _is_permanent_wechat_url(str(resp.url)):
            return str(resp.url)
        body = resp.text
        if "已过期" in body:
            logger.warning(f"微信链接抓取时已过期，无法解析永久地址: {url[:80]}")
            return url
        # 2) og:url meta
        m = _OG_URL_RE.search(body)
        if m and _is_permanent_wechat_url(m.group(1)):
            return m.group(1)
        # 3) 正文里的 /s/<token>
        m = _WECHAT_PERMALINK_RE.search(body)
        if m:
            return m.group(0)
        # 4) 用 biz/mid/idx/sn 拼出永久链接
        biz, mid, idx, sn = (
            _BIZ_RE.search(body), _MID_RE.search(body),
            _IDX_RE.search(body), _SN_RE.search(body),
        )
        if biz and mid and idx and sn:
            return (
                f"https://mp.weixin.qq.com/s?__biz={biz.group(1)}"
                f"&mid={mid.group(1)}&idx={idx.group(1)}&sn={sn.group(1)}"
            )
        logger.warning(f"未能从微信文章页提取永久链接，保留原链接: {url[:80]}")
    except Exception as e:
        logger.warning(f"微信永久链接解析失败，保留原链接: {type(e).__name__}: {e}")
    return url


class ExaWechatAdapter(SourceAdapter):
    source_type = SOURCE_TYPE_EXA_WECHAT

    DEFAULT_LIMIT_PER_KEYWORD = 5
    DEFAULT_MAX_KEYWORDS = 20  # 避免一次跑爆 API

    async def fetch(
        self,
        source: SourceRegistry,
        *,
        accounts: Optional[List[SourceAccount]] = None,
        since: Optional[datetime] = None,
    ) -> List[FetchedItem]:
        cfg = source.fetch_config or {}
        per_keyword_limit = int(cfg.get("limit_per_keyword", self.DEFAULT_LIMIT_PER_KEYWORD))
        max_keywords = int(cfg.get("max_keywords", self.DEFAULT_MAX_KEYWORDS))

        # 构造搜索词：账号名 + fetch_config.keywords
        account_keywords = [a.display_name for a in (accounts or []) if a.display_name]
        extra_keywords = list(cfg.get("keywords", []) or [])
        # 去重 + 截顶
        all_keywords: List[str] = []
        seen_kw: set[str] = set()
        for kw in account_keywords + extra_keywords:
            kw = kw.strip()
            if kw and kw not in seen_kw:
                seen_kw.add(kw)
                all_keywords.append(kw)
        all_keywords = all_keywords[:max_keywords]

        if not all_keywords:
            logger.warning(f"[{source.platform}] 没有可用的搜索关键词，跳过")
            return []

        # 用 display_name → SourceAccount.id 索引，便于命中后回填
        account_index = {(a.display_name or "").strip(): a.id for a in (accounts or [])}

        # 并发搜索（注意：mcporter 是 subprocess，太多并发可能被限速）
        sem = asyncio.Semaphore(int(cfg.get("concurrency", 3)))

        async def _one(kw: str) -> List[FetchedItem]:
            async with sem:
                try:
                    results = await agent_reach_client.search_wechat(kw, num_results=per_keyword_limit)
                except Exception as e:
                    logger.warning(f"[{source.platform}] '{kw}' 搜索失败: {e}")
                    return []
                items: List[FetchedItem] = []
                for r in results:
                    url = (r.get("url") or "").strip()
                    if not url or "mp.weixin.qq.com" not in url:
                        continue
                    items.append(FetchedItem(
                        title=(r.get("title") or url).strip(),
                        url=url,
                        summary=r.get("snippet"),
                        author=r.get("author"),
                        published_at=_parse_dt(r.get("published")),
                        source_account_id=account_index.get(kw),
                        extras={"matched_keyword": kw},
                    ))
                return items

        batches = await asyncio.gather(*[_one(kw) for kw in all_keywords], return_exceptions=True)

        # 合并 + URL 去重
        seen_urls: set[str] = set()
        merged: List[FetchedItem] = []
        for batch in batches:
            if isinstance(batch, Exception):
                continue
            for item in batch:
                if item.url in seen_urls:
                    continue
                seen_urls.add(item.url)
                merged.append(item)

        # 把临时签名链接解析成永久链接（趁 signature 还有效），否则存库后约 1 天就过期
        resolve_sem = asyncio.Semaphore(int(cfg.get("resolve_concurrency", 5)))

        async def _resolve(item: FetchedItem) -> FetchedItem:
            async with resolve_sem:
                item.url = await resolve_wechat_permalink(item.url)
            return item

        resolved = await asyncio.gather(*[_resolve(it) for it in merged], return_exceptions=True)
        merged = [it for it in resolved if isinstance(it, FetchedItem)]

        permanent = sum(1 for it in merged if _is_permanent_wechat_url(it.url))
        logger.info(
            f"[{source.platform}] exa_wechat 抓到 {len(merged)} 条"
            f"（关键词 {len(all_keywords)} 个，永久链接 {permanent} 条）"
        )
        return merged


def _parse_dt(value: Any) -> Optional[datetime]:
    if not value:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo is None else value.replace(tzinfo=None)
    if isinstance(value, str):
        for parser in (
            lambda s: datetime.fromisoformat(s.replace("Z", "+00:00")),
            parsedate_to_datetime,
        ):
            try:
                dt = parser(value)
                return dt if dt.tzinfo is None else dt.replace(tzinfo=None)
            except Exception:
                continue
    return None
