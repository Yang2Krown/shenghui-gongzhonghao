"""文章内容快照的统一解码、纯文本提取和字数统计。"""

import json
from typing import Any, Optional


CONTENT_TEXT_KEYS = ("final_text", "content", "text", "body")


def decode_content_json(raw: Any) -> Any:
    """解码文章当前存储值，同时保留无法解析的旧纯文本。

    现有编辑器把生成结果序列化成 JSON 字符串保存；历史文章也可能直接
    保存纯文本。版本快照必须保留前者的完整对象，而不能把 JSON 对象再次
    转成一段 JSON 文本。
    """

    if raw is None or raw == "":
        return {}
    if not isinstance(raw, str):
        return raw
    try:
        return json.loads(raw)
    except (TypeError, ValueError):
        return raw


def _as_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    return str(value)


def extract_content_text(content_json: Any) -> str:
    """从编辑器快照提取纯文本，不把 JSON 字符串本身当正文。"""

    if content_json is None:
        return ""
    if isinstance(content_json, str):
        # JSON 列中的字符串可能是旧纯文本，也可能是二次编码的 JSON。
        decoded = decode_content_json(content_json)
        if decoded is not content_json:
            return extract_content_text(decoded)
        return content_json
    if isinstance(content_json, dict):
        for key in CONTENT_TEXT_KEYS:
            value = content_json.get(key)
            if isinstance(value, str):
                return value
        # 为未来的编辑器扩展保留一层常见 data/body 包装，但不遍历所有字段，
        # 避免把标题、诊断 JSON 或 agent 元数据误算进正文。
        for key in ("data", "document", "payload"):
            value = content_json.get(key)
            if isinstance(value, (dict, list, str)):
                text = extract_content_text(value)
                if text:
                    return text
        return ""
    if isinstance(content_json, list):
        parts = [extract_content_text(item) for item in content_json]
        return "\n".join(part for part in parts if part)
    return _as_text(content_json)


def build_content_snapshot(raw: Any) -> tuple[Any, str, int]:
    """返回 ``(content_json, content_text, word_count)``。"""

    content_json = decode_content_json(raw)
    content_text = extract_content_text(content_json)
    # 现有 ContentCreation/编辑器的统计口径是 Python 字符数；它对中文、
    # 英文、数字和空白保持一致，避免版本列表和文章详情出现两套字数。
    return content_json, content_text, count_content_words(content_text)


def count_content_words(text: Optional[str]) -> int:
    """按项目现有口径统计中英文混合正文长度。"""

    return len(text or "")
