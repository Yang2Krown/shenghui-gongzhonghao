"""小红书关键词双源采集、硬过滤与素材入库。"""
from __future__ import annotations

import asyncio
import json
import logging
import math
import os
import random
import re
import shutil
import sys
import tempfile
import time
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlencode, urlparse

import httpx
import redis.asyncio as aioredis
from sqlalchemy import and_, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.timezone import utcnow
from app.models.raw_info import RawInfo
from app.models.source_registry import FETCH_STRATEGY_CRON, SourceRegistry
from app.models.xhs import (
    XhsDailyQuota, XhsEngagementSnapshot, XhsKeyword, XhsKeywordRun, XhsNote,
    XhsNoteDiscovery, XhsProviderCall,
)
from app.services.scraping.link_extractor import extract_xhs

logger = logging.getLogger(__name__)
PUBLIC_STATUSES = {"ready", "ready_degraded", "synced"}
PAID_PROVIDER = "tikhub"
FREE_PROVIDER = "cli"
DAILY_MIN_LIKES_EXCLUSIVE = 200
WEEKLY_MIN_LIKES_EXCLUSIVE = 2000


def collection_level(published_at: datetime | None, now: datetime) -> str | None:
    if published_at is None or published_at < now - timedelta(days=7):
        return None
    return "daily" if published_at >= now - timedelta(hours=24) else "weekly"


def minimum_likes_exclusive(published_at: datetime | None, now: datetime) -> int:
    return DAILY_MIN_LIKES_EXCLUSIVE if collection_level(published_at, now) == "daily" else WEEKLY_MIN_LIKES_EXCLUSIVE


def qualifies_by_time_and_likes(published_at: datetime | None, like_count: int | None, now: datetime) -> bool:
    level = collection_level(published_at, now)
    return level is not None and like_count is not None and like_count > minimum_likes_exclusive(published_at, now)


def eligibility_clause(now: datetime):
    """SQL equivalent of the two mutually exclusive collection levels."""
    day_cutoff = now - timedelta(hours=24)
    week_cutoff = now - timedelta(days=7)
    return or_(
        and_(XhsNote.published_at >= day_cutoff, XhsNote.like_count > DAILY_MIN_LIKES_EXCLUSIVE),
        and_(XhsNote.published_at >= week_cutoff, XhsNote.published_at < day_cutoff, XhsNote.like_count > WEEKLY_MIN_LIKES_EXCLUSIVE),
    )
CLI_AUTH_INVALID_KEY = "xhs:cli:auth_invalid"
CLI_COOLDOWN_KEY = "xhs:cli:cooldown"


class TikHubBudgetExhausted(RuntimeError): pass
class CliCoolingDown(RuntimeError): pass
class CliAuthenticationExpired(CliCoolingDown): pass


def normalize_keyword(value: str) -> str:
    return " ".join((value or "").strip().lower().split())


def count_value(value: Any) -> int | None:
    if value is None or value == "": return None
    if isinstance(value, bool): return int(value)
    if isinstance(value, (int, float)): return int(value)
    text = str(value).strip().lower().replace(",", "").replace("+", "")
    try:
        if text.endswith("万") or text.endswith("w"): return int(float(text[:-1]) * 10000)
        if text.endswith("k"): return int(float(text[:-1]) * 1000)
        return int(float(text))
    except (TypeError, ValueError): return None


def dt_value(value: Any) -> datetime | None:
    if value is None or value == "": return None
    if isinstance(value, datetime): return value.replace(tzinfo=None)
    if isinstance(value, (int, float)):
        stamp = value / 1000 if value > 10_000_000_000 else value
        try: return datetime.fromtimestamp(stamp)
        except (ValueError, OSError): return None
    text = str(value).strip().replace("Z", "+00:00")
    try: return datetime.fromisoformat(text).replace(tzinfo=None)
    except ValueError: return None


def first(data: dict, *paths: str):
    for path in paths:
        cur: Any = data
        for part in path.split("."):
            if isinstance(cur, dict):
                cur = cur.get(part)
            elif isinstance(cur, list) and part.isdigit():
                index = int(part)
                cur = cur[index] if index < len(cur) else None
            else:
                cur = None; break
        if cur is not None and cur != "": return cur
    return None


def remote_image_url(value: Any) -> str | None:
    if not value: return None
    url=str(value).strip()
    if url.startswith("http://") and ".xhscdn.com/" in url:
        return "https://"+url[len("http://"):]
    return url


