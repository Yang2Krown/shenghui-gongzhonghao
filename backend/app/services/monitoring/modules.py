"""后台独立监测模块聚合。"""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import case, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.timezone import utcnow
from app.models.api_request_log import ApiRequestLog
from app.models.credit import CreditTransaction, UserCredit
from app.models.llm_monitoring import LlmCallLog, LlmModelPricing
from app.models.payment import PaymentOrder
from app.models.raw_info import RawInfo
from app.models.source_registry import SourceRegistry
from app.models.user import User
from app.services.llm.monitoring import ensure_default_pricing


def _iso(dt) -> str | None:
    return dt.isoformat() if dt else None


def _date_key(dt) -> str:
    return dt.strftime("%Y-%m-%d")


def _safe_time(value: Any) -> str | None:
    if not value:
        return None
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def _money(value: Any) -> float:
    if value is None:
        return 0.0
    if isinstance(value, Decimal):
        return float(value)
    return float(value)


def _int(value: Any) -> int:
    return int(value or 0)


async def collect_source_health(db: AsyncSession) -> dict[str, Any]:
    """数据源健康：源启用状态、最近入库、24h 新增、停滞源。"""
    now = utcnow()
    last_24h = now - timedelta(hours=24)

    rows = (await db.execute(
        select(
            SourceRegistry,
            func.max(RawInfo.scraped_at).label("latest_raw_at"),
            func.count(RawInfo.id).label("total_raw_infos"),
            func.sum(case((RawInfo.scraped_at >= last_24h, 1), else_=0)).label("raw_infos_24h"),
        )
        .outerjoin(RawInfo, RawInfo.source_registry_id == SourceRegistry.id)
        .group_by(SourceRegistry.id)
        .order_by(SourceRegistry.enabled.desc(), SourceRegistry.source_type.asc(), SourceRegistry.weight.desc())
    )).all()

    items = []
    enabled_total = 0
    stale_total = 0
    no_data_total = 0
    new_24h_total = 0
    type_counts: dict[str, dict[str, int]] = {}
    for source, latest_raw_at, total_raw_infos, raw_infos_24h in rows:
        raw_24h = _int(raw_infos_24h)
        total_raw = _int(total_raw_infos)
        is_enabled = bool(source.enabled)
        if is_enabled:
            enabled_total += 1
        if total_raw == 0:
            no_data_total += 1
        stale_hours = None
        if latest_raw_at:
            stale_hours = round((now - latest_raw_at).total_seconds() / 3600, 1)
        is_stale = is_enabled and (not latest_raw_at or latest_raw_at < last_24h)
        if is_stale:
            stale_total += 1
        new_24h_total += raw_24h

        bucket = type_counts.setdefault(source.source_type, {"sources": 0, "enabled": 0, "raw_infos_24h": 0})
        bucket["sources"] += 1
        bucket["enabled"] += 1 if is_enabled else 0
        bucket["raw_infos_24h"] += raw_24h

        items.append({
            "id": source.id,
            "name": source.name,
            "platform": source.platform,
            "source_type": source.source_type,
            "enabled": is_enabled,
            "auth_status": source.auth_status,
            "requires_auth": source.requires_auth,
            "weight": source.weight,
            "latest_raw_at": _iso(latest_raw_at),
            "last_fetched_at": _safe_time(source.last_fetched_at),
            "stale_hours": stale_hours,
            "raw_infos_24h": raw_24h,
            "total_raw_infos": total_raw,
            "level": "warn" if is_stale else "ok",
        })

    return {
        "generated_at": _iso(now),
        "summary": {
            "sources_total": len(rows),
            "enabled_sources": enabled_total,
            "stale_sources": stale_total,
            "no_data_sources": no_data_total,
            "raw_infos_24h": new_24h_total,
        },
        "by_type": [
            {"source_type": key, **value}
            for key, value in sorted(type_counts.items(), key=lambda item: item[0])
        ],
        "items": items,
    }


