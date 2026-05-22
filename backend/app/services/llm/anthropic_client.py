"""Anthropic Claude 客户端（Phase 3 启用）。

Phase 2 暂时只留接口签名，让 LLMClient 抽象闭合。
要用时：pip install anthropic; 把下面的实现解开。
"""

import logging
from typing import Any, Dict, List, Optional

from app.core.config import settings
from app.services.llm.llm_client import ChatMessage, ChatResult, LLMClient, parse_json_loose

logger = logging.getLogger(__name__)


class AnthropicClient(LLMClient):
    provider = "anthropic"
    default_model = "claude-sonnet-4-6"

    def __init__(self):
        if not settings.ANTHROPIC_API_KEY:
            raise RuntimeError("ANTHROPIC_API_KEY 未配置")
        try:
            from anthropic import AsyncAnthropic
        except ImportError as e:
            raise RuntimeError(
                "要使用 Anthropic provider，请先：pip install anthropic"
            ) from e
        self._client = AsyncAnthropic(
            api_key=settings.ANTHROPIC_API_KEY,
            base_url=settings.ANTHROPIC_API_BASE or None,
        )
        self.default_model = settings.ANTHROPIC_MODEL or self.default_model

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

        resp = await self._client.messages.create(**kwargs)
        text = "".join(block.text for block in resp.content if hasattr(block, "text"))
        parsed = parse_json_loose(text) if json_mode else None

        usage = None
        if resp.usage:
            usage = {
                "prompt_tokens": resp.usage.input_tokens,
                "completion_tokens": resp.usage.output_tokens,
                "total_tokens": resp.usage.input_tokens + resp.usage.output_tokens,
            }

        return ChatResult(
            text=text,
            parsed=parsed,
            usage=usage,
            model=resp.model,
            finish_reason=resp.stop_reason,
        )
