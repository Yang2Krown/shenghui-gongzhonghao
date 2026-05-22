import random
import logging
from typing import Optional

import redis.asyncio as aioredis

from app.core.config import settings

logger = logging.getLogger(__name__)

# Redis key 前缀
_CODE_PREFIX = "sms:code:"
_COOLDOWN_PREFIX = "sms:cooldown:"

CODE_TTL = 300       # 验证码有效期 5 分钟
COOLDOWN_TTL = 60    # 发送冷却 60 秒


def _get_redis() -> aioredis.Redis:
    password = settings.REDIS_PASSWORD or None
    return aioredis.Redis(
        host=settings.REDIS_HOST,
        port=settings.REDIS_PORT,
        password=password,
        db=settings.REDIS_DB,
        decode_responses=True,
    )


def _generate_code() -> str:
    return str(random.randint(100000, 999999))


async def send_sms_code(phone: str) -> dict:
    """发送短信验证码，返回 {"ok": bool, "message": str}"""
    r = _get_redis()
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
    finally:
        await r.aclose()


async def verify_sms_code(phone: str, code: str) -> bool:
    """校验验证码，通过后删除"""
    r = _get_redis()
    try:
        stored = await r.get(f"{_CODE_PREFIX}{phone}")
        if stored and stored == code:
            await r.delete(f"{_CODE_PREFIX}{phone}")
            return True
        return False
    finally:
        await r.aclose()


async def _call_aliyun_sms(phone: str, code: str) -> bool:
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
        runtime = util_models.RuntimeOptions()
        response = client.send_sms_with_options(request, runtime)
        if response.body.code == "OK":
            return True
        logger.error(f"阿里云短信失败: {response.body.code} {response.body.message}")
        return False
    except Exception as e:
        logger.error(f"阿里云短信异常: {e}")
        return False
