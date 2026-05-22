"""LLM 调用 retry 工具：可重试错误识别 + 指数退避。

对齐设计文档 v2.0 第 4.2 节："API 调用失败 → 重试最多 3 次"。
"""

import asyncio
import logging
from typing import Any, Awaitable, Callable, Tuple, Type

logger = logging.getLogger(__name__)


# 这些异常视为"可重试"——通常是临时性问题
def _retryable_errors() -> Tuple[Type[BaseException], ...]:
    """返回可重试的异常类型元组。延迟 import 避免依赖问题。"""
    errors: list = [
        asyncio.TimeoutError,
        ConnectionError,
        TimeoutError,
    ]
    # openai
    try:
        from openai import APIError, APITimeoutError, RateLimitError, APIConnectionError
        errors.extend([APIError, APITimeoutError, RateLimitError, APIConnectionError])
    except ImportError:
        pass
    # anthropic
    try:
        from anthropic import APIError as AnthropicAPIError
        errors.append(AnthropicAPIError)
    except ImportError:
        pass
    # httpx
    try:
        import httpx
        errors.extend([httpx.HTTPError, httpx.TimeoutException, httpx.NetworkError])
    except ImportError:
        pass
    return tuple(errors)


async def with_retry(
    func: Callable[[], Awaitable[Any]],
    *,
    max_attempts: int = 3,
    base_delay: float = 1.5,
    description: str = "LLM call",
) -> Any:
    """对一个 async 调用做指数退避重试。

    Args:
        func: 无参数的 async 函数（用 lambda 或 partial 包装）
        max_attempts: 最多尝试次数（含首次）
        base_delay: 首次失败后等待秒数；后续 base_delay * 2^attempt
        description: 日志里打的描述

    Returns:
        func 的返回值

    Raises:
        最后一次失败时的异常
    """
    retryable = _retryable_errors()
    last_exc: BaseException = RuntimeError("not started")
    for attempt in range(1, max_attempts + 1):
        try:
            return await func()
        except retryable as e:
            last_exc = e
            if attempt >= max_attempts:
                logger.error(f"{description}: 达到最大重试次数 {max_attempts}，放弃: {type(e).__name__}: {e}")
                raise
            delay = base_delay * (2 ** (attempt - 1))
            logger.warning(
                f"{description}: 第 {attempt}/{max_attempts} 次失败 ({type(e).__name__}: {str(e)[:80]})，{delay}s 后重试"
            )
            await asyncio.sleep(delay)
        except Exception as e:
            # 不可重试的错误（参数错误、模型不存在、auth 等）→ 立即抛
            logger.error(f"{description}: 不可重试错误 {type(e).__name__}: {e}")
            raise
    raise last_exc
