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
    """从模型输出里抠 JSON。容错：去掉 ```json fence、首尾噪音、截断修复。失败返 None。"""
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

        # 截断修复：尝试补全不完整的 JSON
        if first >= 0:
            repaired = _repair_truncated_json(s[first:])
            if repaired is not None:
                logger.info("JSON 截断修复成功")
                return repaired

    logger.warning(f"LLM JSON 解析失败，前 200 字: {text[:200]}")
    return None


def _repair_truncated_json(s: str) -> Optional[Dict[str, Any]]:
    """尝试修复被 max_tokens 截断的 JSON。

    策略：用栈追踪嵌套顺序，逐层闭合未关闭的括号/引号，然后尝试解析。
    """
    stack = []          # 追踪嵌套顺序：'{' 或 '['
    in_string = False
    escape_next = False

    for ch in s:
        if escape_next:
            escape_next = False
            continue
        if ch == "\\":
            escape_next = True
            continue
        if ch == '"' and not escape_next:
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch == "{":
            stack.append("}")
        elif ch == "[":
            stack.append("]")
        elif ch in ("}", "]"):
            if stack and stack[-1] == ch:
                stack.pop()

    # 如果在字符串中间截断，先闭合字符串
    suffix = ""
    if in_string:
        suffix += '"'

    # 按嵌套逆序闭合（从最内层到最外层）
    suffix += "".join(reversed(stack))

    if not suffix:
        return None

    candidate = s + suffix
    try:
        return json.loads(candidate)
    except json.JSONDecodeError:
        pass

    # 备选策略：逐个截断末尾找到能解析的最长前缀
    # 处理 LLM 在末尾多写了不完整内容的情况
    for i in range(len(s) - 1, 0, -1):
        if s[i] in (",", ":"):
            # 截掉这个不完整的键值对，重新闭合
            partial = s[:i]
            # 重新计算栈
            partial_stack = []
            partial_in_str = False
            partial_esc = False
            for ch in partial:
                if partial_esc:
                    partial_esc = False
                    continue
                if ch == "\\":
                    partial_esc = True
                    continue
                if ch == '"' and not partial_esc:
                    partial_in_str = not partial_in_str
                    continue
                if partial_in_str:
                    continue
                if ch == "{":
                    partial_stack.append("}")
                elif ch == "[":
                    partial_stack.append("]")
                elif ch in ("}", "]"):
                    if partial_stack and partial_stack[-1] == ch:
                        partial_stack.pop()
            partial_suffix = ('"' if partial_in_str else "") + "".join(reversed(partial_stack))
            try:
                return json.loads(partial + partial_suffix)
            except json.JSONDecodeError:
                continue

    return None
