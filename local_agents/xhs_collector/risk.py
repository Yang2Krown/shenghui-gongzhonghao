from __future__ import annotations

import random
from datetime import datetime, timedelta
from typing import Any

# 自适应风控退避。原则（参考 MediaCrawler）：触发人机验证即停，冷却随连续触发
# 指数拉长，连续成功缓慢回升，绝不短冷却硬冲。首次触发落在 [8,12] 分钟，
# 与旧的 RISK_COOLDOWN_MINUTES=(8,12) 等价，向后兼容。
COOLDOWN_FLOOR_MINUTES = 10.0
COOLDOWN_CAP_MINUTES = 240.0
BACKOFF_MULTIPLIER = 2.0
RECOVERY_STEP = 0.85
RECOVERY_SUCCESS_THRESHOLD = 5
JITTER_PCT = 0.2

STATE_KEY = "risk_state"
# 恢复时间戳沿用既有 key，scheduler/requeue_risk_slots/resume_after 都读它，协议不变。
COOLDOWN_UNTIL_KEY = "risk_cooldown_until"


class RiskBackoff:
    def __init__(self, store):
        self.store = store

    def _load(self) -> dict[str, Any]:
        state = self.store.get(STATE_KEY)
        if not isinstance(state, dict):
            state = {}
        return {
            "consecutive_blocks": int(state.get("consecutive_blocks") or 0),
            "consecutive_successes": int(state.get("consecutive_successes") or 0),
            "cooldown_minutes": float(state.get("cooldown_minutes") or COOLDOWN_FLOOR_MINUTES),
        }

    def _save(self, state: dict[str, Any]) -> None:
        self.store.set(STATE_KEY, {
            "consecutive_blocks": state["consecutive_blocks"],
            "consecutive_successes": state["consecutive_successes"],
            "cooldown_minutes": state["cooldown_minutes"],
            "updated_at": datetime.now().isoformat(timespec="seconds"),
        })

    def current_cooldown_minutes(self) -> float:
        return self._load()["cooldown_minutes"]

    def _cooldown_active(self) -> datetime | None:
        """冷却未过期则返回恢复时间，否则 None。"""
        stored = self.store.get(COOLDOWN_UNTIL_KEY)
        if not stored:
            return None
        try:
            resume_at = datetime.fromisoformat(stored)
        except ValueError:
            return None
        return resume_at if resume_at > datetime.now() else None

    def on_block(self) -> datetime:
        """触发人机验证：指数拉长冷却并写恢复时间。冷却未过期时幂等，不累加计数。

        冷却时长只由「连续触发次数」决定：floor × multiplier^(blocks-1)，封顶 cap。
        序列 10 → 20 → 40 → 80 → 160 → 240（封顶），不叠加历史基数，可预测。
        """
        active = self._cooldown_active()
        if active is not None:
            return active
        state = self._load()
        state["consecutive_blocks"] += 1
        state["consecutive_successes"] = 0
        cooldown = min(
            COOLDOWN_CAP_MINUTES,
            COOLDOWN_FLOOR_MINUTES * (BACKOFF_MULTIPLIER ** (state["consecutive_blocks"] - 1)),
        )
        state["cooldown_minutes"] = cooldown
        actual = cooldown * random.uniform(1 - JITTER_PCT, 1 + JITTER_PCT)
        resume_at = datetime.now() + timedelta(minutes=actual)
        self.store.set(COOLDOWN_UNTIL_KEY, resume_at.isoformat(timespec="minutes"))
        self._save(state)
        return resume_at

    def on_success(self) -> None:
        """一个关键词采集成功：累计连续成功，达阈值则冷却基数缓慢回升。"""
        state = self._load()
        state["consecutive_successes"] += 1
        if state["consecutive_successes"] % RECOVERY_SUCCESS_THRESHOLD == 0:
            state["cooldown_minutes"] = max(
                COOLDOWN_FLOOR_MINUTES,
                state["cooldown_minutes"] * RECOVERY_STEP,
            )
            state["consecutive_blocks"] = max(0, state["consecutive_blocks"] - 1)
        self._save(state)

    def on_manual_verify(self) -> None:
        """人工验证通过 / 登录成功：人工已介入，风险信号重置。"""
        self._save({
            "consecutive_blocks": 0,
            "consecutive_successes": 0,
            "cooldown_minutes": COOLDOWN_FLOOR_MINUTES,
        })
