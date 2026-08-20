"""X (Twitter) adapter —— 走 twitterapi.io HTTP API，国内服务器直连可用（无需代理/cookie）。

替代旧的 playwright_x_adapter：国内服务器访问不了 x.com，twitterapi.io 在墙外代抓、
转发普通 HTTPS 接口给我们，所以腾讯大陆机器能直接用。

两种模式（和 sogou_wechat 一样，靠"有没有配 keywords"区分，共用一个 adapter）：
- 账号订阅：源挂了 accounts、未配 keywords → 逐个博主调 /twitter/user/last_tweets
- 关键词搜索：fetch_config.keywords 非空 → 逐词调 /twitter/tweet/advanced_search

关键设计：推文正文(text)整条存进 RawInfo.content。服务器被墙，后续写公众号正文时
只能从库里读，不可能再回 x.com 取——所以采集时必须把原文落库。

API key：os.getenv("TWITTERAPI_IO_KEY")，值放 .env(本地) / .env.production(服务器)，
按用户要求不进 config.py。

SourceRegistry.fetch_config:
- keywords: List[str]         配了→关键词模式；不配→账号模式
- query_type: "Latest"|"Top" 关键词模式排序，默认 Latest
- limit: int                 每个账号/关键词最多取多少条（默认 20，=API 一页）
- include_replies: bool      账号模式是否带回复，默认 False
- concurrency: int           并发请求数，默认 3（别一次性把 58 个号炸出去）
- rotate_batch: int          每次只处理一小批（账号或关键词），按时间片轮转；防一次发太多
- rotate_period_sec: int     轮转周期，默认 1800
"""

import asyncio
import logging
import os
import random
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import httpx
from dotenv import load_dotenv

from app.models.source_registry import SourceRegistry, SourceAccount, SOURCE_TYPE_X
from app.services.scraping.base import AdapterHealth, FetchedItem, SourceAdapter

logger = logging.getLogger(__name__)

# 本地开发：把 backend/.env 读进 os.environ（生产由 docker-compose 注入，容器内无此 .env，no-op）。
# ponytail: 故意绕开 config.py —— key 只活在 .env / .env.production，不进代码仓库的 settings
load_dotenv(Path(__file__).resolve().parents[4] / ".env")

API_BASE = "https://api.twitterapi.io"


class TwitterApiCreditsExhausted(RuntimeError):
    """twitterapi.io 余额不足；同一轮后续请求应立即停止。"""


def _api_key() -> str:
    return (os.getenv("TWITTERAPI_IO_KEY") or "").strip()


def _parse_created_at(s: Optional[str]) -> Optional[datetime]:
    """twitterapi.io 的 createdAt 是 Twitter 经典格式：'Tue Jun 09 05:51:34 +0000 2026'。

    统一存 naive-UTC，和库里其它 published_at 一致（playwright_x 旧逻辑也是 strip tz）。
    """
    if not s:
        return None
    try:
        return datetime.strptime(s, "%a %b %d %H:%M:%S %z %Y").replace(tzinfo=None)
    except Exception:
        return None


def _tweet_to_item(
    tw: Dict[str, Any],
    account_id: Optional[int],
    discovered_from: str,
) -> Optional[FetchedItem]:
    """单条推文 JSON → FetchedItem（engagement 字段对齐旧 playwright_x，下游不用改）。"""
    text = (tw.get("text") or "").strip()
    url = tw.get("url") or tw.get("twitterUrl")
    if not text or not url:
        return None
    # 跳过纯转推（别人的内容，不算博主原创；引用推 quoted_tweet 保留，带博主评论）
    if tw.get("retweeted_tweet") and text.startswith("RT @"):
        return None

    author = tw.get("author") or {}
    handle = author.get("userName") or ""

    title = text.split("\n", 1)[0].strip()[:120]
    if len(text) > len(title):
        title = (title.rstrip() + "…")[:120]

    likes = tw.get("likeCount") or 0
    replies = tw.get("replyCount") or 0
    retweets = tw.get("retweetCount") or 0

    return FetchedItem(
        title=title or text[:120],
        url=url,
        summary=text[:500] or None,
        content=text,                       # 整条原文落库：服务器被墙，后面写正文只能读这里
        author=f"@{handle}" if handle else (author.get("name") or None),
        published_at=_parse_created_at(tw.get("createdAt")),
        engagement={
            "like": likes,
            "comments": replies,
            "retweet": retweets,
            "quote": tw.get("quoteCount") or 0,
            "views": tw.get("viewCount") or 0,
            "bookmark": tw.get("bookmarkCount") or 0,
            "interactive": likes + replies + retweets,
        },
        extras={
            "tweet_id": tw.get("id"),
            "x_handle": handle,
            "lang": tw.get("lang"),
            "conversation_id": tw.get("conversationId"),
            "is_reply": tw.get("isReply"),
            "has_article": bool(tw.get("article")),   # 长文推：text 可能不全，需要时再走 get_article
            "discovered_from": discovered_from,
        },
        source_account_id=account_id,
    )


