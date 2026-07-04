"""AIGoCode Claude 客户端。

使用 AIGoCode API（Anthropic 兼容格式）。
"""

import logging
import time
from typing import Any, Dict, List, Optional

from app.core.config import settings
from app.services.llm.llm_client import ChatMessage, ChatResult, LLMClient, parse_json_loose
from app.services.llm.monitoring import record_llm_call
from app.services.llm.retry import with_retry

logger = logging.getLogger(__name__)


class AIGoCodeClient(LLMClient):
    provider = "aigocode"
    default_model = "claude-opus-4-8-r"

    def __init__(self):
        if not settings.AIGOCODE_API_KEY:
            raise RuntimeError("AIGOCODE_API_KEY 未配置")
        try:
            from anthropic import AsyncAnthropic
        except ImportError as e:
            raise RuntimeError(
                "要使用 AIGoCode provider，请先：pip install anthropic"
            ) from e
        import httpx
        self._client = AsyncAnthropic(
            api_key=settings.AIGOCODE_API_KEY,
            base_url=settings.AIGOCODE_API_BASE or "https://api.highwayapi.ai/anthropic",
            timeout=httpx.Timeout(
                connect=10.0,
                read=120.0,
                write=10.0,
                pool=10.0,
            ),
            max_retries=0,  # 由我们自己的 retry 控制
        )
        self.default_model = settings.AIGOCODE_MODEL or self.default_model

    async def chat(
        self,
        messages: List[ChatMessage],
        *,
        model: Optional[str] = None,
        temperature: float = 0.3,
        max_tokens: int = 4096,
        json_mode: bool = False,
        json_schema: Optional[Dict[str, Any]] = None,
    ) -> ChatResult:
        # Anthropic 的 system 是单独参数，不在 messages 里
        system_msgs = [m.content for m in messages if m.role == "system"]
        chat_msgs = [
            {"role": m.role, "content": m.content}
            for m in messages
            if m.role in ("user", "assistant")
        ]

        kwargs: Dict[str, Any] = {
            "model": model or self.default_model,
            "messages": chat_msgs,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if system_msgs:
            kwargs["system"] = "\n\n".join(system_msgs)

        # Anthropic 没有 response_format，json_mode 靠 system prompt 提示
        if json_mode and "system" in kwargs:
            kwargs["system"] += "\n\n请仅输出严格的 JSON，不要包含 markdown fence 或解释文字。"

        # 用流式接收：长文本改写（如 Agent C）非流式请求容易被中转站网关
        # 判定为「长时间无响应」而返回 504，流式下字节持续流动可避免超时。
        async def _create():
            async with self._client.messages.stream(**kwargs) as stream:
                return await stream.get_final_message()

        started_at = time.perf_counter()
        try:
            resp = await with_retry(
                _create,
                max_attempts=3,
                description=f"AIGoCode chat ({kwargs['model']})",
            )
        except Exception as exc:
            await record_llm_call(
                provider=self.provider,
                model=kwargs["model"],
                status="failed",
                duration_ms=(time.perf_counter() - started_at) * 1000,
                error_message=str(exc),
            )
            raise
        text = "".join(block.text for block in resp.content if getattr(block, "text", None))
        parsed = parse_json_loose(text) if json_mode else None

        usage = None
        if resp.usage:
            usage = {
                "prompt_tokens": resp.usage.input_tokens,
                "completion_tokens": resp.usage.output_tokens,
                "total_tokens": resp.usage.input_tokens + resp.usage.output_tokens,
            }

        # 统一截断标志：Anthropic 用 "max_tokens"，下游 Agent 按 "length" 判断
        finish_reason = resp.stop_reason
        if finish_reason == "max_tokens":
            finish_reason = "length"

        result = ChatResult(
            text=text,
            parsed=parsed,
            usage=usage,
            model=resp.model,
            finish_reason=finish_reason,
        )
        await record_llm_call(
            provider=self.provider,
            model=result.model or kwargs["model"],
            usage=usage,
            duration_ms=(time.perf_counter() - started_at) * 1000,
            status="success",
            finish_reason=result.finish_reason,
        )
        return result
