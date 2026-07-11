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
import time
from datetime import datetime
from email.utils import parsedate_to_datetime
from typing import Any, List, Optional

import httpx

from app.core.config import settings
from app.models.source_registry import SourceRegistry, SourceAccount, SOURCE_TYPE_EXA_WECHAT
from app.services.scraping.agent_reach_runner import agent_reach_client
from app.services.scraping.base import FetchedItem, SourceAdapter

logger = logging.getLogger(__name__)


# ── 微信临时签名链接 → 永久链接 ───────────────────────────────
DAJIALA_SOUGOU_LINK_API = "https://www.dajiala.com/fbmain/monitor/v3/sougou_link"
_DAJIALA_QPS_LOCK = asyncio.Lock()
_dajiala_last_request_at = 0.0


def _is_permanent_wechat_url(url: str) -> bool:
    """永久链接：/s/<token> 形式，或 __biz&mid&sn 齐全的形式。"""
    if "mp.weixin.qq.com" not in url:
        return False
    if "/s/" in url:
        return True
    return "__biz=" in url and "mid=" in url and "sn=" in url


def _is_temporary_wechat_url(url: str) -> bool:
    """识别需要转链的公众号地址：微信签名链或搜狗中转链。"""
    normalized = (url or "").strip().lower()
    return (
        ("mp.weixin.qq.com" in normalized and not _is_permanent_wechat_url(normalized))
        or "weixin.sogou.com/link" in normalized
    )


async def _wait_dajiala_qps() -> None:
    """极致了转链接口限制 1 QPS；同一 worker 内串行节流。"""
    global _dajiala_last_request_at
    async with _DAJIALA_QPS_LOCK:
        delay = 1.0 - (time.monotonic() - _dajiala_last_request_at)
        if delay > 0:
            await asyncio.sleep(delay)
        _dajiala_last_request_at = time.monotonic()


async def _convert_temporary_wechat_url(url: str, *, timeout: float) -> str:
    """调用极致了把临时公众号链接转换为永久链接；失败时保留原链。"""
    key = (settings.DAJIALA_API_KEY or "").strip()
    if not key:
        logger.error("DAJIALA_API_KEY 未配置，临时公众号链接无法转换: %s", url[:100])
        return url

    payload = {"url": url, "key": key}
    verifycode = (settings.DAJIALA_VERIFYCODE or "").strip()
    # 接口文档虽然说明附加码可选，但服务端实际要求字段始终存在；
    # 未设置附加码时也必须传空字符串，否则返回 code=20002。
    payload["verifycode"] = verifycode

    for attempt in range(1, 4):
        await _wait_dajiala_qps()
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.post(DAJIALA_SOUGOU_LINK_API, json=payload)
                response.raise_for_status()
                result = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            if attempt < 3:
                logger.warning("极致了转链请求失败，第 %s/3 次重试: %s", attempt, type(exc).__name__)
                await asyncio.sleep(attempt)
                continue
            logger.warning("极致了转链请求失败，保留原链: %s", url[:100])
            return url

        code = result.get("code")
        if code == 0:
            permanent_link = (result.get("data") or {}).get("permanent_link")
            if permanent_link and _is_permanent_wechat_url(permanent_link):
                return permanent_link.strip()
            logger.warning("极致了转链返回成功但永久链接无效，保留原链: %s", url[:100])
            return url
        if code == -1 and attempt < 3:
            logger.warning("极致了转链触发 QPS 限制，5 秒后重试")
            await asyncio.sleep(5)
            continue
        if code == 106 and attempt < 3:
            logger.warning("极致了转链读取数据过快，2 秒后重试")
            await asyncio.sleep(2)
            continue
        logger.warning("极致了转链失败 code=%s msg=%s，保留原链", code, result.get("msg"))
        return url
    return url


async def resolve_wechat_permalink(
    url: str,
    *,
    timeout: float = 10.0,
) -> tuple[str, Optional[str], Optional[str]]:
    """用极致了把公众号临时链转换为永久链；不再抓取或保存 HTML 快照。

    为兼容既有调用保留三元组返回值，后两个值始终为 ``None``。
    """
    if not _is_temporary_wechat_url(url):
        return url, None, None
    return await _convert_temporary_wechat_url(url, timeout=timeout), None, None


async def resolve_items_permalinks(
    items: List[FetchedItem],
    *,
    concurrency: int = 5,
) -> List[FetchedItem]:
    """批量转换公众号临时链接；转换失败的条目不进入后续入库。"""
    sem = asyncio.Semaphore(concurrency)

    async def _one(it: FetchedItem) -> FetchedItem:
        async with sem:
            it.url, _, _ = await resolve_wechat_permalink(
                it.url,
            )
        return it

    resolved = await asyncio.gather(*[_one(it) for it in items], return_exceptions=True)
    # 硬性保证：转换失败仍是临时链时直接丢弃，禁止临时链进入 RawInfo。
    return [
        it for it in resolved
        if isinstance(it, FetchedItem) and not _is_temporary_wechat_url(it.url)
    ]


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
        merged = await resolve_items_permalinks(
            merged, concurrency=int(cfg.get("resolve_concurrency", 5))
        )

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