def xsec_note_url(
    note_id: str,
    url: Any = None,
    token: Any = None,
    source: Any = None,
) -> str:
    """生成可从搜索结果直达的笔记链接。

    xiaohongshu-cli 的搜索卡片可能同时返回裸 URL 和单独的
    xsec_token。裸 /explore/{note_id} 在未登录浏览器中常会被小红书转到
    300031 验证页，因此不能因为已有 url 字段就丢掉 token。
    """
    raw_url = str(url or "").strip()
    query = parse_qs(urlparse(raw_url).query) if raw_url else {}
    xsec_token = str(token or (query.get("xsec_token") or [""])[0]).strip()
    xsec_source = str(source or (query.get("xsec_source") or [""])[0] or "pc_search").strip()
    stable_url = f"https://www.xiaohongshu.com/explore/{note_id}"
    if not xsec_token:
        return raw_url or stable_url
    return stable_url + "?" + urlencode({"xsec_token": xsec_token, "xsec_source": xsec_source})


def search_publish_time(payload: dict, now: datetime | None = None) -> datetime | None:
    """解析 CLI 搜索卡片中的相对日期或 MM-DD；详情时间仍优先使用精确时间戳。"""
    now=now or utcnow()
    tags=first(payload,"corner_tag_info","note_card.corner_tag_info") or []
    text=next((str(x.get("text") or "").strip() for x in tags if isinstance(x,dict) and x.get("type")=="publish_time"),"")
    if not text:return None
    if text in {"刚刚","今天"} or "分钟前" in text or "小时前" in text:return now
    if text.startswith("昨天"):return now-timedelta(days=1)
    days=re.search(r"(\d+)\s*天前",text)
    if days:return now-timedelta(days=int(days.group(1)))
    full=re.search(r"(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})",text)
    short=re.search(r"(?<!\d)(\d{1,2})[-/.](\d{1,2})(?!\d)",text)
    try:
        if full:return datetime(int(full.group(1)),int(full.group(2)),int(full.group(3)))
        if short:
            value=datetime(now.year,int(short.group(1)),int(short.group(2)))
            return value.replace(year=now.year-1) if value>now+timedelta(days=1) else value
    except ValueError:return None
    return None


@dataclass
class Candidate:
    note_id: str
    title: str = ""
    content: str = ""
    published_at: datetime | None = None
    note_type: str | None = None
    author_id: str | None = None
    author_nickname: str = ""
    author_bio: str = ""
    avatar_url: str | None = None
    cover_url: str | None = None
    like_count: int | None = None
    collect_count: int | None = None
    comment_count: int | None = None
    share_count: int | None = None
    view_count: int | None = None
    tags: list[str] = field(default_factory=list)
    xsec_url: str | None = None
    ranks: dict[str, int] = field(default_factory=dict)
    payloads: dict[str, Any] = field(default_factory=dict)
    score: float = 0
    title_generated: bool = False

    def merge(self, other: "Candidate") -> None:
        for name in ("title","content","published_at","note_type","author_id","author_nickname","author_bio","avatar_url","cover_url","like_count","collect_count","comment_count","share_count","view_count"):
            if getattr(self, name) in (None, "", []): setattr(self, name, getattr(other, name))
        # 后续来源/详情补全到 token 时，允许它替换先到的裸链接。
        if not _xsec_token(self.xsec_url) and _xsec_token(other.xsec_url):
            self.xsec_url = other.xsec_url
        elif not self.xsec_url:
            self.xsec_url = other.xsec_url
        self.tags = list(dict.fromkeys(self.tags + other.tags))
        self.ranks.update(other.ranks); self.payloads.update(other.payloads)
        self.title_generated = self.title_generated or other.title_generated


def normalize_candidate(raw: dict, provider: str, rank: int) -> Candidate | None:
    model_type=str(raw.get("model_type") or "").strip().lower()
    if model_type and model_type != "note":return None
    envelope = raw.get("note") if isinstance(raw.get("note"), dict) else _find_note_mapping(raw) or raw
    note_id = first(envelope, "note_id", "id", "noteId", "note_card.note_id", "note_card.id")
    if not note_id: return None
    user = first(envelope, "user", "author", "note_card.user") or {}
    interact = first(envelope, "interact_info", "interactInfo", "note_card.interact_info") or {}
    cover = remote_image_url(first(envelope, "cover.url_default", "cover.url", "cover_url", "image_list.0.url_default", "note_card.cover.url_default"))
    note_type = str(first(envelope, "type", "note_type", "note_card.type") or "").lower()
    note_type = "video" if "video" in note_type else "image" if note_type else None
    raw_url = first(envelope, "url", "share_url", "note_url") or first(raw, "url", "share_url", "note_url")
    token = first(envelope, "xsec_token", "xsecToken") or first(raw, "xsec_token", "xsecToken", "note_card.xsec_token", "note_card.xsecToken")
    source = first(envelope, "xsec_source", "xsecSource") or first(raw, "xsec_source", "xsecSource", "note_card.xsec_source", "note_card.xsecSource")
    url = xsec_note_url(str(note_id), raw_url, token, source)
    def metric(*paths: str, fallback: tuple[str, ...]) -> int | None:
        value=first(interact,*paths)
        if value is None:value=first(envelope,*fallback)
        return count_value(value)
    return Candidate(
        note_id=str(note_id), title=str(first(envelope,"title","display_title","note_card.display_title") or ""),
        content=str(first(envelope,"desc","content","note_card.desc") or ""),
        published_at=dt_value(first(envelope,"published_at","time","publish_time","note_card.time")) or search_publish_time(raw), note_type=note_type,
        author_id=str(first(user,"user_id","id","userid") or "") or None,
        author_nickname=str(first(user,"nickname","nick_name","name") or ""), author_bio=str(first(user,"desc","bio") or ""),
        avatar_url=remote_image_url(first(user,"avatar","image")), cover_url=cover,
        like_count=metric("liked_count","like_count","likedCount",fallback=("like_count","likes")),
        collect_count=metric("collected_count","collect_count","collectedCount",fallback=("collect_count","collects")),
        comment_count=metric("comment_count","commentCount",fallback=("comment_count","comments")),
        share_count=metric("share_count","shared_count","shareCount",fallback=("share_count","shared_count","shares")),
        view_count=metric("view_count","viewCount",fallback=("view_count","views")),
        tags=[str(x.get("name") if isinstance(x,dict) else x) for x in (first(envelope,"tag_list","tags") or []) if x],
        xsec_url=str(url), ranks={provider: rank}, payloads={provider: raw},
    )


