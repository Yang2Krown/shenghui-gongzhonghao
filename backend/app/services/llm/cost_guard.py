"""LLM 成本预算和 provider 失败熔断。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal
from typing import Any, Optional

from sqlalchemy import case, desc, func, select

from app.core.config import settings
from app.core.timezone import utcnow
from app.db.session import AsyncSessionLocal
from app.models.llm_monitoring import LlmCallLog


class CostGuardBlocked(RuntimeError):
    """成本防护拒绝外部调用。"""

    def __init__(self, message: str, *, reason: str, retry_after_seconds: Optional[int] = None):
        super().__init__(message)
        self.reason = reason
        self.retry_after_seconds = retry_after_seconds


@dataclass(frozen=True)
class ProviderGuardState:
    provider: str
    calls: int
    failures: int
    failure_rate: float
    cost_yuan_24h: float
    blocked: bool
    reason: Optional[str] = None
    retry_after_seconds: Optional[int] = None


def _money(value: Any) -> float:
    if value is None:
        return 0.0
    if isinstance(value, Decimal):
        return float(value)
    return float(value)


async def ensure_llm_call_allowed(provider: str, model: str) -> None:
    """在真实发起外部 LLM 调用前执行预算和熔断检查。"""
    if not settings.COST_GUARD_ENABLED:
        return

    async with AsyncSessionLocal() as db:
        status = await collect_llm_guard_status(db)

    overall = status["overall"]
    if overall["blocked"]:
        raise CostGuardBlocked(
            overall["message"],
            reason=overall["reason"],
            retry_after_seconds=overall.get("retry_after_seconds"),
        )

    provider_state = next((item for item in status["providers"] if item["provider"] == provider), None)
    if provider_state and provider_state["blocked"]:
        raise CostGuardBlocked(
            f"{provider}/{model} 暂时熔断：{provider_state['reason']}",
            reason=provider_state["reason"],
            retry_after_seconds=provider_state.get("retry_after_seconds"),
        )


async def collect_llm_guard_status(db) -> dict[str, Any]:
    """返回后台展示用的 LLM 成本防护状态。"""
    now = utcnow()
    last_24h = now - timedelta(hours=24)
    window_start = now - timedelta(minutes=settings.LLM_FAILURE_BREAKER_WINDOW_MINUTES)

    total_cost_24h = _money((await db.execute(
        select(func.coalesce(func.sum(LlmCallLog.cost_yuan), 0)).where(LlmCallLog.created_at >= last_24h)
    )).scalar_one())

    provider_cost_rows = (await db.execute(
        select(
            LlmCallLog.provider,
            func.count(LlmCallLog.id),
            func.coalesce(func.sum(LlmCallLog.cost_yuan), 0),
        )
        .where(LlmCallLog.created_at >= last_24h)
        .group_by(LlmCallLog.provider)
        .order_by(desc(func.coalesce(func.sum(LlmCallLog.cost_yuan), 0)))
    )).all()

    provider_failure_rows = (await db.execute(
        select(
            LlmCallLog.provider,
            func.count(LlmCallLog.id),
            func.coalesce(func.sum(case((LlmCallLog.status == "failed", 1), else_=0)), 0),
            func.max(LlmCallLog.created_at),
        )
        .where(LlmCallLog.created_at >= window_start)
        .group_by(LlmCallLog.provider)
    )).all()

    failure_by_provider = {
        provider: {
            "calls": int(calls or 0),
            "failures": int(failures or 0),
            "latest_at": latest_at,
        }
        for provider, calls, failures, latest_at in provider_failure_rows
    }

    providers = []
    seen = set()
    for provider, calls_24h, cost_24h in provider_cost_rows:
        seen.add(provider)
        failure = failure_by_provider.get(provider, {"calls": 0, "failures": 0, "latest_at": None})
        providers.append(_provider_state(provider, int(calls_24h or 0), _money(cost_24h), failure, now))

    for provider, failure in failure_by_provider.items():
        if provider in seen:
            continue
        providers.append(_provider_state(provider, 0, 0.0, failure, now))

    daily_budget = float(settings.LLM_DAILY_BUDGET_YUAN or 0)
    budget_blocked = daily_budget > 0 and total_cost_24h >= daily_budget
    overall = {
        "enabled": settings.COST_GUARD_ENABLED,
        "blocked": budget_blocked,
        "reason": "daily_budget_exceeded" if budget_blocked else None,
        "message": (
            f"24 小时 LLM 成本 ¥{round(total_cost_24h, 2)} 已达到全局预算 ¥{daily_budget}"
            if budget_blocked else "LLM 成本防护正常"
        ),
        "cost_yuan_24h": round(total_cost_24h, 4),
        "daily_budget_yuan": daily_budget,
        "provider_daily_budget_yuan": float(settings.LLM_PROVIDER_DAILY_BUDGET_YUAN or 0),
    }

    return {
        "overall": overall,
        "breaker": {
            "enabled": settings.LLM_FAILURE_BREAKER_ENABLED,
            "window_minutes": settings.LLM_FAILURE_BREAKER_WINDOW_MINUTES,
            "min_calls": settings.LLM_FAILURE_BREAKER_MIN_CALLS,
            "failure_rate": settings.LLM_FAILURE_BREAKER_FAILURE_RATE,
            "cooldown_minutes": settings.LLM_FAILURE_BREAKER_COOLDOWN_MINUTES,
        },
        "providers": providers,
    }


def _provider_state(provider: str, calls_24h: int, cost_24h: float, failure: dict, now) -> dict[str, Any]:
    calls = int(failure.get("calls") or 0)
    failures = int(failure.get("failures") or 0)
    failure_rate = round(failures / calls, 4) if calls else 0
    provider_budget = float(settings.LLM_PROVIDER_DAILY_BUDGET_YUAN or 0)

    budget_blocked = provider_budget > 0 and cost_24h >= provider_budget
    breaker_blocked = (
        settings.LLM_FAILURE_BREAKER_ENABLED
        and calls >= settings.LLM_FAILURE_BREAKER_MIN_CALLS
        and failure_rate >= settings.LLM_FAILURE_BREAKER_FAILURE_RATE
    )
    retry_after = None
    if breaker_blocked and failure.get("latest_at"):
        cooldown_until = failure["latest_at"] + timedelta(minutes=settings.LLM_FAILURE_BREAKER_COOLDOWN_MINUTES)
        retry_after = max(0, int((cooldown_until - now).total_seconds()))
        breaker_blocked = retry_after > 0

    reason = None
    if budget_blocked:
        reason = "provider_daily_budget_exceeded"
    elif breaker_blocked:
        reason = "provider_failure_breaker"

    return {
        "provider": provider,
        "calls_24h": calls_24h,
        "cost_yuan_24h": round(cost_24h, 4),
        "calls_window": calls,
        "failures_window": failures,
        "failure_rate_window": failure_rate,
        "blocked": bool(reason),
        "reason": reason,
        "retry_after_seconds": retry_after,
    }
