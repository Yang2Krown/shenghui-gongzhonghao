"""极致了公众号历史/当天发文 adapter。

用于替换不稳定的搜狗微信搜索：固定公众号账号从 SourceAccount 读取，
日常用 post_condition 拉当天发文；历史补库通过任务显式调用 post_history。
"""

import asyncio
import logging
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional, Tuple

import httpx

from app.core.config import settings
from app.models.source_registry import SourceRegistry, SourceAccount, SOURCE_TYPE_DAJIALA_WECHAT
from app.services.scraping.adapters.exa_wechat_adapter import resolve_items_permalinks
from app.services.scraping.base import AdapterHealth, FetchedItem, SourceAdapter

logger = logging.getLogger(__name__)


API_BASE = "https://www.dajiala.com/fbmain/monitor/v3"


def _api_key() -> str:
    return (settings.DAJIALA_API_KEY or "").strip()


def _verifycode() -> str:
    return (settings.DAJIALA_VERIFYCODE or "").strip()


def _parse_time(value: Any, text: Any) -> Optional[datetime]:
    if value:
        try:
            return datetime.fromtimestamp(int(value))
        except Exception:
            pass
    if text:
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
            try:
                return datetime.strptime(str(text), fmt)
            except Exception:
                continue
    return None


def _account_payload(account: SourceAccount, page: Optional[int] = None) -> Dict[str, Any]:
    """构造极致了请求体。

    biz 是微信文章 __biz 值；SourceAccount.handle 通常是微信号，不一定是 __biz。
    只有明显像 __biz 的值才填 biz，其它都走 name，避免把 wxid/gh_id 误塞进 biz。
    """
    handle = (account.handle or "").strip()
    name = handle or (account.display_name or "").strip()
    payload: Dict[str, Any] = {
        "biz": "",
        "url": "",
        "name": name,
        "key": _api_key(),
        "verifycode": _verifycode(),
    }
    if handle and (handle.startswith(("Mj", "Mz")) or handle.endswith("==")):
        payload["biz"] = handle
        payload["name"] = ""
    if page is not None:
        payload["page"] = page
    return payload


def _article_to_item(
    raw: Dict[str, Any],
    account: SourceAccount,
    *,
    endpoint: str,
    page: Optional[int],
) -> Optional[FetchedItem]:
    title = str(raw.get("title") or "").strip()
    url = str(raw.get("url") or "").strip()
    if not title or not url:
        return None

    summary = str(raw.get("digest") or "").strip() or None
    cover_url = raw.get("cover_url") or raw.get("pic_cdn_url_1_1") or raw.get("pic_cdn_url_16_9")
    return FetchedItem(
        title=title,
        url=url,
        summary=summary,
        author=account.display_name,
        published_at=_parse_time(raw.get("post_time"), raw.get("post_time_str")),
        engagement={
            "send_to_fans_num": raw.get("send_to_fans_num") or 0,
            "position": raw.get("position"),
            "original": raw.get("original"),
        },
        extras={
            "provider": "dajiala",
            "endpoint": endpoint,
            "page": page,
            "source_account_name": account.display_name,
            "source_account_handle": account.handle,
            "appmsgid": raw.get("appmsgid"),
            "position": raw.get("position"),
            "cover_url": cover_url,
            "pre_post_time": raw.get("pre_post_time"),
            "update_time": raw.get("update_time"),
            "item_show_type": raw.get("item_show_type"),
            "msg_status": raw.get("msg_status"),
            "is_deleted": raw.get("is_deleted"),
            "types": raw.get("types"),
            "raw": raw,
        },
        source_account_id=account.id,
    )