def unwrap_items(payload: Any) -> list[dict]:
    if isinstance(payload, list): return [x for x in payload if isinstance(x, dict)]
    if not isinstance(payload, dict): return []
    data = payload.get("data", payload)
    if isinstance(data, list): return [x for x in data if isinstance(x, dict)]
    for key in ("items","notes","feeds","note_list","list"):
        value = data.get(key) if isinstance(data, dict) else None
        if isinstance(value, list): return [x for x in value if isinstance(x, dict)]
    nested=data.get("data") if isinstance(data,dict) else None
    if isinstance(nested,(dict,list)):return unwrap_items(nested)
    return []


def _find_note_mapping(payload: Any, depth: int = 0) -> dict | None:
    if depth>5:return None
    if isinstance(payload,dict):
        if first(payload,"note_id","noteId") or (payload.get("id") and any(k in payload for k in ("title","display_title","desc","interact_info"))):return payload
        for key in ("note","note_card","note_info","data","item","items","feeds"):
            found=_find_note_mapping(payload.get(key),depth+1)
            if found:return found
    elif isinstance(payload,list):
        for item in payload:
            found=_find_note_mapping(item,depth+1)
            if found:return found
    return None


def merge_provider_candidates(batches: dict[str, list[dict]]) -> dict[str, Candidate]:
    """每个同级来源先各取 20，再按稳定 note_id 合并。"""
    merged: dict[str, Candidate] = {}
    for provider, items in batches.items():
        for idx, raw in enumerate(items[:settings.XHS_PROVIDER_CANDIDATE_LIMIT], 1):
            candidate = normalize_candidate(raw, provider, idx)
            if not candidate:
                continue
            if candidate.note_id in merged:
                merged[candidate.note_id].merge(candidate)
            else:
                merged[candidate.note_id] = candidate
    return merged


def reserve_tikhub_searches(db: Session, count: int, day: date | None = None) -> XhsDailyQuota:
    day = day or utcnow().date()
    quota = db.execute(select(XhsDailyQuota).where(XhsDailyQuota.quota_date == day).with_for_update()).scalar_one_or_none()
    if not quota:
        quota = XhsDailyQuota(quota_date=day, limit_count=settings.TIKHUB_DAILY_LIMIT, used_count=0, reserved_search_count=0)
        db.add(quota); db.flush()
    quota.reserved_search_count = min(max(quota.limit_count - quota.used_count, 0), max(count, 0))
    db.commit(); return quota


def consume_tikhub_quota(db: Session, *, operation: str) -> XhsDailyQuota:
    day = utcnow().date()
    quota = db.execute(select(XhsDailyQuota).where(XhsDailyQuota.quota_date == day).with_for_update()).scalar_one_or_none()
    if not quota:
        quota = XhsDailyQuota(quota_date=day, limit_count=settings.TIKHUB_DAILY_LIMIT, used_count=0, reserved_search_count=0)
        db.add(quota); db.flush()
    available = quota.limit_count - quota.used_count
    if available <= 0 or (operation != "search" and available <= quota.reserved_search_count):
        db.rollback(); raise TikHubBudgetExhausted("TikHub 今日 100 次共享额度已用尽或已为搜索预留")
    quota.used_count += 1
    if operation == "search" and quota.reserved_search_count > 0: quota.reserved_search_count -= 1
    db.commit(); return quota


