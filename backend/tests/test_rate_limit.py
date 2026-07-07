import pytest
from fastapi import HTTPException

from app.core.rate_limit import RateLimitRule, enforce_rate_limit, parse_rate


class FakeRedis:
    def __init__(self):
        self.values = {}
        self.ttls = {}
        self.closed = False

    async def incr(self, key):
        self.values[key] = self.values.get(key, 0) + 1
        return self.values[key]

    async def expire(self, key, ttl):
        self.ttls[key] = ttl

    async def ttl(self, key):
        return self.ttls.get(key, 60)

    async def aclose(self):
        self.closed = True


def test_parse_rate():
    assert parse_rate("10/60") == (10, 60)


@pytest.mark.asyncio
async def test_enforce_rate_limit_allows_within_limit(monkeypatch):
    fake = FakeRedis()
    monkeypatch.setattr("app.core.rate_limit._get_redis", lambda: fake)

    await enforce_rate_limit([RateLimitRule("test", 2, 60, "user:1")])
    await enforce_rate_limit([RateLimitRule("test", 2, 60, "user:1")])

    assert fake.closed is True


@pytest.mark.asyncio
async def test_enforce_rate_limit_blocks_over_limit(monkeypatch):
    fake = FakeRedis()
    monkeypatch.setattr("app.core.rate_limit._get_redis", lambda: fake)

    await enforce_rate_limit([RateLimitRule("test", 1, 60, "user:1")])

    with pytest.raises(HTTPException) as exc:
        await enforce_rate_limit([RateLimitRule("test", 1, 60, "user:1")])

    assert exc.value.status_code == 429
    assert exc.value.headers["Retry-After"] == "65"
