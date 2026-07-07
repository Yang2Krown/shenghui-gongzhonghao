"""Refresh token registration, validation, and revocation."""
import time
from datetime import datetime
from typing import Dict, Tuple

import redis.asyncio as aioredis

from app.core.config import settings


class RefreshTokenStoreUnavailable(RuntimeError):
    pass


_PREFIX = "auth:refresh:"
_USER_PREFIX = "auth:refresh:user:"
_memory_tokens: Dict[str, Tuple[str, float]] = {}


def _get_redis() -> aioredis.Redis:
    return aioredis.Redis(
        host=settings.REDIS_HOST,
        port=settings.REDIS_PORT,
        password=settings.REDIS_PASSWORD or None,
        db=settings.REDIS_DB,
        decode_responses=True,
        socket_connect_timeout=settings.REDIS_CONNECT_TIMEOUT_SECONDS,
        socket_timeout=settings.REDIS_SOCKET_TIMEOUT_SECONDS,
    )


def _ttl_from_exp(exp) -> int:
    if isinstance(exp, datetime):
        expires_at = exp.timestamp()
    else:
        expires_at = float(exp)
    return max(0, int(expires_at - time.time()))


def _cleanup_memory_tokens() -> None:
    now = time.time()
    for jti, (_, expires_at) in list(_memory_tokens.items()):
        if expires_at <= now:
            _memory_tokens.pop(jti, None)


async def register_refresh_token(jti: str, user_id: object, exp) -> None:
    ttl = _ttl_from_exp(exp)
    if not jti or ttl <= 0:
        raise ValueError("刷新令牌已过期或缺少 jti")

    redis_client = _get_redis()
    try:
        await redis_client.setex(f"{_PREFIX}{jti}", ttl, str(user_id))
        await redis_client.sadd(f"{_USER_PREFIX}{user_id}", jti)
        await redis_client.expire(f"{_USER_PREFIX}{user_id}", ttl)
    except Exception as exc:
        if settings.is_production:
            raise RefreshTokenStoreUnavailable("刷新令牌存储暂不可用") from exc
        _cleanup_memory_tokens()
        _memory_tokens[jti] = (str(user_id), time.time() + ttl)
    finally:
        await redis_client.aclose()


async def is_refresh_token_active(jti: str, user_id: object) -> bool:
    if not jti:
        return False

    redis_client = _get_redis()
    try:
        stored_user_id = await redis_client.get(f"{_PREFIX}{jti}")
        return stored_user_id == str(user_id)
    except Exception as exc:
        if settings.is_production:
            raise RefreshTokenStoreUnavailable("刷新令牌存储暂不可用") from exc
        _cleanup_memory_tokens()
        stored = _memory_tokens.get(jti)
        return bool(stored and stored[0] == str(user_id))
    finally:
        await redis_client.aclose()


async def revoke_refresh_token(jti: str) -> None:
    if not jti:
        return

    redis_client = _get_redis()
    try:
        await redis_client.delete(f"{_PREFIX}{jti}")
    except Exception as exc:
        if settings.is_production:
            raise RefreshTokenStoreUnavailable("刷新令牌存储暂不可用") from exc
        _memory_tokens.pop(jti, None)
    finally:
        await redis_client.aclose()


async def revoke_user_refresh_tokens(user_id: object) -> None:
    redis_client = _get_redis()
    user_key = f"{_USER_PREFIX}{user_id}"
    try:
        jtis = await redis_client.smembers(user_key)
        if jtis:
            await redis_client.delete(*(f"{_PREFIX}{jti}" for jti in jtis))
        await redis_client.delete(user_key)
    except Exception as exc:
        if settings.is_production:
            raise RefreshTokenStoreUnavailable("刷新令牌存储暂不可用") from exc
        for jti, (stored_user_id, _) in list(_memory_tokens.items()):
            if stored_user_id == str(user_id):
                _memory_tokens.pop(jti, None)
    finally:
        await redis_client.aclose()