def log_call(db: Session, provider: str, operation: str, status: str, *, run_id: int | None = None, note_id: str | None = None, started: float | None = None, error: Exception | None = None, request_count: int = 1) -> None:
    estimated_cost=settings.TIKHUB_UNIT_PRICE_CNY*request_count if provider==PAID_PROVIDER and status=="success" else 0
    db.add(XhsProviderCall(provider=provider, operation=operation, run_id=run_id, note_identity=note_id, status=status, is_paid=provider==PAID_PROVIDER, request_count=request_count, latency_ms=int((time.monotonic()-started)*1000) if started else None, estimated_cost=estimated_cost, error_code=type(error).__name__ if error else None, error_message=str(error)[:1000] if error else None, metadata_json={"cookie_logged": False}))
    db.commit()


class TikHubProvider:
    async def _call(self, path: str, params: dict) -> dict:
        if not settings.TIKHUB_TOKEN: raise RuntimeError("TIKHUB_TOKEN 未配置")
        headers = {"Authorization": f"Bearer {settings.TIKHUB_TOKEN}"}
        redis=aioredis.from_url(settings.CELERY_BROKER_URL,decode_responses=True)
        acquired=None;deadline=time.monotonic()+30
        try:
            while time.monotonic()<deadline and acquired is None:
                for slot in range(2):
                    lock=redis.lock(f"xhs:tikhub:slot:{slot}",timeout=45,blocking=False)
                    if await lock.acquire(blocking=False):acquired=lock;break
                if acquired is None:await asyncio.sleep(.25)
            if acquired is None:raise RuntimeError("TikHub 全局并发 2 等待超时")
            async with httpx.AsyncClient(base_url=settings.TIKHUB_API_BASE, timeout=30) as client:
                response = await client.get(path, params=params, headers=headers)
                response.raise_for_status(); return response.json()
        finally:
            try:
                if acquired and await acquired.owned():await acquired.release()
            finally:await redis.aclose()

    async def search(self, keyword: str) -> list[dict]:
        payload = await self._call(settings.TIKHUB_XHS_SEARCH_PATH, {"keyword": keyword, "sort_type": "general", "note_type": "不限", "time_filter": "一周内", "page": 1, "source": "explore_feed", "ai_mode": 0})
        return unwrap_items(payload)[:settings.XHS_PROVIDER_CANDIDATE_LIMIT]

    async def detail(self, candidate: Candidate) -> dict:
        return await self._call(settings.TIKHUB_XHS_DETAIL_PATH, {"note_id": candidate.note_id, "xsec_token": _xsec_token(candidate.xsec_url)})


def _xsec_token(url: str | None) -> str:
    if not url:return ""
    return (parse_qs(urlparse(url).query).get("xsec_token") or [""])[0]


class CliProvider:
    @staticmethod
    def _error_message(out: bytes, err: bytes) -> str:
        """Extract the CLI's structured error, which is usually written to stdout."""
        stdout = out.decode("utf-8", "replace").strip()
        stderr = err.decode("utf-8", "replace").strip()
        if stdout:
            try:
                payload = json.loads(stdout)
                error = payload.get("error") if isinstance(payload, dict) else None
                if isinstance(error, dict):
                    code = str(error.get("code") or "").strip()
                    message = str(error.get("message") or "").strip()
                    if code and message:
                        return f"{code}: {message}"[-1000:]
                    if message or code:
                        return (message or code)[-1000:]
                if error:
                    return str(error)[-1000:]
            except json.JSONDecodeError:
                pass
        return (stderr or stdout or "xiaohongshu-cli 执行失败（未返回错误详情）")[-1000:]

    @staticmethod
    def _is_auth_expired(message: str) -> bool:
        lowered = message.lower()
        return any(x in lowered for x in (
            "session expired", "cookie expired", "not_authenticated",
            "not authenticated", "re-login",
        ))

    @staticmethod
    def _is_risk_error(message: str) -> bool:
        lowered = message.lower()
        return any(x in lowered for x in (
            "captcha", "verify", "461", "471",
        ))

    async def _raise_cli_error(self, message: str) -> None:
        redis = aioredis.from_url(settings.CELERY_BROKER_URL, decode_responses=True)
        try:
            if self._is_auth_expired(message):
                # 登录失效不是短暂冷却：持久阻断到管理员重新扫码。
                await redis.set(CLI_AUTH_INVALID_KEY, message[:500])
                raise CliAuthenticationExpired(message)
            if self._is_risk_error(message):
                await redis.set(CLI_COOLDOWN_KEY, "1", ex=settings.XHS_CLI_COOLDOWN_MINUTES * 60)
                raise CliCoolingDown(message)
        finally:
            await redis.aclose()
        raise RuntimeError(message)

    def _env(self, temp_home: str) -> dict:
        cookie = Path(settings.XHS_CLI_COOKIE_FILE)
        if not cookie.is_file(): raise RuntimeError("xiaohongshu-cli Cookie 私密文件未配置")
        config = Path(temp_home) / ".xiaohongshu-cli"; config.mkdir(parents=True)
        os.symlink(cookie, config / "cookies.json")
        env = os.environ.copy(); env.update({"HOME": temp_home, "OUTPUT": "json"}); return env

    async def _run(self, *args: str) -> dict:
        if not shutil.which(settings.XHS_CLI_BIN): raise RuntimeError(f"{settings.XHS_CLI_BIN} 未安装")
        redis=aioredis.from_url(settings.CELERY_BROKER_URL,decode_responses=True)
        lock=redis.lock("xhs:cli:global",timeout=settings.XHS_CLI_TIMEOUT_SECONDS+30,blocking_timeout=settings.XHS_CLI_TIMEOUT_SECONDS+30)
        try:
            auth_error=await redis.get(CLI_AUTH_INVALID_KEY)
            if auth_error: raise CliAuthenticationExpired(auth_error)
            if await redis.exists(CLI_COOLDOWN_KEY): raise CliCoolingDown("xiaohongshu-cli 正在验证码冷却期")
            if not await lock.acquire(): raise CliCoolingDown("xiaohongshu-cli 全局单并发锁等待超时")
            await asyncio.sleep(random.uniform(3,8))
            with tempfile.TemporaryDirectory(prefix="xhs-cli-") as home:
                proc = await asyncio.create_subprocess_exec(sys.executable, "-m", "app.services.xhs_cli_entrypoint", *args, "--json", stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE, env=self._env(home))
                out, err = await asyncio.wait_for(proc.communicate(), settings.XHS_CLI_TIMEOUT_SECONDS)
        finally:
            try:
                if await lock.owned(): await lock.release()
            finally: await redis.aclose()
        if proc.returncode:
            message = self._error_message(out, err)
            await self._raise_cli_error(message)
        payload = json.loads(out.decode("utf-8"));
        if isinstance(payload, dict) and payload.get("ok") is False:
            message = self._error_message(out, err)
            await self._raise_cli_error(message)
        return payload

    async def search(self, keyword: str) -> list[dict]: return unwrap_items(await self._run("search", keyword, "--sort", "popular"))[:settings.XHS_PROVIDER_CANDIDATE_LIMIT]
    async def detail(self, candidate: Candidate) -> dict: return await self._run("read", candidate.xsec_url or candidate.note_id)


