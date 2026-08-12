"""文章版本、文本 diff 和语义摘要的共享服务。"""

from __future__ import annotations

import difflib
import json
import logging
from datetime import datetime
from typing import Any, Optional

from app.services.llm.llm_client import ChatMessage, LLMClient, get_llm_client, parse_json_loose

logger = logging.getLogger(__name__)


def version_pair_key(before_version_id: int, after_version_id: int) -> str:
    return f"{int(before_version_id)}:{int(after_version_id)}"


def diff_summary_pairs(raw: Any) -> dict[str, dict]:
    """读取版本上的多版本对摘要，兼容未来/旧的单对象格式。"""

    if not isinstance(raw, dict):
        return {}
    pairs = raw.get("pairs")
    if isinstance(pairs, dict):
        return {
            str(key): value
            for key, value in pairs.items()
            if isinstance(value, dict)
        }
    # 当前 Phase 1c 首次写入使用 pairs；如果已有外部实验数据直接写了
    # status，则作为 legacy 保留，不覆盖它。
    if raw.get("status"):
        return {"legacy": dict(raw)}
    return {}


def get_pair_summary(raw: Any, before_version_id: int, after_version_id: int) -> Optional[dict]:
    return diff_summary_pairs(raw).get(version_pair_key(before_version_id, after_version_id))


def set_pair_summary(
    raw: Any,
    before_version_id: int,
    after_version_id: int,
    summary: dict,
) -> dict:
    pairs = diff_summary_pairs(raw)
    pairs[version_pair_key(before_version_id, after_version_id)] = summary
    result = {"pairs": pairs}
    if isinstance(raw, dict) and raw.get("legacy"):
        result["legacy"] = raw["legacy"]
    return result


def semantic_summary_status(raw: Any) -> Optional[str]:
    pairs = diff_summary_pairs(raw)
    if not pairs:
        return None
    # 列表只需要提示当前版本是否有摘要；优先显示仍需用户关注的状态。
    for status in ("running", "queued", "failed", "succeeded"):
        if any(item.get("status") == status for item in pairs.values()):
            return status
    return None


def iso_now(value: Optional[datetime] = None) -> str:
    return (value or datetime.utcnow()).isoformat()


def build_text_diff(
    before_text: str,
    after_text: str,
    *,
    before_label: str = "before",
    after_label: str = "after",
) -> dict:
    """使用 Python 标准库生成统一 diff 和前端可直接渲染的结构化行。"""

    before_lines = (before_text or "").splitlines()
    after_lines = (after_text or "").splitlines()
    matcher = difflib.SequenceMatcher(None, before_lines, after_lines, autojunk=False)
    lines: list[dict[str, str]] = []
    added_count = 0
    removed_count = 0

    for tag, start_before, end_before, start_after, end_after in matcher.get_opcodes():
        if tag == "equal":
            lines.extend({"kind": "unchanged", "text": value} for value in before_lines[start_before:end_before])
        elif tag == "delete":
            removed_count += end_before - start_before
            lines.extend({"kind": "removed", "text": value} for value in before_lines[start_before:end_before])
        elif tag == "insert":
            added_count += end_after - start_after
            lines.extend({"kind": "added", "text": value} for value in after_lines[start_after:end_after])
        elif tag == "replace":
            removed_count += end_before - start_before
            added_count += end_after - start_after
            lines.extend({"kind": "removed", "text": value} for value in before_lines[start_before:end_before])
            lines.extend({"kind": "added", "text": value} for value in after_lines[start_after:end_after])

    unified = "\n".join(
        difflib.unified_diff(
            before_lines,
            after_lines,
            fromfile=before_label,
            tofile=after_label,
            lineterm="",
        )
    )
    return {
        "before_text": before_text or "",
        "after_text": after_text or "",
        "added_count": added_count,
        "removed_count": removed_count,
        "unified_diff": unified,
        "lines": lines,
        "hunks": _build_hunks(lines),
        "summary": f"新增 {added_count} 行，删除 {removed_count} 行",
    }


def _build_hunks(lines: list[dict[str, str]]) -> list[list[dict[str, str]]]:
    """将结构化行按相邻上下文分组，供前端按块渲染。"""

    if not lines:
        return []
    hunks: list[list[dict[str, str]]] = [[]]
    for line in lines:
        if line["kind"] == "unchanged" and hunks[-1] and any(
            item["kind"] != "unchanged" for item in hunks[-1]
        ):
            # 保留当前上下文行；连续的 unchanged 仍属于同一块。
            hunks[-1].append(line)
        elif line["kind"] != "unchanged" and hunks[-1] and all(
            item["kind"] == "unchanged" for item in hunks[-1]
        ):
            hunks.append([line])
        else:
            hunks[-1].append(line)
    return [hunk for hunk in hunks if hunk]


class VersionDiffSummaryError(RuntimeError):
    """语义摘要无法得到符合约定的 JSON。"""

    def __init__(self, message: str, *, raw_output: str = "") -> None:
        super().__init__(message)
        self.raw_output = raw_output


