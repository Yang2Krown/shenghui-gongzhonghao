import time

import pytest

from app.core.config import settings
from app.core import sms_service
from app.core.sms_service import _call_aliyun_sms, send_sms_code, verify_sms_code


@pytest.mark.asyncio
async def test_call_aliyun_sms_times_out(monkeypatch):
    monkeypatch.setattr(settings, "SMS_SEND_TIMEOUT_SECONDS", 0.01)

    def slow_send(phone: str, code: str) -> bool:
        time.sleep(0.05)
        return True

    monkeypatch.setattr("app.core.sms_service._call_aliyun_sms_sync", slow_send)

    assert await _call_aliyun_sms("13800138000", "123456") is False


@pytest.mark.asyncio
async def test_send_and_verify_sms_code_uses_memory_fallback_in_development(monkeypatch):
    class BrokenRedis:
        async def exists(self, key):
            raise ConnectionError("redis down")

        async def get(self, key):
            raise ConnectionError("redis down")

        async def aclose(self):
            return None

    monkeypatch.setattr(settings, "ENVIRONMENT", "development")
    monkeypatch.setattr("app.core.sms_service._get_redis", lambda: BrokenRedis())
    monkeypatch.setattr("app.core.sms_service._call_aliyun_sms", lambda phone, code: _async_true())
    monkeypatch.setattr("app.core.sms_service._generate_code", lambda: "654321")
    sms_service._memory_codes.clear()
    sms_service._memory_cooldowns.clear()

    result = await send_sms_code("13800138000")

    assert result == {"ok": True, "message": "验证码已发送"}
    assert await verify_sms_code("13800138000", "654321") is True
    assert await verify_sms_code("13800138000", "654321") is False


@pytest.mark.asyncio
async def test_send_sms_code_rejects_when_redis_down_in_production(monkeypatch):
    class BrokenRedis:
        async def exists(self, key):
            raise ConnectionError("redis down")

        async def aclose(self):
            return None

    monkeypatch.setattr(settings, "ENVIRONMENT", "production")
    monkeypatch.setattr("app.core.sms_service._get_redis", lambda: BrokenRedis())

    result = await send_sms_code("13800138000")

    assert result["ok"] is False
    assert "暂不可用" in result["message"]


async def _async_true():
    return True
