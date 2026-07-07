import time

import pytest

from app.core.config import settings
from app.core.refresh_tokens import (
    _memory_tokens,
    is_refresh_token_active,
    register_refresh_token,
    revoke_refresh_token,
    revoke_user_refresh_tokens,
)
from app.core.security import create_refresh_token, decode_token


class FakeRedis:
    def __init__(self):
        self.values = {}
        self.sets = {}
        self.expirations = {}
        self.closed = False

    async def setex(self, key, ttl, value):
        self.values[key] = value
        self.expirations[key] = ttl

    async def get(self, key):
        return self.values.get(key)

    async def delete(self, *keys):
        for key in keys:
            self.values.pop(key, None)
            self.sets.pop(key, None)

    async def sadd(self, key, value):
        self.sets.setdefault(key, set()).add(value)

    async def expire(self, key, ttl):
        self.expirations[key] = ttl

    async def smembers(self, key):
        return self.sets.get(key, set())

    async def aclose(self):
        self.closed = True


def test_refresh_token_contains_jti():
    token = create_refresh_token(subject=123)
    payload = decode_token(token)

    assert payload["type"] == "refresh"
    assert payload["sub"] == "123"
    assert payload["jti"]


@pytest.mark.asyncio
async def test_register_validate_and_revoke_refresh_token(monkeypatch):
    fake = FakeRedis()
    monkeypatch.setattr("app.core.refresh_tokens._get_redis", lambda: fake)
    exp = int(time.time()) + 300

    await register_refresh_token("jti-1", 123, exp)

    assert await is_refresh_token_active("jti-1", 123) is True
    assert await is_refresh_token_active("jti-1", 456) is False

    await revoke_refresh_token("jti-1")

    assert await is_refresh_token_active("jti-1", 123) is False


@pytest.mark.asyncio
async def test_revoke_user_refresh_tokens(monkeypatch):
    fake = FakeRedis()
    monkeypatch.setattr("app.core.refresh_tokens._get_redis", lambda: fake)
    exp = int(time.time()) + 300

    await register_refresh_token("jti-1", 123, exp)
    await register_refresh_token("jti-2", 123, exp)
    await register_refresh_token("jti-3", 456, exp)
    await revoke_user_refresh_tokens(123)

    assert await is_refresh_token_active("jti-1", 123) is False
    assert await is_refresh_token_active("jti-2", 123) is False
    assert await is_refresh_token_active("jti-3", 456) is True


@pytest.mark.asyncio
async def test_refresh_token_store_memory_fallback_in_development(monkeypatch):
    class BrokenRedis:
        async def setex(self, *args, **kwargs):
            raise ConnectionError("redis down")

        async def get(self, *args, **kwargs):
            raise ConnectionError("redis down")

        async def delete(self, *args, **kwargs):
            raise ConnectionError("redis down")

        async def aclose(self):
            return None

    monkeypatch.setattr(settings, "ENVIRONMENT", "development")
    monkeypatch.setattr("app.core.refresh_tokens._get_redis", lambda: BrokenRedis())
    _memory_tokens.clear()
    exp = int(time.time()) + 300

    await register_refresh_token("jti-dev", 123, exp)

    assert await is_refresh_token_active("jti-dev", 123) is True
    await revoke_refresh_token("jti-dev")
    assert await is_refresh_token_active("jti-dev", 123) is False
