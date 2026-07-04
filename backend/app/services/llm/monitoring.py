"""LLM 调用成本记录与模型单价。"""

from __future__ import annotations

import inspect
import logging
from decimal import Decimal
from typing import Any, Optional

from sqlalchemy import select

from app.db.session import AsyncSessionLocal
from app.models.llm_monitoring import LlmCallLog, LlmModelPricing

logger = logging.getLogger(__name__)


DEFAULT_PRICING = {
    ("deepseek", "deepseek-v4-flash"): ("DeepSeek V4 Flash", Decimal("2"), Decimal("8")),
    ("moonshot", "moonshot-v1-32k"): ("Moonshot v1 32k", Decimal("12"), Decimal("12")),
    ("anthropic", "claude-sonnet-4-6"): ("Claude Sonnet 4.6", Decimal("21"), Decimal("105")),
    ("aigocode", "claude-opus-4-8-r"): ("AIGoCode Claude Opus", Decimal("105"), Decimal("525")),
}


def infer_operation() -> str:
    """从调用栈粗略推断业务功能，减少到处手填 operation。"""
    for frame in inspect.stack()[2:14]:
        filename = frame.filename.replace("\\", "/")
        if "/services/title_generation/" in filename or "/api/v1/title_generation.py" in filename:
            return "title_generation"
        if "/services/content_generation/" in filename or "/api/v1/content_generation.py" in filename:
            return "content_generation"
        if "/services/outline_generation/" in filename:
            return "outline_generation"
        if "/services/topic_mining/" in filename:
            return "topic_mining"
        if "/services/content_polish" in filename or "/api/v1/content_polish.py" in filename:
            return "content_polish"
        if "/api/v1/content_continuation.py" in filename:
            return "content_continuation"
        if "/services/preprocess/" in filename:
            return "preprocess"
        if "/services/commercial" in filename:
            return "commercial_detection"
        if "/services/feishu/" in filename:
            return "feishu_brief"
    return "unknown"


async def get_or_create_pricing(db, provider: str, model: str) -> LlmModelPricing:
    pricing = (await db.execute(
        select(LlmModelPricing).where(
            LlmModelPricing.provider == provider,
            LlmModelPricing.model == model,
        )
    )).scalar_one_or_none()
    if pricing:
        return pricing

    display_name, input_price, output_price = DEFAULT_PRICING.get(
        (provider, model),
        (f"{provider} {model}", Decimal("0"), Decimal("0")),
    )
    pricing = LlmModelPricing(
        provider=provider,
        model=model,
        display_name=display_name,
        input_price_per_million=input_price,
        output_price_per_million=output_price,
        currency="CNY",
        enabled=True,
        note="自动发现模型，请在后台确认单价",
    )
    db.add(pricing)
    await db.flush()
    return pricing


async def ensure_default_pricing(db) -> bool:
    """补齐默认模型单价，兼容 create_all 先建表但 migration seed 没跑的环境。"""
    changed = False
    for (provider, model), (display_name, input_price, output_price) in DEFAULT_PRICING.items():
        exists = (await db.execute(
            select(LlmModelPricing.id).where(
                LlmModelPricing.provider == provider,
                LlmModelPricing.model == model,
            )
        )).scalar_one_or_none()
        if exists:
            continue
        db.add(LlmModelPricing(
            provider=provider,
            model=model,
            display_name=display_name,
            input_price_per_million=input_price,
            output_price_per_million=output_price,
            currency="CNY",
            enabled=True,
            note="默认估算价，可在后台调整",
        ))
        changed = True
    if changed:
        await db.flush()
    return changed


def calculate_cost_yuan(usage: Optional[dict], pricing: LlmModelPricing) -> Decimal:
    usage = usage or {}
    prompt_tokens = Decimal(str(usage.get("prompt_tokens") or 0))
    completion_tokens = Decimal(str(usage.get("completion_tokens") or 0))
    input_price = Decimal(str(pricing.input_price_per_million or 0))
    output_price = Decimal(str(pricing.output_price_per_million or 0))
    return (prompt_tokens * input_price + completion_tokens * output_price) / Decimal("1000000")


async def record_llm_call(
    *,
    provider: str,
    model: str,
    usage: Optional[dict] = None,
    duration_ms: float = 0,
    status: str = "success",
    finish_reason: Optional[str] = None,
    error_message: Optional[str] = None,
    operation: Optional[str] = None,
    operation_id: Optional[str] = None,
    user_id: Optional[int] = None,
    metadata: Optional[dict[str, Any]] = None,
) -> None:
    """记录一次 LLM 调用。失败不影响主业务。"""
    try:
        usage = usage or {}
        async with AsyncSessionLocal() as db:
            pricing = await get_or_create_pricing(db, provider, model)
            cost_yuan = calculate_cost_yuan(usage, pricing)
            db.add(LlmCallLog(
                provider=provider,
                model=model,
                operation=operation or infer_operation(),
                operation_id=operation_id,
                user_id=user_id,
                status=status,
                prompt_tokens=int(usage.get("prompt_tokens") or 0),
                completion_tokens=int(usage.get("completion_tokens") or 0),
                total_tokens=int(usage.get("total_tokens") or 0),
                cost_yuan=cost_yuan,
                duration_ms=round(duration_ms, 2),
                finish_reason=finish_reason,
                error_message=(error_message or "")[:2000] or None,
                pricing_snapshot={
                    "input_price_per_million": float(pricing.input_price_per_million or 0),
                    "output_price_per_million": float(pricing.output_price_per_million or 0),
                    "currency": pricing.currency,
                },
                metadata_json=metadata or {},
            ))
            await db.commit()
    except Exception as exc:
        logger.warning("记录 LLM 调用成本失败: %s", exc)