def needs_hydration(c: Candidate) -> bool:
    return any(x in (None, "") for x in (c.title,c.content,c.author_nickname,c.cover_url,c.published_at,c.like_count)) or all(x is None for x in (c.like_count,c.collect_count,c.comment_count,c.share_count))


async def hydrate(
    c: Candidate,
    cli: CliProvider,
    tikhub: TikHubProvider,
    db: Session,
    run_id: int,
    *,
    allow_paid: bool = True,
) -> None:
    if not needs_hydration(c): return
    if c.xsec_url:
        try:
            parsed = await extract_xhs(c.xsec_url)
            extra = normalize_candidate({**parsed, "note_id": c.note_id, "url": c.xsec_url}, "html", 99)
            if extra: c.merge(extra)
        except Exception: logger.exception("xhs HTML 补全失败 note_id=%s", c.note_id)
    if needs_hydration(c):
        started=time.monotonic()
        try:
            payload=await cli.detail(c); extra=normalize_candidate({**(payload.get("data",payload) if isinstance(payload,dict) else {}),"note_id":c.note_id}, FREE_PROVIDER, 99)
            if extra: c.merge(extra)
            log_call(db,FREE_PROVIDER,"detail","success",run_id=run_id,note_id=c.note_id,started=started)
        except Exception as e: log_call(db,FREE_PROVIDER,"detail","failed",run_id=run_id,note_id=c.note_id,started=started,error=e)
    if needs_hydration(c) and allow_paid:
        started=time.monotonic()
        try:
            consume_tikhub_quota(db,operation="detail"); payload=await tikhub.detail(c); extra=normalize_candidate({**(payload.get("data",payload) if isinstance(payload,dict) else {}),"note_id":c.note_id}, PAID_PROVIDER, 99)
            if extra: c.merge(extra)
            log_call(db,PAID_PROVIDER,"detail","success",run_id=run_id,note_id=c.note_id,started=started)
        except Exception as e: log_call(db,PAID_PROVIDER,"detail","blocked" if isinstance(e,TikHubBudgetExhausted) else "failed",run_id=run_id,note_id=c.note_id,started=started,error=e)


def rank(c: Candidate, now: datetime) -> float:
    platform_rank = min(c.ranks.values()) if c.ranks else 20
    search = max(0.0, 1 - ((platform_rank - 1) / 19))
    likes = min(1.0, math.log1p(max(c.like_count or 0,0))/math.log1p(100000))
    fresh = max(0.0, 1 - max((now - c.published_at).total_seconds(),0)/(7*86400)) if c.published_at else 0
    dual = 1 if PAID_PROVIDER in c.ranks and FREE_PROVIDER in c.ranks else 0
    return round((search*.5 + likes*.3 + fresh*.15 + dual*.05)*100, 4)


