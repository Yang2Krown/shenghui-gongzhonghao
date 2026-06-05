"""Moonshot（Kimi）客户端实现：基于 OpenAI SDK + 联网搜索工具。

Moonshot API 兼容 OpenAI 格式，额外支持 $web_search 工具调用。
用于 Agent A2 可写性审计等需要实时搜索的场景。
"""

import json
import logging
from typing import Any, Dict, List, Optional

from openai import AsyncOpenAI, APIError

from app.core.config import settings
from app.services.llm.llm_client import ChatMessage, ChatResult, LLMClient, parse_json_loose
from app.services.llm.retry import with_retry

logger = logging.getLogger(__name__)

# Moonshot 联网搜索工具定义
WEB_SEARCH_TOOL = {
    "type": "builtin_function",
    "function": {"name": "$web_search"},
}


class MoonshotClient(LLMClient):
    """Moonshot / Kimi API 客户端，支持联网搜索。"""

    provider = "moonshot"
    default_model = settings.MOONSHOT_MODEL

    def __init__(self):
        if not settings.MOONSHOT_API_KEY:
            raise RuntimeError("MOONSHOT_API_KEY 未配置")
        self._client = AsyncOpenAI(
            api_key=settings.MOONSHOT_API_KEY,
            base_url=settings.MOONSHOT_API_BASE,
        )
        self.default_model = settings.MOONSHOT_MODEL or self.default_model

    async def chat(
        self,
        messages: List[ChatMessage],
        *,
        model: Optional[str] = None,
        temperature: float = 0.3,
        max_tokens: int = 4096,
        json_mode: bool = False,
        json_schema: Optional[Dict[str, Any]] = None,
        web_search: bool = False,
    ) -> ChatResult:
        """通用 chat 接口，可选启用联网搜索。

        Args:
            web_search: 是否启用 $web_search 联网搜索工具。
                        启用后模型会自主决定是否搜索、搜什么，
                        搜索结果自动注入上下文。
        """
        kwargs: Dict[str, Any] = {
            "model": model or self.default_model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}
        if web_search:
            kwargs["tools"] = [WEB_SEARCH_TOOL]

        resp = await with_retry(
            lambda: self._client.chat.completions.create(**kwargs),
            max_attempts=3,
            description=f"Moonshot chat ({kwargs['model']})",
        )

        choice = resp.choices[0]
        message = choice.message
        text = message.content or ""

        # 处理 tool_calls（联网搜索触发时，模型可能先返回 tool_calls 而非最终答案）
        if message.tool_calls and web_search:
            text = await self._handle_search_tool_calls(
                kwargs["messages"], message, kwargs, web_search
            )

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

    async def _handle_search_tool_calls(
        self,
        original_messages: list,
        assistant_message,
        kwargs: dict,
        web_search: bool,
    ) -> str:
        """处理联网搜索的多轮 tool_call 循环。

        Moonshot 的搜索流程：
        1. 模型返回 tool_calls（name=$web_search）
        2. 平台自动执行搜索，结果在下一轮 tool message 中返回
        3. 我们把 assistant + tool messages 追加到上下文，再次调用
        4. 模型基于搜索结果生成最终答案
        """
        messages = list(original_messages)

        # 追加 assistant 的 tool_calls 消息
        messages.append({
            "role": "assistant",
            "content": assistant_message.content,
            "tool_calls": [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {"name": tc.function.name, "arguments": tc.function.arguments},
                }
                for tc in assistant_message.tool_calls
            ],
        })

        # 追加 tool 结果（Moonshot 平台自动执行搜索，结果在 tool_calls 的 arguments 中）
        for tc in assistant_message.tool_calls:
            search_args = tc.function.arguments
            # Moonshot 搜索结果在 arguments 字段中（JSON 字符串）
            messages.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": search_args,
            })

            # 记录搜索信息
            try:
                args_parsed = json.loads(search_args) if isinstance(search_args, str) else search_args
                if isinstance(args_parsed, dict) and "results" in args_parsed:
                    logger.info(
                        f"Moonshot 联网搜索完成: "
                        f"查询={args_parsed.get('query', '?')}, "
                        f"结果数={len(args_parsed['results'])}"
                    )
            except (json.JSONDecodeError, TypeError):
                pass

        # 去掉 tools 参数，避免无限循环搜索
        final_kwargs = {k: v for k, v in kwargs.items() if k != "tools"}
        final_kwargs["messages"] = messages

        resp = await with_retry(
            lambda: self._client.chat.completions.create(**final_kwargs),
            max_attempts=3,
            description="Moonshot chat (post-search)",
        )

        final_choice = resp.choices[0]
        return final_choice.message.content or ""
