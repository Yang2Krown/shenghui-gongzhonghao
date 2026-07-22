from __future__ import annotations

import json
import os
import random
import re
import subprocess
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import urlencode

from normalizer import has_result_list, merge, normalize, unwrap


class RiskBlocked(RuntimeError):
    def __init__(self, message: str, verification_url: str | None = None):
        super().__init__(message)
        self.verification_url = verification_url


DAILY_MIN_LIKES_EXCLUSIVE = 200
WEEKLY_MIN_LIKES_EXCLUSIVE = 2000
DAILY_EXPANSION_TARGET = 10
MAX_PAGE_DUPLICATE_RATIO = 0.8


def collection_level(published_at: datetime, now: datetime) -> str:
    return "daily" if published_at >= now - timedelta(hours=24) else "weekly"


class XhsCollector:
    def __init__(self, root: Path):
        self.entrypoint = root / "cli_entrypoint.py"

    def _run_cli(self, *args: str, timeout_seconds: float = 120) -> dict:
        env = os.environ.copy()
        env["OUTPUT"] = "json"
        process = subprocess.run(
            [sys.executable, str(self.entrypoint), *args, "--json"],
            env=env, capture_output=True, text=True, timeout=max(1, timeout_seconds),
        )
        stdout = process.stdout.strip()
        payload = None
        if stdout:
            try: payload = json.loads(stdout)
            except json.JSONDecodeError: pass
        if process.returncode or (isinstance(payload, dict) and payload.get("ok") is False):
            error = payload.get("error") if isinstance(payload, dict) else None
            error_code = str(error.get("code") or "") if isinstance(error, dict) else ""
            message = str(error.get("message") or error) if isinstance(error, dict) else str(error or process.stderr or stdout or "CLI 执行失败")
            lowered = message.lower()
            if error_code in {"verification_required", "ip_blocked"} or any(value in lowered for value in ("captcha", "verification_required", "461", "471")):
                verify_type = re.search(r"type=([^,\s]+)", message)
                verify_uuid = re.search(r"uuid=([^,\s]+)", message)
                verification_url = None
                if verify_uuid and verify_uuid.group(1) != "unknown":
                    query = urlencode({
                        "redirectPath": "https://www.xiaohongshu.com/explore",
                        "verifyUuid": verify_uuid.group(1),
                        "verifyType": verify_type.group(1) if verify_type else "unknown",
                        "verifyBiz": "461",
                    })
                    verification_url = f"https://www.xiaohongshu.com/website-login/captcha?{query}"
                raise RiskBlocked(message[:1000], verification_url)
            raise RuntimeError(message[:1000])
        return payload if isinstance(payload, dict) else {"data": payload}

    def collect_keyword(self, keyword: str) -> dict:
        searches = []
        now = datetime.now()

        def fetch_page(level: str, sort: str, page: int) -> dict:
            payload = self._run_cli("search", keyword, "--sort", sort, "--page", str(page))
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
                detail_payload = self._run_cli("read", item["original_url"])
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
                time.sleep(random.uniform(20, 40))
        diagnostics["final_candidate_count"] = len(results)
        return {"notes": results, "diagnostics": diagnostics}