def fill_title_from_content(c: Candidate, limit: int = 80) -> bool:
    """标题缺失时使用正文第一段生成临时标题；无正文则保持缺失。"""
    if (c.title or "").strip():
        c.title = c.title.strip()
        return False
    content = (c.content or "").strip()
    if not content:
        return False
    paragraphs = [part.strip() for part in re.split(r"\n\s*\n+", content) if part.strip()]
    if not paragraphs:
        return False
    title = re.sub(r"\s+", " ", paragraphs[0]).strip()
    if not title:
        return False
    c.title = title if len(title) <= limit else title[: limit - 1].rstrip() + "…"
    c.title_generated = True
    return True


def rejection_reason(c: Candidate, now: datetime) -> str | None:
    if c.published_at is None or c.like_count is None: return "unknown_metric"
    if c.published_at < now - timedelta(days=7): return "old"
    if c.like_count <= minimum_likes_exclusive(c.published_at, now): return "low_like"
    if c.note_type not in {"image","video"}: return "unknown_type"
    fill_title_from_content(c)
    if not all((c.title,c.content,c.author_nickname,c.cover_url)): return "core_incomplete"
    return None


def pre_hydration_rejection(c: Candidate, now: datetime) -> str | None:
    """只用搜索卡片已有硬指标提前淘汰，避免为明确不合格候选请求详情。"""
    if c.published_at is not None and c.published_at < now-timedelta(days=7):return "old"
    if c.like_count is not None and c.published_at is not None and c.like_count <= minimum_likes_exclusive(c.published_at,now):return "low_like"
    if c.note_type is not None and c.note_type not in {"image","video"}:return "unknown_type"
    return None


def get_xhs_source(db: Session) -> SourceRegistry:
    source=db.execute(select(SourceRegistry).where(SourceRegistry.platform=="xhs_search")).scalar_one_or_none()
    if source: return source
    source=SourceRegistry(name="小红书关键词搜索",platform="xhs_search",source_type="xhs",url="https://www.xiaohongshu.com",requires_auth=True,auth_status="ok",fetch_strategy=FETCH_STRATEGY_CRON,fetch_config={"providers":["tikhub","cli"],"sort":"general"},enabled=True,description="TikHub 与 xiaohongshu-cli 同级每日搜索")
    db.add(source);db.flush();return source


def upsert_note(db: Session, c: Candidate, quality_status: str, now: datetime) -> XhsNote:
    row=db.execute(select(XhsNote).where(XhsNote.note_id==c.note_id)).scalar_one_or_none()
    stable=f"https://www.xiaohongshu.com/explore/{c.note_id}"
    if not row:
        row=XhsNote(note_id=c.note_id,stable_url=stable,first_discovered_at=now,last_discovered_at=now)
        db.add(row)
    for field_name in ("title","content","published_at","note_type","author_id","author_nickname","author_bio","avatar_url","cover_url","like_count","collect_count","comment_count","share_count","view_count"):
        value=getattr(c,field_name)
        if value is not None and value!="": setattr(row,field_name,value)
    row.native_tags=c.tags
    # 新一轮偶尔只拿到裸 URL 时，不要覆盖库里仍可用的最新 token 链接。
    if _xsec_token(c.xsec_url) or not row.latest_xsec_url:
        row.latest_xsec_url=c.xsec_url
    row.last_discovered_at=now;row.detail_status="hydrated";row.media_status="remote_ok" if c.cover_url else "missing";row.quality_status=quality_status;row.comprehensive_score=c.score;row.source_payload={"providers":list(c.ranks),"ranks":c.ranks,"generated_title":c.title_generated}
    db.flush();return row


def upsert_engagement_snapshot(db: Session, note: XhsNote, snapshot_date: date) -> XhsEngagementSnapshot:
    """同一笔记当天再次命中时刷新互动数据，不把当日首次值当成最终值。"""
    snapshot=db.execute(select(XhsEngagementSnapshot).where(XhsEngagementSnapshot.note_id==note.id,XhsEngagementSnapshot.snapshot_date==snapshot_date)).scalar_one_or_none()
    if not snapshot:
        snapshot=XhsEngagementSnapshot(note_id=note.id,snapshot_date=snapshot_date)
        db.add(snapshot)
    for field_name in ("like_count","collect_count","comment_count","share_count","view_count"):
        value=getattr(note,field_name)
        if value is not None:setattr(snapshot,field_name,value)
    return snapshot


