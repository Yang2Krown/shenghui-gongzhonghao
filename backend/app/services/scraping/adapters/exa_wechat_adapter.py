"""微信公众号关键词搜索流 adapter（P0 方案 A）。

策略：
1. 对每个 SourceAccount.display_name 跑 Exa 搜索（限 mp.weixin.qq.com 域）
2. 额外把 SourceRegistry.fetch_config.keywords 加进搜索词
3. 命中的文章如果标题/正文包含公众号名 → 关联 source_account_id

不订阅、不长期监听——只能搜"最近被收录的"文章。够 P0 用。
"""

import asyncio
import logging
from datetime import datetime
from email.utils import parsedate_to_datetime
from typing import Any, List, Optional

from app.models.source_registry import SourceRegistry, SourceAccount, SOURCE_TYPE_EXA_WECHAT
from app.services.scraping.agent_reach_runner import agent_reach_client
from app.services.scraping.base import FetchedItem, SourceAdapter

logger = logging.getLogger(__name__)


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

        logger.info(f"[{source.platform}] exa_wechat 抓到 {len(merged)} 条（关键词 {len(all_keywords)} 个）")
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
