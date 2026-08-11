"""会议纪要到可执行建议的结构化提取。"""

import json
import logging
import re
from typing import Any, Optional

from app.services.llm import LLMClient, get_llm_client
from app.services.llm.llm_client import ChatMessage, parse_json_loose

logger = logging.getLogger(__name__)

MAX_SUGGESTIONS = 15
PRIORITY_ORDER = {"P0": 0, "P1": 1, "P2": 2}


class MeetingExtractionError(ValueError):
    """LLM 输出无法转换成会议建议时抛出的业务异常。"""


_SYSTEM_PROMPT = """你是内部内容运营会议纪要分析助手。
你的任务是从会议纪要中提取可执行的行动类建议，供人工确认后进入执行闭环。

严格规则：
1. 只提取会议原文中明确提出、可以由人或团队执行/验收的行动；不要编造、补充或推断会议中没有的建议。
2. 过滤寒暄、主持词、进度汇报、事实复述、纯观点、情绪表达和没有行动指向的讨论。
3. 保持会议原话语义，content 用一句清楚的行动描述；不要把多个互不相关的行动强行合并。
4. proposer、category、priority、acceptance_criteria 只有原文有依据时才填写；没有依据时 proposer/acceptance_criteria 可为 null，category 填“其他”，priority 默认 P1。
5. 最多输出 15 条；超过 15 条时优先保留 P0，再保留 P1、P2，且不能因为截断而创造新内容。
6. 只输出 JSON 数组，不要输出 markdown、解释或额外文字。

输出格式：
[
  {
    "content": "行动建议",
    "proposer": "提出人或 null",
    "category": "选题/写作/排版/流程/工具/其他",
    "priority": "P0/P1/P2",
    "acceptance_criteria": "可验证的完成标准或 null"
  }
]"""


def _text(value: Any, *, max_length: Optional[int] = None) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, (dict, list)):
        return None
    value = str(value).strip()
    if not value:
        return None
    return value[:max_length] if max_length else value


def _payload_to_items(payload: Any) -> list[Any]:
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        # 某些 provider 的 json_mode 只允许 object，兼容其常见包装，
        # 但最终业务层仍只接受其中的数组。
        for key in ("suggestions", "items", "data", "results"):
            value = payload.get(key)
            if isinstance(value, list):
                return value
    raise MeetingExtractionError("LLM 输出不是 JSON 建议数组")


def _parse_json_output(text: str) -> Any:
    """解析数组或 provider 包装对象，并对被截断的数组做最小闭合修复。"""
    if not text:
        return None
    value = text.strip()
    if value.startswith("```"):
        value = value.split("\n", 1)[-1].rsplit("```", 1)[0].strip()

    try:
        parsed = json.loads(value)
        _payload_to_items(parsed)
        return parsed
    except (TypeError, ValueError, json.JSONDecodeError, MeetingExtractionError):
        pass

    # 复用项目既有容错器，先处理带前后解释或 object 包装的情况。
    parsed = parse_json_loose(value)
    if parsed is not None:
        try:
            _payload_to_items(parsed)
            return parsed
        except MeetingExtractionError:
            pass

    start = value.find("[")
    if start < 0:
        return None
    fragment = value[start:]

    def close_fragment(candidate: str) -> Any:
        stack: list[str] = []
        in_string = False
        escaped = False
        for char in candidate:
            if escaped:
                escaped = False
                continue
            if char == "\\":
                escaped = True
                continue
            if char == '"':
                in_string = not in_string
                continue
            if in_string:
                continue
            if char == "[":
                stack.append("]")
            elif char == "{":
                stack.append("}")
            elif char in {"]", "}"} and stack and stack[-1] == char:
                stack.pop()
        suffix = ('"' if in_string else "") + "".join(reversed(stack))
        try:
            parsed = json.loads(candidate + suffix)
            _payload_to_items(parsed)
            return parsed
        except (TypeError, ValueError, json.JSONDecodeError, MeetingExtractionError):
            return None

    repaired = close_fragment(fragment)
    if repaired is not None:
        logger.info("会议建议 JSON 数组截断修复成功")
        return repaired

    # 若末尾停在一个不完整对象，回退到最近的逗号，保留之前的完整项目。
    for index in range(len(fragment) - 1, 0, -1):
        if fragment[index] == ",":
            repaired = close_fragment(fragment[:index])
            if repaired is not None:
                logger.info("会议建议 JSON 数组部分截断修复成功")
                return repaired
    return None


def _normalize_items(payload: Any, raw_output: str) -> list[dict]:
    normalized: list[dict] = []
    seen: set[str] = set()
    for raw_item in _payload_to_items(payload):
        if not isinstance(raw_item, dict):
            continue
        content = _text(raw_item.get("content"), max_length=4000)
        if not content:
            continue
        dedupe_key = re.sub(r"\s+", " ", content).strip().casefold()
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)

        priority = _text(raw_item.get("priority"), max_length=20) or "P1"
        priority = priority.upper()
        if priority not in PRIORITY_ORDER:
            priority = "P1"
        category = _text(raw_item.get("category"), max_length=50) or "其他"
        proposer = _text(raw_item.get("proposer"), max_length=50)
        acceptance_criteria = _text(raw_item.get("acceptance_criteria"))
        normalized.append(
            {
                "content": content,
                "proposer": proposer,
                "category": category,
                "priority": priority,
                "acceptance_criteria": acceptance_criteria,
                "raw_json": {
                    "raw_output": raw_output,
                    "item": raw_item,
                },
            }
        )

    normalized.sort(key=lambda item: PRIORITY_ORDER[item["priority"]])
    return normalized[:MAX_SUGGESTIONS]


async def extract_suggestions_from_text(
    raw_text: str,
    title: str = "",
    *,
    llm_client: Optional[LLMClient] = None,
) -> list[dict]:
    """调用统一 LLM Client 并返回最多 15 条规范化建议。

    解析同时尝试 provider 已解析结果和项目现有的宽松 JSON 修复器；
    无法得到数组时抛出业务异常，由 Celery 任务负责落失败状态。
    """
    text = raw_text.strip()
    if not text:
        raise MeetingExtractionError("会议纪要不能为空")

    user_content = f"会议主题：{title.strip()}\n\n会议纪要全文：\n{text}"
    client = llm_client or get_llm_client()
    result = await client.chat(
        [
            ChatMessage(role="system", content=_SYSTEM_PROMPT),
            ChatMessage(role="user", content=user_content),
        ],
        temperature=0.2,
        max_tokens=5000,
        json_mode=True,
    )
    raw_output = result.text or ""
    payload = result.parsed if result.parsed is not None else _parse_json_output(raw_output)
    if payload is not None:
        try:
            _payload_to_items(payload)
        except MeetingExtractionError:
            payload = _parse_json_output(raw_output)
    if payload is None:
        raise MeetingExtractionError("LLM 输出无法解析为 JSON")
    items = _normalize_items(payload, raw_output or json.dumps(payload, ensure_ascii=False))
    logger.info("会议建议提取完成：输入 %s 字，得到 %s 条建议", len(text), len(items))
    return items