async def collect_ai_costs(db: AsyncSession) -> dict[str, Any]:
    """AI 调用成本：优先基于 LLM 调用日志，兼容旧积分交易统计。"""
    now = utcnow()
    last_24h = now - timedelta(hours=24)
    last_7d = now - timedelta(days=7)
    last_30d = now - timedelta(days=30)

    async def aggregate_since(since):
        row = (await db.execute(
            select(
                func.count(LlmCallLog.id),
                func.coalesce(func.sum(LlmCallLog.cost_yuan), 0),
                func.coalesce(func.sum(LlmCallLog.prompt_tokens), 0),
                func.coalesce(func.sum(LlmCallLog.completion_tokens), 0),
                func.coalesce(func.sum(LlmCallLog.total_tokens), 0),
                func.coalesce(func.sum(case((LlmCallLog.status == "failed", 1), else_=0)), 0),
                func.coalesce(func.avg(LlmCallLog.duration_ms), 0),
            )
            .where(LlmCallLog.created_at >= since)
        )).one()
        calls = _int(row[0])
        failures = _int(row[5])
        return {
            "calls": calls,
            "cost_yuan": round(_money(row[1]), 4),
            "credits_consumed": 0,
            "prompt_tokens": _int(row[2]),
            "completion_tokens": _int(row[3]),
            "total_tokens": _int(row[4]),
            "recorded_token_calls": calls,
            "failures": failures,
            "failure_rate": round(failures / calls, 4) if calls else 0,
            "avg_duration_ms": round(_money(row[6]), 1),
        }

    by_operation_rows = (await db.execute(
        select(
            LlmCallLog.operation,
            func.count(LlmCallLog.id).label("calls"),
            func.coalesce(func.sum(LlmCallLog.cost_yuan), 0).label("cost_yuan"),
            func.coalesce(func.sum(LlmCallLog.total_tokens), 0).label("tokens"),
            func.coalesce(func.sum(case((LlmCallLog.status == "failed", 1), else_=0)), 0).label("failures"),
        )
        .where(LlmCallLog.created_at >= last_30d)
        .group_by(LlmCallLog.operation)
        .order_by(desc("cost_yuan"), desc("calls"))
    )).all()

    by_model_rows = (await db.execute(
        select(
            LlmCallLog.provider,
            LlmCallLog.model,
            func.count(LlmCallLog.id).label("calls"),
            func.coalesce(func.sum(LlmCallLog.cost_yuan), 0).label("cost_yuan"),
            func.coalesce(func.sum(LlmCallLog.prompt_tokens), 0).label("prompt_tokens"),
            func.coalesce(func.sum(LlmCallLog.completion_tokens), 0).label("completion_tokens"),
            func.coalesce(func.sum(LlmCallLog.total_tokens), 0).label("total_tokens"),
            func.coalesce(func.sum(case((LlmCallLog.status == "failed", 1), else_=0)), 0).label("failures"),
            func.coalesce(func.avg(LlmCallLog.duration_ms), 0).label("avg_ms"),
        )
        .where(LlmCallLog.created_at >= last_30d)
        .group_by(LlmCallLog.provider, LlmCallLog.model)
        .order_by(desc("cost_yuan"), desc("calls"))
    )).all()

    recent_rows = (await db.execute(
        select(LlmCallLog)
        .order_by(LlmCallLog.created_at.desc())
        .limit(80)
    )).scalars().all()

    daily_seed = {
        _date_key(now - timedelta(days=offset)): {
            "date": _date_key(now - timedelta(days=offset)),
            "calls": 0,
            "cost_yuan": 0.0,
            "credits_consumed": 0,
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
            "recorded_token_calls": 0,
        }
        for offset in range(29, -1, -1)
    }

    daily_rows = (await db.execute(
        select(LlmCallLog)
        .where(LlmCallLog.created_at >= last_30d)
    )).scalars().all()
    for row in daily_rows:
        if not row.created_at:
            continue
        key = _date_key(row.created_at)
        item = daily_seed.setdefault(key, {
            "date": key,
            "calls": 0,
            "cost_yuan": 0.0,
            "credits_consumed": 0,
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
            "recorded_token_calls": 0,
        })
        item["calls"] += 1
        item["cost_yuan"] = round(item["cost_yuan"] + _money(row.cost_yuan), 4)
        item["prompt_tokens"] += _int(row.prompt_tokens)
        item["completion_tokens"] += _int(row.completion_tokens)
        item["total_tokens"] += _int(row.total_tokens)
        item["recorded_token_calls"] += 1

    legacy_row = (await db.execute(
        select(
            func.count(CreditTransaction.id),
            func.coalesce(func.sum(CreditTransaction.cost_yuan), 0),
            func.coalesce(func.sum(CreditTransaction.amount), 0),
        )
        .where(
            CreditTransaction.type == "consume",
            CreditTransaction.created_at >= last_30d,
        )
    )).one()

    if await ensure_default_pricing(db):
        await db.commit()
    pricing_rows = (await db.execute(
        select(LlmModelPricing).order_by(LlmModelPricing.provider.asc(), LlmModelPricing.model.asc())
    )).scalars().all()

    return {
        "generated_at": _iso(now),
        "summary": {
            "today": await aggregate_since(last_24h),
            "last_7d": await aggregate_since(last_7d),
            "last_30d": await aggregate_since(last_30d),
        },
        "by_operation": [
            {
                "operation": op or "unknown",
                "calls": _int(calls),
                "cost_yuan": round(_money(cost), 4),
                "credits_consumed": 0,
                "total_tokens": _int(tokens),
                "failures": _int(failures),
                "failure_rate": round(_int(failures) / _int(calls), 4) if _int(calls) else 0,
            }
            for op, calls, cost, tokens, failures in by_operation_rows
        ],
        "by_model": [
            {
                "provider": provider,
                "model": model,
                "calls": _int(calls),
                "cost_yuan": round(_money(cost), 4),
                "prompt_tokens": _int(prompt_tokens),
                "completion_tokens": _int(completion_tokens),
                "total_tokens": _int(total_tokens),
                "failures": _int(failures),
                "failure_rate": round(_int(failures) / _int(calls), 4) if _int(calls) else 0,
                "avg_duration_ms": round(_money(avg_ms), 1),
            }
            for provider, model, calls, cost, prompt_tokens, completion_tokens, total_tokens, failures, avg_ms in by_model_rows
        ],
        "daily": list(daily_seed.values()),
        "pricing": [
            {
                "id": row.id,
                "provider": row.provider,
                "model": row.model,
                "display_name": row.display_name,
                "input_price_per_million": _money(row.input_price_per_million),
                "output_price_per_million": _money(row.output_price_per_million),
                "currency": row.currency,
                "enabled": row.enabled,
                "note": row.note,
            }
            for row in pricing_rows
        ],
        "legacy_credit_transactions": {
            "calls": _int(legacy_row[0]),
            "cost_yuan": round(_money(legacy_row[1]), 4),
            "credits_consumed": abs(_int(legacy_row[2])),
        },
        "recent": [
            {
                "id": row.id,
                "provider": row.provider,
                "model": row.model,
                "user_id": row.user_id,
                "operation": row.operation or "unknown",
                "operation_id": row.operation_id,
                "cost_yuan": _money(row.cost_yuan),
                "token_usage": {
                    "prompt_tokens": row.prompt_tokens,
                    "completion_tokens": row.completion_tokens,
                    "total_tokens": row.total_tokens,
                },
                "status": row.status,
                "duration_ms": row.duration_ms,
                "error_message": row.error_message,
                "created_at": _iso(row.created_at),
                "description": row.finish_reason,
            }
            for row in recent_rows
        ],
    }


