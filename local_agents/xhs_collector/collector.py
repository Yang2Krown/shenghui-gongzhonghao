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


class XhsCollector:
    COLLECTION_TIMEOUT_SECONDS = 8 * 60

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
        deadline = time.monotonic() + self.COLLECTION_TIMEOUT_SECONDS
        search_payload = self._run_cli("search", keyword, "--sort", "popular")
        search_rows = unwrap(search_payload)
        recognized_results = has_result_list(search_payload)
        diagnostics = {
            "version": 1,
            "search_state": "empty" if recognized_results and not search_rows else "ok" if recognized_results else "unrecognized",
            "search_returned_count": len(search_rows),
            "considered_count": min(20, len(search_rows)),
            "normalized_count": 0,
            "within_week_count": 0,
            "eligible_like_count": 0,
            "detail_attempted_count": 0,
            "detail_success_count": 0,
            "final_candidate_count": 0,
            "rejection_counts": {"invalid_payload": 0, "old": 0, "unknown_date": 0, "low_like": 0, "unknown_metric": 0},
        }
        candidates = []
        cutoff = datetime.now() - timedelta(days=7)
        for rank, raw in enumerate(search_rows[:20], 1):
            item = normalize(raw, rank)
            if not item:
                diagnostics["rejection_counts"]["invalid_payload"] += 1
                continue
            diagnostics["normalized_count"] += 1
            published = item.get("published_at")
            likes = (item.get("engagement") or {}).get("likes")
            if published is None:
                diagnostics["rejection_counts"]["unknown_date"] += 1
                continue
            if published < cutoff:
                diagnostics["rejection_counts"]["old"] += 1
                continue
            diagnostics["within_week_count"] += 1
            if likes is None:
                diagnostics["rejection_counts"]["unknown_metric"] += 1
                continue
            if likes <= 2000:
                diagnostics["rejection_counts"]["low_like"] += 1
                continue
            diagnostics["eligible_like_count"] += 1
            candidates.append(item)
        candidates.sort(key=lambda item: ((item.get("engagement") or {}).get("likes") or 0), reverse=True)
        results = []
        for item in candidates[:10]:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            detail = None
            diagnostics["detail_attempted_count"] += 1
            try:
                detail_payload = self._run_cli(
                    "read", item["original_url"], timeout_seconds=min(120, remaining),
                )
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
            if len(results) < min(10, len(candidates)):
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    break
                time.sleep(min(random.uniform(20, 40), remaining))
        diagnostics["final_candidate_count"] = len(results)
        return {"notes": results, "diagnostics": diagnostics}
