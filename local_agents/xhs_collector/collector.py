from __future__ import annotations

import random
import time
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import urlencode

import cli_entrypoint  # noqa: F401  # import 副作用：给 search_notes 注入「一周内」过滤
from xhs_cli import client_mixins
from xhs_cli.client import XhsClient
from xhs_cli.cookies import cache_note_context, load_saved_cookies
from xhs_cli.exceptions import (
    IpBlockedError,
    NeedVerifyError,
    SessionExpiredError,
    SignatureError,
)
from xhs_cli.formatter import parse_note_reference

from normalizer import has_result_list, merge, normalize, unwrap


class RiskBlocked(RuntimeError):
    def __init__(self, message: str, verification_url: str | None = None):
        super().__init__(message)
        self.verification_url = verification_url


class AuthenticationExpired(RuntimeError):
    """小红书明确拒绝当前登录态，需要重新登录。"""


DAILY_MIN_LIKES_EXCLUSIVE = 200
WEEKLY_MIN_LIKES_EXCLUSIVE = 2000
DAILY_EXPANSION_TARGET = 10
MAX_PAGE_DUPLICATE_RATIO = 0.8

SORT_MAP = {
    "general": "general",
    "popular": "popularity_descending",
    "latest": "time_descending",
}


def collection_level(published_at: datetime, now: datetime) -> str:
    return "daily" if published_at >= now - timedelta(hours=24) else "weekly"


