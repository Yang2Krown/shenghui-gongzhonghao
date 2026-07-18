from __future__ import annotations

import hashlib
import random
from datetime import date, datetime, timedelta
from typing import Any


SCHEDULE_GRACE_MINUTES = 12


def _clock_minutes(value: str) -> int:
    hour, minute = (int(part) for part in value.split(":", 1))
    return hour * 60 + minute


def select_daily_keywords(day: date, keywords: list[dict[str, Any]], derived_limit: int = 5) -> list[dict[str, Any]]:
    """Select every enabled base keyword plus a restart-safe random derived sample."""
    base = sorted((item for item in keywords if item.get("type") == "base"), key=lambda item: int(item["id"]))
    derived = sorted(
        (item for item in keywords if item.get("type") == "derived" and item.get("eligible", True)),
        key=lambda item: int(item["id"]),
    )
    seed_source = f"sample:{day.isoformat()}:{','.join(str(item['id']) for item in derived)}"
    rng = random.Random(int(hashlib.sha256(seed_source.encode()).hexdigest()[:16], 16))
    sample = rng.sample(derived, min(max(0, derived_limit), len(derived)))
    return base + sample


def build_daily_plan(
    day: date,
    keywords: list[dict[str, Any]],
    window_start: str = "09:30",
    window_end: str = "22:30",
    jitter_minutes: int = 8,
) -> list[dict[str, Any]]:
    """Spread the selected daily set across the day with restart-safe shuffle and jitter."""
    if not keywords:
        return []
    start = _clock_minutes(window_start)
    end = _clock_minutes(window_end)
    if end <= start:
        raise ValueError("全天采集结束时间必须晚于开始时间")
    ordered = sorted(keywords, key=lambda item: (int(item.get("id") or 0), str(item.get("keyword") or "")))
    interval = (end - start) / max(1, len(ordered) - 1)
    seed_source = f"{day.isoformat()}:{','.join(str(item.get('id')) for item in ordered)}"
    rng = random.Random(int(hashlib.sha256(seed_source.encode()).hexdigest()[:16], 16))
    rng.shuffle(ordered)
    # With 35 keywords the natural interval is about 23 minutes. Bound jitter so
    # adjacent slots still remain at least 15 minutes apart.
    safe_jitter = min(jitter_minutes, max(0, int((interval - 15) / 2)))
    plan: list[dict[str, Any]] = []
    for index, keyword in enumerate(ordered):
        base = start if len(ordered) == 1 else start + interval * index
        # Endpoints only jitter inward; interior slots can move in either direction.
        if index == 0:
            jitter = rng.randint(0, safe_jitter)
        elif index == len(ordered) - 1:
            jitter = rng.randint(-safe_jitter, 0)
        else:
            jitter = rng.randint(-safe_jitter, safe_jitter)
        minute_of_day = round(base + jitter)
        scheduled_at = datetime.combine(day, datetime.min.time()) + timedelta(minutes=minute_of_day)
        plan.append({
            "keyword_id": int(keyword["id"]),
            "keyword": str(keyword["keyword"]),
            "keyword_type": str(keyword.get("type") or "base"),
            "group": keyword.get("group"),
            "scheduled_at": scheduled_at.isoformat(timespec="minutes"),
            "status": "pending",
        })
    return plan


def slot_due(now: datetime, scheduled_at: str, grace_minutes: int = SCHEDULE_GRACE_MINUTES) -> bool:
    planned = datetime.fromisoformat(scheduled_at)
    return timedelta(0) <= now - planned < timedelta(minutes=grace_minutes)


def slot_expired(now: datetime, scheduled_at: str, grace_minutes: int = SCHEDULE_GRACE_MINUTES) -> bool:
    return now - datetime.fromisoformat(scheduled_at) >= timedelta(minutes=grace_minutes)


def recover_interrupted_slots(plan: dict[str, Any], now: datetime) -> int:
    """Close persisted running slots; no scheduled task survives its scheduler iteration."""
    recovered = 0
    for slot in plan.get("slots", []):
        if slot.get("status") != "running":
            continue
        slot["status"] = "failed"
        slot["finished_at"] = now.isoformat(timespec="seconds")
        slot["error"] = "本地 Agent 异常中断，已自动结束，未重复采集"
        recovered += 1
    return recovered
