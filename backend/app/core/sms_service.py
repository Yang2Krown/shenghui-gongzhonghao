import random
import logging
import asyncio
import time
from typing import Dict, Tuple

import redis.asyncio as aioredis

from app.core.config import settings

logger = logging.getLogger(__name__)

# Redis key 前缀
_CODE_PREFIX = "sms:code:"
_COOLDOWN_PREFIX = "sms:cooldown:"

CODE_TTL = 300       # 验证码有效期 5 分钟
COOLDOWN_TTL = 60    # 发送冷却 60 秒

_memory_codes: Dict[str, Tuple[str, float]] = {}
_memory_cooldowns: Dict[str, float] = {}


def _get_redis() -> aioredis.Redis:
    password = settings.REDIS_PASSWORD or None
    return aioredis.Redis(
        host=settings.REDIS_HOST,
        port=settings.REDIS_PORT,
        password=password,
        db=settings.REDIS_DB,
        decode_responses=True,
        socket_connect_timeout=settings.REDIS_CONNECT_TIMEOUT_SECONDS,
        socket_timeout=settings.REDIS_SOCKET_TIMEOUT_SECONDS,
    )


def _generate_code() -> str:
    return str(random.randint(100000, 999999))


def _bypass_phones() -> set:
    """短信白名单手机号集合（应急保底登录用，通过 SMS_BYPASS_PHONES 配置）。"""
    raw = settings.SMS_BYPASS_PHONES or ""
    return {p.strip() for p in raw.split(",") if p.strip()}


def _is_bypass(phone: str) -> bool:
    return phone in _bypass_phones()


async def send_sms_code(phone: str) -> dict:
    """发送短信验证码，返回 {"ok": bool, "message": str}"""
    # 白名单手机号：不调阿里云，直接放行（短信通道故障时的保底登录）。
    if _is_bypass(phone):
        logger.warning("短信白名单命中，跳过阿里云直接放行 phone=%s", phone)
        return {"ok": True, "message": "验证码已发送"}

    r = _get_redis()
    code = None
    try:
        # 冷却检查
        if await r.exists(f"{_COOLDOWN_PREFIX}{phone}"):
            ttl = await r.ttl(f"{_COOLDOWN_PREFIX}{phone}")
            return {"ok": False, "message": f"发送太频繁，请 {ttl} 秒后再试"}

        code = _generate_code()

        # 调用阿里云短信
        ok = await _call_aliyun_sms(phone, code)
        if not ok:
            return {"ok": False, "message": "短信发送失败，请稍后重试"}

        # 存储验证码和冷却标记
        await r.setex(f"{_CODE_PREFIX}{phone}", CODE_TTL, code)
        await r.setex(f"{_COOLDOWN_PREFIX}{phone}", COOLDOWN_TTL, "1")

        return {"ok": True, "message": "验证码已发送"}
    except Exception as e:
        if settings.is_production:
            logger.error("短信 Redis 不可用，生产环境拒绝发送验证码: %s", e)
            return {"ok": False, "message": "验证码服务暂不可用，请稍后重试"}
        logger.warning("短信 Redis 不可用，开发环境使用内存验证码存储: %s", e)
        if code is not None:
            _store_memory_code(phone, code)
            return {"ok": True, "message": "验证码已发送"}
        return await _send_sms_code_memory(phone)
    finally:
        await r.aclose()


async def verify_sms_code(phone: str, code: str) -> bool:
    """校验验证码，通过后删除"""
    # 白名单手机号：只认固定验证码，不依赖 Redis / 阿里云。
    if _is_bypass(phone):
        return code == (settings.SMS_BYPASS_CODE or "")

    r = _get_redis()
    try:
        stored = await r.get(f"{_CODE_PREFIX}{phone}")
        if stored and stored == code:
            await r.delete(f"{_CODE_PREFIX}{phone}")
            return True
        return False
    except Exception as e:
        if settings.is_production:
            logger.error("短信 Redis 不可用，生产环境验证码校验失败: %s", e)
            return False
        logger.warning("短信 Redis 不可用，开发环境使用内存验证码校验: %s", e)
        return _verify_memory_code(phone, code)
    finally:
        await r.aclose()


async def _send_sms_code_memory(phone: str) -> dict:
    _cleanup_memory_codes()
    cooldown_until = _memory_cooldowns.get(phone, 0)
    now = time.time()
    if cooldown_until > now:
        ttl = max(1, int(cooldown_until - now))
        return {"ok": False, "message": f"发送太频繁，请 {ttl} 秒后再试"}

    code = _generate_code()
    ok = await _call_aliyun_sms(phone, code)
    if not ok:
        return {"ok": False, "message": "短信发送失败，请稍后重试"}
    _store_memory_code(phone, code)
    return {"ok": True, "message": "验证码已发送"}


def _store_memory_code(phone: str, code: str) -> None:
    now = time.time()
    _memory_codes[phone] = (code, now + CODE_TTL)
    _memory_cooldowns[phone] = now + COOLDOWN_TTL


def _verify_memory_code(phone: str, code: str) -> bool:
    _cleanup_memory_codes()
    stored = _memory_codes.get(phone)
    if not stored:
        return False
    stored_code, expires_at = stored
    if expires_at <= time.time() or stored_code != code:
        return False
    _memory_codes.pop(phone, None)
    return True


def _cleanup_memory_codes() -> None:
    now = time.time()
    for phone, (_, expires_at) in list(_memory_codes.items()):
        if expires_at <= now:
            _memory_codes.pop(phone, None)
    for phone, expires_at in list(_memory_cooldowns.items()):
        if expires_at <= now:
            _memory_cooldowns.pop(phone, None)


async def _call_aliyun_sms(phone: str, code: str) -> bool:
    try:
        return await asyncio.wait_for(
            asyncio.to_thread(_call_aliyun_sms_sync, phone, code),
            timeout=settings.SMS_SEND_TIMEOUT_SECONDS,
        )
    except asyncio.TimeoutError:
        logger.error("阿里云短信发送超时 phone=%s timeout=%ss", phone, settings.SMS_SEND_TIMEOUT_SECONDS)
        return False


def _call_aliyun_sms_sync(phone: str, code: str) -> bool:
    try:
        from alibabacloud_dysmsapi20170525.client import Client
        from alibabacloud_tea_openapi import models as open_api_models
        from alibabacloud_dysmsapi20170525 import models as sms_models
        from alibabacloud_tea_util import models as util_models
        import json

        config = open_api_models.Config(
            access_key_id=settings.ALIYUN_SMS_ACCESS_KEY_ID,
            access_key_secret=settings.ALIYUN_SMS_ACCESS_KEY_SECRET,
        )
        config.endpoint = "dysmsapi.aliyuncs.com"
        client = Client(config)

        request = sms_models.SendSmsRequest(
            phone_numbers=phone,
            sign_name=settings.ALIYUN_SMS_SIGN_NAME,
            template_code=settings.ALIYUN_SMS_TEMPLATE_CODE,
            template_param=json.dumps({"code": code}),
        )
        timeout_ms = int(settings.SMS_SEND_TIMEOUT_SECONDS * 1000)
        runtime = util_models.RuntimeOptions(
            connect_timeout=timeout_ms,
            read_timeout=timeout_ms,
        )
        response = client.send_sms_with_options(request, runtime)
        if response.body.code == "OK":
            return True
        logger.error(f"阿里云短信失败: {response.body.code} {response.body.message}")
        return False
    except Exception as e:
        logger.error(f"阿里云短信异常: {e}")
        return False