class DajialaWechatAdapter(SourceAdapter):
    source_type = SOURCE_TYPE_DAJIALA_WECHAT
    TIMEOUT = 30

    async def health_check(self) -> AdapterHealth:
        if not _api_key():
            return AdapterHealth(ok=False, reason="DAJIALA_API_KEY 未配置")
        return AdapterHealth(ok=True)

    async def fetch(
        self,
        source: SourceRegistry,
        *,
        accounts: Optional[List[SourceAccount]] = None,
        since: Optional[datetime] = None,
    ) -> List[FetchedItem]:
        """日常增量：查询固定博主当天发文。"""
        if not _api_key():
            logger.error("[%s] DAJIALA_API_KEY 未配置，跳过公众号当天发文抓取", source.platform)
            return []

        cfg = source.fetch_config or {}
        account_list = self._select_accounts(accounts or [], cfg)
        if not account_list:
            logger.warning("[%s] 极致了公众号源没有可抓取账号", source.platform)
            return []

        items = await self._fetch_condition(source.platform, account_list, cfg)
        items = await resolve_items_permalinks(
            items,
            concurrency=int(cfg.get("resolve_concurrency", 3)),
            fetch_permanent_content=True,
            fetch_snapshot=False,
        )
        logger.info("[%s] 极致了当天发文抓回 %s 条（账号 %s 个）", source.platform, len(items), len(account_list))
        return items

    async def fetch_history(
        self,
        source: SourceRegistry,
        *,
        accounts: Optional[List[SourceAccount]] = None,
        max_pages_per_account: int = 1,
        account_ids: Optional[Iterable[int]] = None,
    ) -> List[FetchedItem]:
        """历史补库：显式调用 post_history，避免被日常调度误触发。"""
        if not _api_key():
            logger.error("[%s] DAJIALA_API_KEY 未配置，跳过公众号历史补库", source.platform)
            return []

        cfg = source.fetch_config or {}
        account_list = self._select_accounts(accounts or [], cfg, account_ids=account_ids)
        if not account_list:
            logger.warning("[%s] 极致了公众号历史补库没有可抓取账号", source.platform)
            return []

        pages = max(1, int(max_pages_per_account or 1))
        items = await self._fetch_history(source.platform, account_list, pages, cfg)
        items = await resolve_items_permalinks(
            items,
            concurrency=int(cfg.get("resolve_concurrency", 3)),
            fetch_permanent_content=True,
            fetch_snapshot=False,
        )
        logger.info(
            "[%s] 极致了历史补库抓回 %s 条（账号 %s 个，每号最多 %s 页）",
            source.platform, len(items), len(account_list), pages,
        )
        return items

    @staticmethod
    def _select_accounts(
        accounts: List[SourceAccount],
        cfg: Dict[str, Any],
        *,
        account_ids: Optional[Iterable[int]] = None,
    ) -> List[SourceAccount]:
        selected = [a for a in accounts if a.enabled and (a.handle or a.display_name)]
        if account_ids:
            wanted = {int(x) for x in account_ids}
            selected = [a for a in selected if a.id in wanted]
        limit = int(cfg.get("max_accounts", 0) or 0)
        return selected[:limit] if limit > 0 else selected

    async def _fetch_condition(
        self,
        platform: str,
        accounts: List[SourceAccount],
        cfg: Dict[str, Any],
    ) -> List[FetchedItem]:
        concurrency = max(1, int(cfg.get("concurrency", 2)))
        sem = asyncio.Semaphore(concurrency)
        async with httpx.AsyncClient(timeout=self.TIMEOUT) as client:
            async def _one(acc: SourceAccount) -> List[FetchedItem]:
                async with sem:
                    return await self._post_account(client, platform, "post_condition", acc, page=None)

            batches = await asyncio.gather(*[_one(acc) for acc in accounts], return_exceptions=True)
        return self._merge_batches(batches)

    async def _fetch_history(
        self,
        platform: str,
        accounts: List[SourceAccount],
        max_pages_per_account: int,
        cfg: Dict[str, Any],
    ) -> List[FetchedItem]:
        concurrency = max(1, int(cfg.get("history_concurrency", cfg.get("concurrency", 2))))
        sem = asyncio.Semaphore(concurrency)
        units: List[Tuple[SourceAccount, int]] = [
            (acc, page)
            for acc in accounts
            for page in range(1, max_pages_per_account + 1)
        ]
        async with httpx.AsyncClient(timeout=self.TIMEOUT) as client:
            async def _one(unit: Tuple[SourceAccount, int]) -> List[FetchedItem]:
                acc, page = unit
                async with sem:
                    return await self._post_account(client, platform, "post_history", acc, page=page)

            batches = await asyncio.gather(*[_one(unit) for unit in units], return_exceptions=True)
        return self._merge_batches(batches)

    async def _post_account(
        self,
        client: httpx.AsyncClient,
        platform: str,
        endpoint: str,
        account: SourceAccount,
        *,
        page: Optional[int],
    ) -> List[FetchedItem]:
        payload = _account_payload(account, page=page)
        try:
            resp = await client.post(
                f"{API_BASE}/{endpoint}",
                json=payload,
                headers={"Content-Type": "application/json"},
            )
            resp.raise_for_status()
            data = resp.json()
        except Exception as exc:
            logger.warning(
                "[%s] 极致了 %s 请求失败 account=%s page=%s: %s",
                platform, endpoint, account.display_name, page, exc,
            )
            return []

        if data.get("code") not in (0, "0"):
            logger.warning(
                "[%s] 极致了 %s 返回异常 account=%s page=%s code=%s msg=%s",
                platform, endpoint, account.display_name, page, data.get("code"), data.get("msg"),
            )
            return []

        mode = data.get("mode")
        if mode not in (None, 0, "0"):
            logger.warning(
                "[%s] 极致了 %s account=%s page=%s mode=%s msg=%s",
                platform, endpoint, account.display_name, page, mode, data.get("msg"),
            )

        rows = data.get("data") or []
        if not isinstance(rows, list):
            return []
        return [
            item
            for item in (_article_to_item(row, account, endpoint=endpoint, page=page) for row in rows if isinstance(row, dict))
            if item
        ]

    @staticmethod
    def _merge_batches(batches: List[Any]) -> List[FetchedItem]:
        items: List[FetchedItem] = []
        seen: set[str] = set()
        for batch in batches:
            if isinstance(batch, Exception):
                logger.warning("极致了子任务失败: %s", batch)
                continue
            for item in batch:
                key = item.url or item.dedup_hash()
                if key in seen:
                    continue
                seen.add(key)
                items.append(item)
        return items
