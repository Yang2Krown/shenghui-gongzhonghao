from __future__ import annotations

import json
import os
import random
import subprocess
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

from normalizer import has_result_list, merge, normalize, unwrap


class RiskBlocked(RuntimeError):
    pass


DAILY_MIN_LIKES_EXCLUSIVE = 200
WEEKLY_MIN_LIKES_EXCLUSIVE = 2000


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
            message = str(error or process.stderr or stdout or "CLI 执行失败")
            lowered = message.lower()
            if any(value in lowered for value in ("captcha", "verification_required", "461", "471")):
                raise RiskBlocked(message[:1000])
            raise RuntimeError(message[:1000])
        return payload if isinstance(payload, dict) else {"data": payload}

    def collect_keyword(self, keyword: str) -> dict:
        searches = []
        for level, sort in (("daily", "latest"), ("weekly", "popular")):
            payload = self._run_cli("search", keyword, "--sort", sort)
            rows = unwrap(payload)
            searches.append({
                "level": level,
                "sort": sort,
                "payload": payload,
                "rows": rows,
                "recognized": has_result_list(payload),
            })
        recognized_count = sum(item["recognized"] for item in searches)
        returned_count = sum(len(item["rows"]) for item in searches)
        diagnostics = {
            "version": 2,
            "search_state": "empty" if recognized_count == len(searches) and returned_count == 0 else "ok" if recognized_count else "unrecognized",
            "search_returned_count": returned_count,
            "considered_count": sum(len(item["rows"]) for item in searches),
            "searches": [
                {"level": item["level"], "sort": item["sort"], "returned_count": len(item["rows"]), "recognized": item["recognized"]}
                for item in searches
            ],
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
        now = datetime.now()
        cutoff = now - timedelta(days=7)
        for search in searches:
            for rank, raw in enumerate(search["rows"], 1):
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