def sync_raw_info(db: Session, note: XhsNote) -> None:
    source=get_xhs_source(db)
    raw=db.execute(select(RawInfo).where(RawInfo.url==note.stable_url)).scalar_one_or_none()
    if not raw:
        raw=RawInfo(source_registry_id=source.id,title=note.title or note.note_id,url=note.stable_url)
        db.add(raw)
    raw.title=note.title or note.note_id;raw.author=note.author_nickname;raw.summary=note.ai_summary or (note.content or "")[:500];raw.content=note.content;raw.published_at=note.published_at;raw.scraped_at=utcnow();raw.engagement={"like":note.like_count,"collect":note.collect_count,"comment":note.comment_count,"share":note.share_count,"view":note.view_count};raw.extras={"note_id":note.note_id,"xsec_url":note.latest_xsec_url,"cover_url":note.cover_url,"avatar_url":note.avatar_url,"xhs_search":True};db.flush();note.raw_info_id=raw.id
    if note.quality_status != "ready_degraded":note.quality_status="synced"


def record_discoveries(db: Session, run_id: int, keyword_id: int, note: XhsNote, c, now) -> None:
    """记录本次运行抓到的全部候选（含被淘汰的），供监测页下钻每次抓到了哪些笔记。"""
    for provider,provider_rank in c.ranks.items():
        exists=db.execute(select(XhsNoteDiscovery.id).where(XhsNoteDiscovery.run_id==run_id,XhsNoteDiscovery.note_id==note.id,XhsNoteDiscovery.provider==provider)).scalar_one_or_none()
        if not exists: db.add(XhsNoteDiscovery(note_id=note.id,keyword_id=keyword_id,run_id=run_id,provider=provider,provider_rank=provider_rank,discovered_at=now))


async def collect_keyword(db: Session, keyword_id: int, *, allow_paid: bool = True, retry_existing: bool = False) -> dict:
    now=utcnow(); keyword=db.get(XhsKeyword,keyword_id)
    if not keyword or not keyword.enabled: raise ValueError("关键词不存在或已停用")
    run=db.execute(select(XhsKeywordRun).where(XhsKeywordRun.keyword_id==keyword.id,XhsKeywordRun.run_date==now.date(),XhsKeywordRun.wave=="manual")).scalar_one_or_none()
    if run:
        # 已完成拦截在 API 层（retry 接口 409，force=true 放行）；到这里说明允许重跑
        if not retry_existing: return {"skipped":True,"reason":"same_keyword_same_day"}
        run.status="running";run.started_at=now;run.finished_at=None;run.error_message=None
    else:
        run=XhsKeywordRun(keyword_id=keyword.id,run_date=now.date(),wave="manual",status="running",started_at=now);db.add(run)
    try: db.commit()
    except IntegrityError: db.rollback(); return {"skipped":True,"reason":"same_keyword_same_day"}
    db.refresh(run); cli=CliProvider(); tikhub=TikHubProvider(); batches={FREE_PROVIDER:[],PAID_PROVIDER:[]}
    async def one(provider_name, provider):
        started=time.monotonic()
        if provider_name==PAID_PROVIDER and not allow_paid:
            error=TikHubBudgetExhausted("本次运行仅执行免费链路")
            log_call(db,provider_name,"search","skipped",run_id=run.id,started=started,error=error,request_count=0)
            return [],error
        try:
            if provider_name==PAID_PROVIDER:
                consume_tikhub_quota(db,operation="search")
            items=await provider.search(keyword.keyword);log_call(db,provider_name,"search","success",run_id=run.id,started=started);return items,None
        except Exception as e:
            log_call(db,provider_name,"search","blocked" if isinstance(e,TikHubBudgetExhausted) else "failed",run_id=run.id,started=started,error=e,request_count=0 if isinstance(e,TikHubBudgetExhausted) else 1);return [],e
    # 两个同级来源每次都执行；任一失败不阻断另一来源。
    cli_result, tikhub_result = await asyncio.gather(one(FREE_PROVIDER,cli),one(PAID_PROVIDER,tikhub))
    batches[FREE_PROVIDER],cli_error=cli_result;batches[PAID_PROVIDER],tikhub_error=tikhub_result
    run.cli_status="success" if not cli_error else "cooldown" if isinstance(cli_error,CliCoolingDown) else "failed";run.tikhub_status="skipped_free" if not allow_paid else "success" if not tikhub_error else "blocked_budget" if isinstance(tikhub_error,TikHubBudgetExhausted) else "failed";run.cli_raw_count=len(batches[FREE_PROVIDER]);run.tikhub_raw_count=len(batches[PAID_PROVIDER]);db.commit()
    merged=merge_provider_candidates(batches)
    run.merged_count=len(merged);rejections={"old":0,"low_like":0,"unknown_metric":0,"unknown_type":0,"core_incomplete":0,"rank_overflow":0};eligible=[]
    for c in merged.values():
        reason=pre_hydration_rejection(c,now)
        if reason:
            rejections[reason]+=1;record_discoveries(db,run.id,keyword.id,upsert_note(db,c,"rejected_"+reason,now),c,now);continue
        await hydrate(c,cli,tikhub,db,run.id,allow_paid=allow_paid);reason=rejection_reason(c,now);c.score=rank(c,now)
        if reason: rejections[reason]+=1;record_discoveries(db,run.id,keyword.id,upsert_note(db,c,"rejected_"+reason,now),c,now)
        else: eligible.append(c)
    eligible.sort(key=lambda x:x.score,reverse=True);selected=eligible
    for c in selected:
        note=upsert_note(db,c,"ready_degraded" if c.title_generated else "ready",now);record_discoveries(db,run.id,keyword.id,note,c,now)
        upsert_engagement_snapshot(db,note,now.date())
        sync_raw_info(db,note)
    effective_errors=[x for x in (cli_error,tikhub_error if allow_paid else None) if x]
    daily=[c for c in merged.values() if collection_level(c.published_at,now)=="daily"]
    weekly=[c for c in merged.values() if collection_level(c.published_at,now)=="weekly"]
    rejections["_levels"]={
        "daily":{"candidate_count":len(daily),"eligible_count":sum(qualifies_by_time_and_likes(c.published_at,c.like_count,now) for c in daily),"likes_gt":DAILY_MIN_LIKES_EXCLUSIVE},
        "weekly":{"candidate_count":len(weekly),"eligible_count":sum(qualifies_by_time_and_likes(c.published_at,c.like_count,now) for c in weekly),"likes_gt":WEEKLY_MIN_LIKES_EXCLUSIVE},
    }
    run.within_week_count=len(daily)+len(weekly);run.eligible_like_count=sum(qualifies_by_time_and_likes(c.published_at,c.like_count,now) for c in merged.values());run.filtered_count=len(eligible);run.final_count=len(selected);run.displayable_count=len(selected);run.paid_call_count=db.scalar(select(func.coalesce(func.sum(XhsProviderCall.request_count),0)).where(XhsProviderCall.run_id==run.id,XhsProviderCall.is_paid.is_(True))) or 0;run.rejection_counts=rejections;run.status="completed" if not effective_errors else "partial";run.error_message="; ".join(str(x)[:300] for x in effective_errors) or None;run.finished_at=utcnow();keyword.last_run_at=run.finished_at
    if keyword.keyword_type=="derived": keyword.cooldown_until=now.date()+timedelta(days=3)
    db.commit();return {"run_id":run.id,"keyword":keyword.keyword,"status":run.status,"merged":run.merged_count,"eligible":run.filtered_count,"final":run.final_count,"rejections":rejections}


