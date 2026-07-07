"""Redis-backed fixed-window rate limiting helpers."""

import hashlib
import logging
import time
from dataclasses import dataclass
from typing import Iterable, Optional

import redis.asyncio as aioredis
from fastapi import Depends, HTTPException, Request, status

from app.core.config import settings
from app.core.security import get_current_user
from app.models.user import User

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RateLimitRule:
    scope: str
    limit: int
    window_seconds: int
    actor: str


def parse_rate(value: str) -> tuple[int, int]:
    """Parse a rate string in the form '<limit>/<seconds>'."""
    try:
        limit_text, window_text = value.split("/", 1)
        limit = int(limit_text)
        window = int(window_text)
    except (AttributeError, ValueError) as exc:
        raise ValueError(f"无效限流配置: {value!r}") from exc
    if limit <= 0 or window <= 0:
        raise ValueError(f"限流配置必须为正数: {value!r}")
    return limit, window


def client_ip(request: Request) -> str:
    """Return the best-effort real client IP behind a reverse proxy."""
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        return forwarded_for.split(",", 1)[0].strip() or "unknown"
    real_ip = request.headers.get("x-real-ip")
    if real_ip:
        return real_ip.strip()
    if request.client and request.client.host:
        return request.client.host
    return "unknown"


def normalize_actor(value: object) -> str:
    text = str(value or "anonymous").strip().lower()
    return text or "anonymous"


def user_actor(user_id: object) -> str:
    return f"user:{normalize_actor(user_id)}"


def ip_actor(request: Request) -> str:
    return f"ip:{normalize_actor(client_ip(request))}"


def account_actor(value: object) -> str:
    digest = hashlib.sha256(normalize_actor(value).encode("utf-8")).hexdigest()[:24]
    return f"account:{digest}"


def phone_actor(value: object) -> str:
    digest = hashlib.sha256(normalize_actor(value).encode("utf-8")).hexdigest()[:24]
    return f"phone:{digest}"


async def enforce_rate_limit(
    rules: Iterable[RateLimitRule],
    request: Optional[Request] = None,
) -> None:
    if not settings.RATE_LIMIT_ENABLED:
        return

    redis_client = _get_redis()
    try:
        for rule in rules:
            await _check_one(redis_client, rule, request=request)
    except HTTPException:
        raise
    except Exception as exc:
        if settings.rate_limit_fail_open:
            logger.warning("限流 Redis 不可用，按配置放行: %s", exc)
            return
        logger.error("限流 Redis 不可用，生产保护拒绝请求: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="限流服务暂不可用，请稍后重试",
        ) from exc
    finally:
        await redis_client.aclose()


async def limit_ai_generation(
    request: Request,
    current_user: User = Depends(get_current_user),
) -> User:
    await enforce_rate_limit(
        [rule_from_setting("ai:generation:user", settings.RATE_LIMIT_AI_GENERATION_USER, user_actor(current_user.id))],
        request=request,
    )
    return current_user


async def limit_file_upload(
    request: Request,
    current_user: User = Depends(get_current_user),
) -> User:
    await enforce_rate_limit(
        [rule_from_setting("file:upload:user", settings.RATE_LIMIT_FILE_UPLOAD_USER, user_actor(current_user.id))],
        request=request,
    )
    return current_user


async def limit_link_extract(
    request: Request,
    current_user: User = Depends(get_current_user),
) -> User:
    await enforce_rate_limit(
        [rule_from_setting("link:extract:user", settings.RATE_LIMIT_LINK_EXTRACT_USER, user_actor(current_user.id))],
        request=request,
    )
    return current_user


async def limit_payment_order(
    request: Request,
    current_user: User = Depends(get_current_user),
) -> User:
    await enforce_rate_limit(
        [rule_from_setting("payment:order:user", settings.RATE_LIMIT_PAYMENT_ORDER_USER, user_actor(current_user.id))],
        request=request,
    )
    return current_user


def rule_from_setting(scope: str, setting_value: str, actor: str) -> RateLimitRule:
    limit, window = parse_rate(setting_value)
    return RateLimitRule(scope=scope, limit=limit, window_seconds=window, actor=actor)


async def _check_one(
    redis_client: aioredis.Redis,
    rule: RateLimitRule,
    request: Optional[Request] = None,
) -> None:
    now = int(time.time())
    bucket = now // rule.window_seconds
    key = f"rate:{rule.scope}:{rule.actor}:{bucket}"
    count = await redis_client.incr(key)
    if count == 1:
        await redis_client.expire(key, rule.window_seconds + 5)

    ttl = await redis_client.ttl(key)
    reset_seconds = ttl if ttl and ttl > 0 else rule.window_seconds
    if count > rule.limit:
        if request is not None:
            logger.warning(
                "请求被限流 scope=%s actor=%s path=%s",
                rule.scope,
                rule.actor,
                request.url.path,
            )
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"请求过于频繁，请 {reset_seconds} 秒后再试",
            headers={"Retry-After": str(reset_seconds)},
        )


def _get_redis() -> aioredis.Redis:
    return aioredis.Redis(
        host=settings.REDIS_HOST,
        port=settings.REDIS_PORT,
        password=settings.REDIS_PASSWORD or None,
        db=settings.REDIS_DB,
        decode_responses=True,
    )