async def collect_api_health(db: AsyncSession) -> dict[str, Any]:
    """接口健康：500、错误率、P95、慢接口。"""
    now = utcnow()
    last_1h = now - timedelta(hours=1)
    last_24h = now - timedelta(hours=24)

    rows = (await db.execute(
        select(ApiRequestLog)
        .where(ApiRequestLog.created_at >= last_24h)
        .order_by(ApiRequestLog.created_at.desc())
        .limit(5000)
    )).scalars().all()

    def summarize(window_start):
        window = [row for row in rows if row.created_at and row.created_at >= window_start]
        durations = sorted(row.duration_ms or 0 for row in window)
        total = len(window)
        errors_5xx = sum(1 for row in window if row.status_code >= 500)
        errors_4xx = sum(1 for row in window if 400 <= row.status_code < 500)
        p95 = 0
        if durations:
            p95 = durations[min(len(durations) - 1, int(len(durations) * 0.95))]
        return {
            "requests": total,
            "errors_5xx": errors_5xx,
            "errors_4xx": errors_4xx,
            "error_rate": round(errors_5xx / total, 4) if total else 0,
            "avg_ms": round(sum(durations) / total, 1) if total else 0,
            "p95_ms": round(p95, 1),
        }

    path_stats: dict[str, dict[str, Any]] = {}
    for row in rows:
        key = f"{row.method} {row.path}"
        stat = path_stats.setdefault(key, {
            "endpoint": key,
            "requests": 0,
            "errors_5xx": 0,
            "errors_4xx": 0,
            "durations": [],
            "latest_at": None,
        })
        stat["requests"] += 1
        stat["errors_5xx"] += 1 if row.status_code >= 500 else 0
        stat["errors_4xx"] += 1 if 400 <= row.status_code < 500 else 0
        stat["durations"].append(row.duration_ms or 0)
        stat["latest_at"] = _iso(row.created_at)

    endpoints = []
    for stat in path_stats.values():
        durations = sorted(stat.pop("durations"))
        total = stat["requests"]
        p95 = durations[min(len(durations) - 1, int(len(durations) * 0.95))] if durations else 0
        endpoints.append({
            **stat,
            "avg_ms": round(sum(durations) / total, 1) if total else 0,
            "p95_ms": round(p95, 1),
            "error_rate": round(stat["errors_5xx"] / total, 4) if total else 0,
        })

    endpoints.sort(key=lambda item: (item["errors_5xx"], item["p95_ms"], item["requests"]), reverse=True)

    return {
        "generated_at": _iso(now),
        "summary": {
            "last_1h": summarize(last_1h),
            "last_24h": summarize(last_24h),
        },
        "endpoints": endpoints[:80],
        "recent_errors": [
            {
                "id": row.id,
                "method": row.method,
                "path": row.path,
                "status_code": row.status_code,
                "duration_ms": row.duration_ms,
                "user_id": row.user_id,
                "created_at": _iso(row.created_at),
            }
            for row in rows
            if row.status_code >= 500
        ][:50],
    }