class XTwitterApiAdapter(SourceAdapter):
    source_type = SOURCE_TYPE_X
    TIMEOUT = 25

    async def health_check(self) -> AdapterHealth:
        if not _api_key():
            return AdapterHealth(ok=False, reason="TWITTERAPI_IO_KEY 未配置")
        return AdapterHealth(ok=True)

    async def fetch(
        self,
        source: SourceRegistry,
        *,
        accounts: Optional[List[SourceAccount]] = None,
        since: Optional[datetime] = None,
    ) -> List[FetchedItem]:
        key = _api_key()
        if not key:
            logger.error(f"[{source.platform}] TWITTERAPI_IO_KEY 未配置，跳过 X 抓取")
            return []

        cfg = source.fetch_config or {}
        keywords = [k.strip() for k in (cfg.get("keywords") or []) if k and k.strip()]
        limit = int(cfg.get("limit", 20))
        # twitterapi.io 免费档 QPS = 1 请求 / 5 秒（全局按 key 限）。所以默认串行（并发 1）+
        # 每次请求前隔 min_interval_sec。升级套餐后可在 fetch_config 调高 concurrency / 调低间隔。
        # ponytail: 串行+定速，58 个号约 5 分钟跑完；若以后换高 QPS 套餐，这两个值改 fetch_config 即可
        concurrency = max(1, int(cfg.get("concurrency", 1)))
        interval = float(cfg.get("min_interval_sec", 5.5))

        # ("kw", 关键词, None) 或 ("acc", handle, account_id)
        units: List[Tuple[str, str, Optional[int]]]
        if keywords:
            units = [("kw", kw, None) for kw in keywords]
        else:
            units = [
                ("acc", (a.handle or "").lstrip("@"), a.id)
                for a in (accounts or [])
                if (a.handle or "").strip()
            ]
        units = self._rotate(units, cfg)
        if not units:
            logger.warning(f"[{source.platform}] X adapter 无可抓账号/关键词")
            return []

        sem = asyncio.Semaphore(concurrency)
        credits_exhausted = asyncio.Event()
        async with httpx.AsyncClient(timeout=self.TIMEOUT, headers={"x-api-key": key}) as client:
            async def _one(unit: Tuple[str, str, Optional[int]]) -> List[FetchedItem]:
                kind, value, acc_id = unit
                if credits_exhausted.is_set():
                    return []
                async with sem:
                    if credits_exhausted.is_set():
                        return []
                    # 定速：每次请求前隔 interval 秒（+小抖动），守住 1 req / 5s 的免费档限速
                    await asyncio.sleep(interval + random.random() * 0.5)
                    try:
                        if kind == "kw":
                            return await self._search(client, source.platform, value, limit, cfg)
                        return await self._user_tweets(client, source.platform, value, acc_id, limit, cfg)
                    except TwitterApiCreditsExhausted:
                        credits_exhausted.set()
                        raise

            batches = await asyncio.gather(*[_one(u) for u in units], return_exceptions=True)

        items: List[FetchedItem] = []
        seen: set[str] = set()
        billing_error: Optional[TwitterApiCreditsExhausted] = None
        for b in batches:
            if isinstance(b, TwitterApiCreditsExhausted):
                billing_error = b
                continue
            if isinstance(b, Exception):
                logger.warning(f"[{source.platform}] X 子任务失败: {b}")
                continue
            for it in b:
                if it.url not in seen:
                    seen.add(it.url)
                    items.append(it)

        if billing_error is not None:
            source.auth_status = "expired"
            logger.error("[%s] twitterapi.io 余额不足，已停止本轮剩余请求", source.platform)
            raise billing_error

        source.auth_status = "ok"

        logger.info(
            f"[{source.platform}] X(twitterapi) 抓回 {len(items)} 条"
            f"（{'关键词' if keywords else '账号'}模式，单元 {len(units)} 个）"
        )
        return items

    @staticmethod
    def _rotate(
        units: List[Tuple[str, str, Optional[int]]],
        cfg: Dict[str, Any],
    ) -> List[Tuple[str, str, Optional[int]]]:
        """按时间片轮转取一小批（同 sogou）：无状态，跨界环形绕回。"""
        rb = int(cfg.get("rotate_batch", 0) or 0)
        if rb > 0 and len(units) > rb:
            period = int(cfg.get("rotate_period_sec", 1800))
            start = (int(time.time() // period) * rb) % len(units)
            return (units + units)[start:start + rb]
        return units

    async def _user_tweets(
        self, client: httpx.AsyncClient, platform: str,
        handle: str, account_id: Optional[int], limit: int, cfg: Dict[str, Any],
    ) -> List[FetchedItem]:
        params = {
            "userName": handle,
            "includeReplies": str(bool(cfg.get("include_replies", False))).lower(),
        }
        data = await self._get(client, "/twitter/user/last_tweets", params, platform, handle)
        tweets = (((data or {}).get("data") or {}).get("tweets")) or []
        out = []
        for tw in tweets[:limit]:
            it = _tweet_to_item(tw, account_id, f"user:{handle}")
            if it:
                out.append(it)
        return out

    async def _search(
        self, client: httpx.AsyncClient, platform: str,
        query: str, limit: int, cfg: Dict[str, Any],
    ) -> List[FetchedItem]:
        params = {"query": query, "queryType": cfg.get("query_type", "Latest")}
        data = await self._get(client, "/twitter/tweet/advanced_search", params, platform, query)
        tweets = ((data or {}).get("tweets")) or []
        skip_replies = bool(cfg.get("skip_replies", True))
        out = []
        for tw in tweets[:limit]:
            # 关键词搜索的 Latest 流里夹大量回复（"@somebody ..."），多是噪音、低互动，
            # 提前滤掉省下游 embedding/预处理开销。账号模式不滤（已由 include_replies 控制）。
            # ponytail: 只按 isReply 标志滤，够用；要更细的质量门槛再上 ranking
            if skip_replies and tw.get("isReply"):
                continue
            it = _tweet_to_item(tw, None, f"search:{query}")
            if it:
                out.append(it)
        return out

    async def _get(
        self, client: httpx.AsyncClient, path: str,
        params: Dict[str, Any], platform: str, label: str,
    ) -> Optional[Dict[str, Any]]:
        """单次请求，普通失败返回 None，余额不足则终止整批。

        429（限速）等 6 秒重试一次；仍失败则放弃这个单元。
        """
        for attempt in (1, 2):
            try:
                resp = await client.get(API_BASE + path, params=params)
                if resp.status_code == 429 and attempt == 1:
                    logger.info(f"[{platform}] {path} {label!r} 429 限速，6s 后重试")
                    await asyncio.sleep(6)
                    continue
                if resp.status_code == 402:
                    body = resp.text[:300]
                    raise TwitterApiCreditsExhausted(
                        f"twitterapi.io 余额不足（HTTP 402）: {body}"
                    )
                if resp.status_code != 200:
                    logger.warning(f"[{platform}] {path} {label!r} HTTP {resp.status_code}: {resp.text[:200]}")
                    return None
                return resp.json()
            except TwitterApiCreditsExhausted:
                raise
            except Exception as e:
                logger.warning(f"[{platform}] {path} {label!r} 异常: {type(e).__name__}: {e}")
                return None
        return None


def _selftest() -> None:
    """无网络自测：解析逻辑跑通就行。"""
    sample = {
        "id": "123", "url": "https://x.com/AmandaAskell/status/123",
        "text": "Line one of the tweet\nsecond line with more detail",
        "createdAt": "Tue Jun 09 05:51:34 +0000 2026",
        "likeCount": 1297, "replyCount": 135, "retweetCount": 44,
        "quoteCount": 25, "viewCount": 96799, "bookmarkCount": 126,
        "lang": "en", "conversationId": "123", "isReply": False,
        "author": {"userName": "AmandaAskell", "name": "Amanda Askell"},
    }
    it = _tweet_to_item(sample, account_id=7, discovered_from="user:AmandaAskell")
    assert it is not None
    assert it.title == "Line one of the tweet…"         # 首行做标题，有后续内容补省略号
    assert it.content == sample["text"]                  # 整条原文进 content
    assert it.author == "@AmandaAskell"
    assert it.source_account_id == 7
    assert it.engagement["like"] == 1297
    assert it.engagement["interactive"] == 1297 + 135 + 44
    assert it.published_at == datetime(2026, 6, 9, 5, 51, 34)  # naive-UTC
    assert it.extras["x_handle"] == "AmandaAskell"

    # 纯转推应被丢弃
    rt = {"text": "RT @someone: not mine", "url": "https://x.com/x/status/9",
          "retweeted_tweet": {"id": "9"}, "author": {"userName": "x"}}
    assert _tweet_to_item(rt, None, "user:x") is None

    # 坏时间不炸
    assert _parse_created_at("garbage") is None
    assert _parse_created_at(None) is None

    # 轮转：8 取 3，跨界绕回
    units = [("kw", str(i), None) for i in range(8)]
    got = XTwitterApiAdapter._rotate(units, {"rotate_batch": 3, "rotate_period_sec": 1})
    assert len(got) == 3
    print("x_twitterapi_adapter selftest OK")


if __name__ == "__main__":
    _selftest()