async def refresh_note_image(db: Session, note_identity: str, *, allow_paid: bool = False) -> dict:
    """管理员显式刷新远程图片 URL；免费失败不会自动升级为 TikHub。"""
    note=db.execute(select(XhsNote).where(XhsNote.note_id==note_identity)).scalar_one_or_none()
    if not note: raise ValueError("素材不存在")
    candidate=Candidate(note_id=note.note_id,title=note.title or "",content=note.content or "",published_at=note.published_at,note_type=note.note_type,author_id=note.author_id,author_nickname=note.author_nickname or "",avatar_url=note.avatar_url,cover_url=None,like_count=note.like_count,xsec_url=note.latest_xsec_url or note.stable_url)
    cli=CliProvider();provider_used="cli";started=time.monotonic()
    try:
        payload=await cli.detail(candidate);extra=normalize_candidate({**(payload.get("data",payload) if isinstance(payload,dict) else {}),"note_id":note.note_id},FREE_PROVIDER,1)
        if extra:candidate.merge(extra)
        log_call(db,FREE_PROVIDER,"image_refresh","success",note_id=note.note_id,started=started)
    except Exception as free_error:
        log_call(db,FREE_PROVIDER,"image_refresh","failed",note_id=note.note_id,started=started,error=free_error)
        if not allow_paid:return {"refreshed":False,"paid_request":False,"reason":str(free_error)[:300]}
        provider_used="tikhub";started=time.monotonic();consume_tikhub_quota(db,operation="detail")
        payload=await TikHubProvider().detail(candidate);extra=normalize_candidate({**(payload.get("data",payload) if isinstance(payload,dict) else {}),"note_id":note.note_id},PAID_PROVIDER,1)
        if extra:candidate.merge(extra)
        log_call(db,PAID_PROVIDER,"image_refresh","success",note_id=note.note_id,started=started)
    if not candidate.cover_url:return {"refreshed":False,"paid_request":provider_used=="tikhub","reason":"来源未返回新封面 URL"}
    note.cover_url=candidate.cover_url
    if candidate.avatar_url:note.avatar_url=candidate.avatar_url
    note.media_status="remote_ok";note.last_discovered_at=utcnow()
    from app.models.xhs import XhsImageFailureReport
    for report in db.scalars(select(XhsImageFailureReport).where(XhsImageFailureReport.note_id==note.id,XhsImageFailureReport.status=="open")):
        report.status="resolved"
    db.commit();return {"refreshed":True,"paid_request":provider_used=="tikhub","provider":provider_used,"cover_url":note.cover_url}