async def collect_user_stats(db: AsyncSession) -> dict[str, Any]:
    """用户统计：用户增长、充值、积分消耗、AI 成本和风险用户。"""
    now = utcnow()
    last_24h = now - timedelta(hours=24)
    last_7d = now - timedelta(days=7)
    last_30d = now - timedelta(days=30)

    total_users = (await db.execute(select(func.count(User.id)))).scalar_one() or 0
    active_24h = (await db.execute(
        select(func.count(User.id)).where(User.last_login >= last_24h)
    )).scalar_one() or 0
    new_7d = (await db.execute(
        select(func.count(User.id)).where(User.created_at >= last_7d)
    )).scalar_one() or 0
    paid_users = (await db.execute(
        select(func.count(func.distinct(PaymentOrder.user_id))).where(PaymentOrder.status == "PAID")
    )).scalar_one() or 0
    low_balance_users = (await db.execute(
        select(func.count(UserCredit.id)).where(UserCredit.balance < 20)
    )).scalar_one() or 0

    async def payment_sum_since(since):
        return _money((await db.execute(
            select(func.coalesce(func.sum(PaymentOrder.amount_fen), 0)).where(
                PaymentOrder.status == "PAID",
                PaymentOrder.paid_at >= since,
            )
        )).scalar_one()) / 100

    consumed_30d = _int((await db.execute(
        select(func.coalesce(func.sum(CreditTransaction.amount), 0)).where(
            CreditTransaction.type == "consume",
            CreditTransaction.created_at >= last_30d,
        )
    )).scalar_one())
    llm_30d = (await db.execute(
        select(
            func.count(LlmCallLog.id),
            func.coalesce(func.sum(LlmCallLog.cost_yuan), 0),
            func.coalesce(func.sum(LlmCallLog.total_tokens), 0),
        ).where(LlmCallLog.created_at >= last_30d)
    )).one()

    daily_seed = {
        _date_key(now - timedelta(days=offset)): {
            "date": _date_key(now - timedelta(days=offset)),
            "new_users": 0,
            "revenue_yuan": 0.0,
            "credits_consumed": 0,
            "llm_calls": 0,
            "llm_cost_yuan": 0.0,
        }
        for offset in range(29, -1, -1)
    }

    for created_at, count in (await db.execute(
        select(func.date(User.created_at), func.count(User.id))
        .where(User.created_at >= last_30d)
        .group_by(func.date(User.created_at))
    )).all():
        key = str(created_at)
        if key in daily_seed:
            daily_seed[key]["new_users"] = _int(count)

    for paid_at, amount_fen in (await db.execute(
        select(func.date(PaymentOrder.paid_at), func.coalesce(func.sum(PaymentOrder.amount_fen), 0))
        .where(PaymentOrder.status == "PAID", PaymentOrder.paid_at >= last_30d)
        .group_by(func.date(PaymentOrder.paid_at))
    )).all():
        key = str(paid_at)
        if key in daily_seed:
            daily_seed[key]["revenue_yuan"] = round(_money(amount_fen) / 100, 2)

    for created_at, amount in (await db.execute(
        select(func.date(CreditTransaction.created_at), func.coalesce(func.sum(CreditTransaction.amount), 0))
        .where(CreditTransaction.type == "consume", CreditTransaction.created_at >= last_30d)
        .group_by(func.date(CreditTransaction.created_at))
    )).all():
        key = str(created_at)
        if key in daily_seed:
            daily_seed[key]["credits_consumed"] = abs(_int(amount))

    for created_at, calls, cost in (await db.execute(
        select(
            func.date(LlmCallLog.created_at),
            func.count(LlmCallLog.id),
            func.coalesce(func.sum(LlmCallLog.cost_yuan), 0),
        )
        .where(LlmCallLog.created_at >= last_30d)
        .group_by(func.date(LlmCallLog.created_at))
    )).all():
        key = str(created_at)
        if key in daily_seed:
            daily_seed[key]["llm_calls"] = _int(calls)
            daily_seed[key]["llm_cost_yuan"] = round(_money(cost), 4)

    user_rows = (await db.execute(
        select(
            User,
            UserCredit.balance,
            UserCredit.total_purchased,
            UserCredit.total_consumed,
            func.coalesce(func.sum(case((PaymentOrder.status == "PAID", PaymentOrder.amount_fen), else_=0)), 0).label("paid_fen_30d"),
        )
        .outerjoin(UserCredit, UserCredit.user_id == User.id)
        .outerjoin(
            PaymentOrder,
            (PaymentOrder.user_id == User.id) & (PaymentOrder.paid_at >= last_30d),
        )
        .group_by(User.id, UserCredit.balance, UserCredit.total_purchased, UserCredit.total_consumed)
    )).all()

    consumed_rows = (await db.execute(
        select(CreditTransaction.user_id, func.coalesce(func.sum(CreditTransaction.amount), 0))
        .where(CreditTransaction.type == "consume", CreditTransaction.created_at >= last_30d)
        .group_by(CreditTransaction.user_id)
    )).all()
    consumed_by_user = {uid: abs(_int(amount)) for uid, amount in consumed_rows}

    llm_rows = (await db.execute(
        select(
            LlmCallLog.user_id,
            func.count(LlmCallLog.id),
            func.coalesce(func.sum(LlmCallLog.cost_yuan), 0),
            func.coalesce(func.sum(LlmCallLog.total_tokens), 0),
        )
        .where(LlmCallLog.created_at >= last_30d, LlmCallLog.user_id.is_not(None))
        .group_by(LlmCallLog.user_id)
    )).all()
    llm_by_user = {
        uid: {"calls": _int(calls), "cost_yuan": round(_money(cost), 4), "total_tokens": _int(tokens)}
        for uid, calls, cost, tokens in llm_rows
    }

    items = []
    for user, balance, total_purchased, total_consumed, paid_fen_30d in user_rows:
        llm = llm_by_user.get(user.id, {"calls": 0, "cost_yuan": 0.0, "total_tokens": 0})
        item = {
            "id": user.id,
            "username": user.username,
            "phone": user.phone,
            "role": user.role,
            "is_active": user.is_active,
            "balance": _int(balance),
            "total_purchased": _int(total_purchased),
            "total_consumed": _int(total_consumed),
            "paid_yuan_30d": round(_money(paid_fen_30d) / 100, 2),
            "credits_consumed_30d": consumed_by_user.get(user.id, 0),
            "llm_calls_30d": llm["calls"],
            "llm_cost_yuan_30d": llm["cost_yuan"],
            "llm_tokens_30d": llm["total_tokens"],
            "created_at": _iso(user.created_at),
            "last_login": _iso(user.last_login),
        }
        item["risk_flags"] = []
        if balance is not None and item["balance"] < 20:
            item["risk_flags"].append("low_balance")
        if item["llm_cost_yuan_30d"] >= 10 and item["paid_yuan_30d"] <= 0:
            item["risk_flags"].append("high_cost_no_payment")
        items.append(item)

    top_cost_users = sorted(items, key=lambda x: (x["llm_cost_yuan_30d"], x["credits_consumed_30d"]), reverse=True)[:30]
    low_balance_list = sorted(
        [item for item in items if "low_balance" in item["risk_flags"]],
        key=lambda x: (x["balance"], -x["credits_consumed_30d"]),
    )[:50]

    recent_payments = (await db.execute(
        select(PaymentOrder, User.username, User.phone)
        .join(User, User.id == PaymentOrder.user_id)
        .order_by(PaymentOrder.created_at.desc())
        .limit(50)
    )).all()

    return {
        "generated_at": _iso(now),
        "summary": {
            "total_users": _int(total_users),
            "active_users_24h": _int(active_24h),
            "new_users_7d": _int(new_7d),
            "paid_users": _int(paid_users),
            "low_balance_users": _int(low_balance_users),
            "revenue_24h": round(await payment_sum_since(last_24h), 2),
            "revenue_7d": round(await payment_sum_since(last_7d), 2),
            "revenue_30d": round(await payment_sum_since(last_30d), 2),
            "credits_consumed_30d": abs(consumed_30d),
            "llm_calls_30d": _int(llm_30d[0]),
            "llm_cost_yuan_30d": round(_money(llm_30d[1]), 4),
            "llm_tokens_30d": _int(llm_30d[2]),
        },
        "daily": list(daily_seed.values()),
        "top_cost_users": top_cost_users,
        "low_balance_users": low_balance_list,
        "recent_payments": [
            {
                "id": order.id,
                "user_id": order.user_id,
                "username": username,
                "phone": phone,
                "package_name": order.package_name,
                "amount_yuan": order.amount_yuan,
                "credits": order.credits,
                "status": order.status,
                "created_at": _iso(order.created_at),
                "paid_at": _iso(order.paid_at),
            }
            for order, username, phone in recent_payments
        ],
    }
