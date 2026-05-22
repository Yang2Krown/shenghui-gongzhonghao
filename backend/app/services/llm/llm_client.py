"""LLM 客户端抽象 + provider 工厂。

为什么要抽象一层？
- Phase 2 用 DeepSeek 做"信息类型 + 要素提取"（便宜够用）
- Phase 3 切 Claude 跑 Agent A/B（4 Persona 评议 / 6 维度评分）
- 切换只需改 settings.LLM_PROVIDER，业务代码不用改

所有 provider 实现统一接口：chat() -> ChatResult，输入 messages + 可选 JSON schema。
"""

import json
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from app.core.config import settings

logger = logging.getLogger(__name__)


@dataclass
class ChatMessage:
    role: str               # "system" / "user" / "assistant"
    content: str


@dataclass
class ChatResult:
    text: str               # 原始文本输出
    parsed: Optional[Dict[str, Any]] = None  # 若 response_format=json 则附 dict
    usage: Optional[Dict[str, int]] = None   # {prompt_tokens, completion_tokens, total_tokens}
    model: Optional[str] = None
    finish_reason: Optional[str] = None


class LLMClient(ABC):
    """所有 LLM provider 实现此接口。"""

    provider: str = ""
    default_model: str = ""

    @abstractmethod
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
        """通用 chat 接口。

        - json_mode=True：要求模型输出严格 JSON（DeepSeek 走 response_format，Claude 走 tool use）
        - json_schema：若提供，用于校验输出（实现可忽略 schema 仅做提示）
        """


def get_llm_client(provider: Optional[str] = None) -> LLMClient:
    """根据 provider 名取 client；不传则用 settings.LLM_PROVIDER。"""
    name = (provider or settings.LLM_PROVIDER or "deepseek").lower()

    if name == "deepseek":
        from app.services.llm.deepseek_client import DeepSeekClient
        return DeepSeekClient()
    if name == "anthropic":
        from app.services.llm.anthropic_client import AnthropicClient
        return AnthropicClient()

    raise ValueError(f"未知 LLM provider: {name}")


def parse_json_loose(text: str) -> Optional[Dict[str, Any]]:
    """从模型输出里抠 JSON。容错：去掉 ```json fence、首尾噪音。失败返 None。"""
    if not text:
        return None
    s = text.strip()
    if s.startswith("```"):
        # 去 ```json ... ``` fence
        s = s.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
    try:
        return json.loads(s)
    except json.JSONDecodeError:
        # 找第一个 { 到最后一个 }
        first = s.find("{")
        last = s.rfind("}")
        if first >= 0 and last > first:
            try:
                return json.loads(s[first : last + 1])
            except json.JSONDecodeError:
                pass
    logger.warning(f"LLM JSON 解析失败，前 200 字: {text[:200]}")
    return None