class XhsCollector:
    """单常驻 XhsClient 采集器。

    所有关键词在同一进程、同一会话下串行采集，复用 search session、限速计数
    与签名状态，避免过去「每关键词一个子进程」造成的会话碎片化指纹。
    """

    def __init__(self, root: Path):
        self.root = root
        self._client: XhsClient | None = None

    # ─── 会话生命周期 ────────────────────────────────────────────────────────

    def _build_client(self, cookies: dict) -> XhsClient:
        if client_mixins.ReadingEndpointsMixin.search_notes.__name__ != "_search_notes_with_matching_filters":
            raise RuntimeError("cli_entrypoint 的「一周内」过滤 patch 未生效，采集结果将不受时间约束")
        return XhsClient(
            cookies,
            timeout=30,
            request_delay=random.uniform(6, 12),
            max_retries=2,
        )

    def _ensure_client(self) -> XhsClient:
        if self._client is None:
            cookies = load_saved_cookies() or {}
            cookies.pop("saved_at", None)
            if not cookies.get("a1"):
                raise AuthenticationExpired("本地无可用小红书 Cookie，请先扫码或浏览器同步")
            self._client = self._build_client(cookies)
        return self._client

    def reset_session(self) -> None:
        """登录刷新 Cookie 后调用：丢弃旧 client，下次采集用新 Cookie 重建。"""
        if self._client is not None:
            try:
                self._client.close()
            finally:
                self._client = None

    # ─── 异常映射与 captcha URL ──────────────────────────────────────────────

    @staticmethod
    def _captcha_url(verify_type: str, verify_uuid: str) -> str | None:
        if not verify_uuid or verify_uuid == "unknown":
            return None
        query = urlencode({
            "redirectPath": "https://www.xiaohongshu.com/explore",
            "verifyUuid": verify_uuid,
            "verifyType": verify_type or "unknown",
            "verifyBiz": "461",
        })
        return f"https://www.xiaohongshu.com/website-login/captcha?{query}"

    def _call(self, fn, *args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except NeedVerifyError as exc:
            raise RiskBlocked(str(exc), self._captcha_url(exc.verify_type, exc.verify_uuid)) from exc
        except IpBlockedError as exc:
            raise RiskBlocked(str(exc), None) from exc
        except SessionExpiredError as exc:
            raise AuthenticationExpired(str(exc)) from exc
        except SignatureError as exc:
            # 签名失效(300015)通常是 a1/web_session 已失效，按会话过期走重新登录。
            raise AuthenticationExpired(f"签名失效(300015)，按会话过期处理: {exc}") from exc

    # ─── 进程内 search / read / status ───────────────────────────────────────

    def _search(self, keyword: str, sort: str, page: int) -> dict:
        client = self._ensure_client()
        result = self._call(
            client.search_notes,
            keyword=keyword,
            page=page,
            sort=SORT_MAP.get(sort, "general"),
            note_type=0,
        )
        # 复刻 CLI search 的 token 自动缓存，保证后续 read 有 xsec_token 可用。
        for item in (result or {}).get("items", []):
            note_card = item.get("note_card", {}) if isinstance(item, dict) else {}
            note_id = item.get("id", note_card.get("note_id", ""))
            token = item.get("xsec_token", note_card.get("xsec_token", ""))
            if note_id and token:
                cache_note_context(note_id, token, "pc_search")
        return result

    def _read(self, url: str) -> dict:
        note_id, token, source = parse_note_reference(url)
        client = self._ensure_client()
        if token:
            cache_note_context(note_id, token, source or "pc_feed")
        return self._call(
            client.get_note_detail,
            note_id,
            xsec_token=token,
            xsec_source=source or "pc_feed",
        )

    def check_status(self) -> None:
        """校验当前 Cookie 是否仍有效。不 force_refresh，异常即状态。"""
        client = self._ensure_client()
        self._call(client.get_self_info)

    # ─── 关键词采集 ──────────────────────────────────────────────────────────

    def collect_keyword(self, keyword: str) -> dict:
        searches = []
        now = datetime.now()

        def fetch_page(level: str, sort: str, page: int) -> dict:
            payload = self._search(keyword, sort, page)
            search = {
                "level": level, "sort": sort, "page": page, "payload": payload,
                "rows": unwrap(payload), "recognized": has_result_list(payload),
            }
            searches.append(search)
            return search

        def page_signal(rows: list, threshold: int, expected_level: str | None = None) -> tuple[set[str], int, int]:
            note_ids: set[str] = set()
            eligible = 0
            max_likes = 0
            for rank, raw in enumerate(rows, 1):
                item = normalize(raw, rank)
                if not item:
                    continue
                note_ids.add(item["note_id"])
                published = item.get("published_at")
                likes = (item.get("engagement") or {}).get("likes")
                if published is None or likes is None or published < now - timedelta(days=7):
                    continue
                max_likes = max(max_likes, likes)
                if likes > threshold and (expected_level is None or collection_level(published, now) == expected_level):
                    eligible += 1
            return note_ids, eligible, max_likes

        # Latest is time-ordered, so low likes on page 1 do not predict page 2.
        # Fetch two pages by default and only expand to page 3 when qualified
        # daily results are scarce and page 2 still contains genuinely new rows.
        daily_first = fetch_page("daily", "latest", 1)
        daily_searches = [daily_first]
        if daily_first["rows"]:
            daily_second = fetch_page("daily", "latest", 2)
            daily_searches.append(daily_second)
            first_ids, first_eligible, _ = page_signal(daily_first["rows"], DAILY_MIN_LIKES_EXCLUSIVE, "daily")
            second_ids, second_eligible, _ = page_signal(daily_second["rows"], DAILY_MIN_LIKES_EXCLUSIVE, "daily")
            duplicate_ratio = len(first_ids & second_ids) / max(1, len(second_ids))
            if (
                daily_second["rows"]
                and first_eligible + second_eligible < DAILY_EXPANSION_TARGET
                and duplicate_ratio < MAX_PAGE_DUPLICATE_RATIO
            ):
                daily_searches.append(fetch_page("daily", "latest", 3))

        # Popular is roughly heat-ordered. If page 1 has no item above the
        # weekly threshold, later pages have very low expected value, so stop.
        weekly_first = fetch_page("weekly", "popular", 1)
        weekly_searches = [weekly_first]
        _, _, weekly_max_likes = page_signal(weekly_first["rows"], WEEKLY_MIN_LIKES_EXCLUSIVE)
        if weekly_first["rows"] and weekly_max_likes > WEEKLY_MIN_LIKES_EXCLUSIVE:
            weekly_searches.append(fetch_page("weekly", "popular", 2))
        recognized_count = sum(item["recognized"] for item in searches)
        returned_count = sum(len(item["rows"]) for item in searches)
        diagnostics = {
            "version": 2,
            "search_state": "empty" if recognized_count == len(searches) and returned_count == 0 else "ok" if recognized_count else "unrecognized",
            "search_returned_count": returned_count,
            "considered_count": sum(len(item["rows"]) for item in searches),
            "searches": [
                {"level": item["level"], "sort": item["sort"], "page": item["page"], "returned_count": len(item["rows"]), "recognized": item["recognized"]}
                for item in searches
            ],
            "pagination": {
                "daily_pages": [item["page"] for item in daily_searches],
                "weekly_pages": [item["page"] for item in weekly_searches],
            },
            "normalized_count": 0,
            "within_week_count": 0,
            "eligible_like_count": 0,
            "levels": {
                "daily": {"candidate_count": 0, "eligible_count": 0, "likes_gt": DAILY_MIN_LIKES_EXCLUSIVE},
                "weekly": {"candidate_count": 0, "eligible_count": 0, "likes_gt": WEEKLY_MIN_LIKES_EXCLUSIVE},
            },
            "detail_attempted_count": 0,
            "detail_success_count": 0,
            "final_candidate_count": 0,
            "rejection_counts": {"invalid_payload": 0, "duplicate": 0, "level_mismatch": 0, "old": 0, "unknown_date": 0, "low_like": 0, "unknown_metric": 0},
        }
        candidates_by_level = {"daily": [], "weekly": []}
        seen_note_ids = set()
        cutoff = now - timedelta(days=7)
        for search in searches:
            for page_rank, raw in enumerate(search["rows"], 1):
                rank = (search["page"] - 1) * 20 + page_rank
                item = normalize(raw, rank)
                if not item:
                    diagnostics["rejection_counts"]["invalid_payload"] += 1
                    continue
                note_id = item["note_id"]
                if note_id in seen_note_ids:
                    diagnostics["rejection_counts"]["duplicate"] += 1
                    continue
                published = item.get("published_at")
                if published is None:
                    diagnostics["rejection_counts"]["unknown_date"] += 1
                    continue
                if published < cutoff:
                    diagnostics["rejection_counts"]["old"] += 1
                    continue
                level = collection_level(published, now)
                seen_note_ids.add(note_id)
                diagnostics["normalized_count"] += 1
                diagnostics["within_week_count"] += 1
                diagnostics["levels"][level]["candidate_count"] += 1
                likes = (item.get("engagement") or {}).get("likes")
                if likes is None:
                    diagnostics["rejection_counts"]["unknown_metric"] += 1
                    continue
                threshold = diagnostics["levels"][level]["likes_gt"]
                if likes <= threshold:
                    diagnostics["rejection_counts"]["low_like"] += 1
                    continue
                diagnostics["eligible_like_count"] += 1
                diagnostics["levels"][level]["eligible_count"] += 1
                item["collection_level"] = level
                item["collection_sort"] = search["sort"]
                candidates_by_level[level].append(item)

        candidates = candidates_by_level["daily"] + candidates_by_level["weekly"]
        candidates.sort(key=lambda item: ((item.get("engagement") or {}).get("likes") or 0), reverse=True)
        results = []
        for item in candidates:
            detail = None
            diagnostics["detail_attempted_count"] += 1
            try:
                detail_payload = self._read(item["original_url"])
                detail_rows = unwrap(detail_payload)
                detail = normalize(detail_rows[0], item["provider_rank"]) if detail_rows else normalize(detail_payload, item["provider_rank"])
                if detail:
                    diagnostics["detail_success_count"] += 1
            except RiskBlocked:
                raise
            except Exception:
                detail = None
            merged = merge(item, detail)
            if isinstance(merged.get("published_at"), datetime):
                merged["published_at"] = merged["published_at"].isoformat()
            results.append(merged)
            if len(results) < len(candidates):
                time.sleep(random.uniform(15, 45))
        diagnostics["final_candidate_count"] = len(results)

        # 461 探针：详情抓取触发的人机验证会被 get_note_detail 降级 HTML 吞掉，
        # 但 XhsClient._handle_response 已累加 _verify_count。这里读出并主动转为
        # 风控信号，保证「触发即停」，不被降级路径掩盖。
        verify_count = getattr(self._client, "_verify_count", 0) if self._client is not None else 0
        if verify_count > 0:
            self._client._verify_count = 0
            raise RiskBlocked(f"详情抓取触发 {verify_count} 次人机验证（已被降级掩盖），进入冷却")

        return {"notes": results, "diagnostics": diagnostics}