_SUMMARY_SYSTEM_PROMPT = """
你是文章版本变更分析员。请只根据输入中的修改前正文、修改后正文和（如果提供的）
会议建议，输出严格 JSON，不要输出 Markdown、解释或代码围栏。
输出结构必须是：
{
  "summary": "本次修改主要调整了什么",
  "changes": [
    {"position": "开头/中段/结尾或原文可确认的位置", "before": "修改前内容", "after": "修改后内容", "reason": "会议或内容中明确体现的修改原因"}
  ],
  "suggestion_match": "关联的会议建议；没有则为 null"
}
只描述正文中真实存在的变化。会议建议没有明确说明原因时，reason 必须为 null，
不能根据常识补写动机；找不到对应建议时 suggestion_match 必须为 null。
""".strip()


def _text_value(value: Any, *, max_length: int = 4000) -> Optional[str]:
    if value is None:
        return None
    value = str(value).strip()
    return value[:max_length] if value else None


def normalize_semantic_summary(payload: Any, *, raw_output: str) -> dict:
    if not isinstance(payload, dict):
        raise VersionDiffSummaryError("LLM 输出不是 JSON 对象", raw_output=raw_output)
    summary = _text_value(payload.get("summary"), max_length=4000)
    if not summary:
        raise VersionDiffSummaryError("LLM 输出缺少 summary", raw_output=raw_output)
    raw_changes = payload.get("changes")
    if raw_changes is None:
        raw_changes = []
    if not isinstance(raw_changes, list):
        raise VersionDiffSummaryError("LLM 输出的 changes 不是数组", raw_output=raw_output)

    changes = []
    for item in raw_changes[:30]:
        if not isinstance(item, dict):
            continue
        position = _text_value(item.get("position"), max_length=100)
        before = _text_value(item.get("before"), max_length=2000)
        after = _text_value(item.get("after"), max_length=2000)
        reason = _text_value(item.get("reason"), max_length=2000)
        if not position and not before and not after:
            continue
        changes.append({
            "position": position,
            "before": before,
            "after": after,
            "reason": reason,
        })

    suggestion_match = payload.get("suggestion_match")
    if suggestion_match is not None:
        suggestion_match = _text_value(suggestion_match, max_length=2000)
    return {
        "summary": summary,
        "changes": changes,
        "suggestion_match": suggestion_match,
    }


async def summarize_version_diff(
    before_text: str,
    after_text: str,
    suggestion_text: Optional[str] = None,
    *,
    llm_client: Optional[LLMClient] = None,
) -> dict:
    """调用现有 LLM Client，解析并校验版本语义差异。"""

    client = llm_client or get_llm_client()
    context = {
        "before": before_text or "",
        "after": after_text or "",
        "meeting_suggestion": suggestion_text or None,
    }
    try:
        result = await client.chat(
            [
                ChatMessage(role="system", content=_SUMMARY_SYSTEM_PROMPT),
                ChatMessage(
                    role="user",
                    content=json.dumps(context, ensure_ascii=False),
                ),
            ],
            temperature=0.1,
            max_tokens=3000,
            json_mode=True,
        )
    except Exception as exc:
        raise VersionDiffSummaryError(str(exc)[:1000]) from exc

    raw_output = result.text or ""
    payload = result.parsed if isinstance(result.parsed, dict) else parse_json_loose(raw_output)
    if not isinstance(payload, dict):
        raise VersionDiffSummaryError("LLM 输出无法解析为语义摘要 JSON", raw_output=raw_output)
    normalized = normalize_semantic_summary(payload, raw_output=raw_output)
    normalized.update({
        "raw_output": raw_output,
        "model": result.model,
        "usage": result.usage,
        "finish_reason": result.finish_reason,
    })
    return normalized


def build_experience_content(
    *,
    before_version: Any,
    after_version: Any,
    text_diff: dict,
    note: Optional[str] = None,
    suggestion_text: Optional[str] = None,
    semantic_summary: Optional[dict] = None,
) -> str:
    """生成可追溯的基础经验正文；语义摘要完成后可再次调用补全。"""

    sections = [
        "【来源版本】",
        f"文章：{after_version.title}",
        f"版本：v{before_version.version_no if before_version else '—'} → v{after_version.version_no}",
        f"版本类型：{getattr(after_version, 'version_type', '')}",
        "",
        "【文本 diff 摘要】",
        text_diff.get("summary") or "未检测到文本行变化",
    ]
    if semantic_summary and semantic_summary.get("summary"):
        sections.extend(["", "【语义差异摘要】", semantic_summary["summary"]])
        changes = semantic_summary.get("changes") or []
        if changes:
            sections.append("修改点：")
            for item in changes:
                sections.append(
                    f"- {item.get('position') or '未标注'}："
                    f"{item.get('before') or '（无）'} → {item.get('after') or '（无）'}；"
                    f"原因：{item.get('reason') or '未在输入中明确'}"
                )
        if semantic_summary.get("suggestion_match"):
            sections.extend(["", "【关联会议建议】", semantic_summary["suggestion_match"]])
    if note:
        sections.extend(["", "【版本备注】", note])
    if suggestion_text and not (semantic_summary and semantic_summary.get("suggestion_match")):
        sections.extend(["", "【关联会议建议】", suggestion_text])
    return "\n".join(sections).strip()
