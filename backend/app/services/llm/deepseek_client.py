"""DeepSeek 客户端实现：基于 OpenAI SDK（DeepSeek 兼容 OpenAI API）。"""

import logging
from typing import Any, Dict, List, Optional

from openai import AsyncOpenAI, APIError

from app.core.config import settings
from app.services.llm.llm_client import ChatMessage, ChatResult, LLMClient, parse_json_loose
from app.services.llm.retry import with_retry

logger = logging.getLogger(__name__)


class DeepSeekClient(LLMClient):
    provider = "deepseek"
    default_model = "deepseek-chat"

    def __init__(self):
        if not settings.DEEPSEEK_API_KEY:
            raise RuntimeError("DEEPSEEK_API_KEY 未配置")
        self._client = AsyncOpenAI(
            api_key=settings.DEEPSEEK_API_KEY,
            base_url=settings.DEEPSEEK_API_BASE,
        )
        self.default_model = settings.DEEPSEEK_MODEL or self.default_model

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
        kwargs: Dict[str, Any] = {
            "model": model or self.default_model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}

        # 设计文档 4.2 节：API 失败重试最多 3 次
        resp = await with_retry(
            lambda: self._client.chat.completions.create(**kwargs),
            max_attempts=3,
            description=f"DeepSeek chat ({kwargs['model']})",
        )

        choice = resp.choices[0]
        text = choice.message.content or ""
        parsed = parse_json_loose(text) if json_mode else None

        usage = None
        if resp.usage:
            usage = {
                "prompt_tokens": resp.usage.prompt_tokens,
                "completion_tokens": resp.usage.completion_tokens,
                "total_tokens": resp.usage.total_tokens,
            }

        return ChatResult(
            text=text,
            parsed=parsed,
            usage=usage,
            model=resp.model,
            finish_reason=choice.finish_reason,
        )
