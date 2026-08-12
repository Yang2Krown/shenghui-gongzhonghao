"""文章复盘的文本分块、重点改动识别和 AI 分析。"""

from __future__ import annotations

import difflib
import json
import logging
import re
from typing import Any, Optional

from app.services.llm.llm_client import (
    ChatMessage,
    LLMClient,
    get_llm_client,
    parse_json_loose,
)

logger = logging.getLogger(__name__)

MAX_GROUP_TEXT = 8_000
MAX_ANALYSIS_GROUPS = 40


def _clip(value: Any, max_length: int) -> str:
    text = str(value or "").strip()
    if len(text) <= max_length:
        return text
    return f"{text[:max_length]}\n……（内容过长，已截断）"


def normalize_review_text(text: str) -> str:
    """统一换行，但不改写文章正文。"""

    value = (text or "").replace("\r\n", "\n").replace("\r", "\n")
    return value.strip()


def split_review_blocks(text: str) -> list[str]:
    """优先按段落切分；没有空行的 PDF 文本则按非空行切分。"""

    normalized = normalize_review_text(text)
    if not normalized:
        return []
    raw_blocks = re.split(r"\n\s*\n+", normalized)
    if len(raw_blocks) == 1:
        raw_blocks = normalized.splitlines()
    blocks = []
    for block in raw_blocks:
        cleaned = re.sub(r"[ \t]+", " ", block).strip()
        if cleaned:
            blocks.append(cleaned)
    return blocks


def _impact(before_text: str, after_text: str, before_count: int, after_count: int) -> tuple[str, bool, float]:
    max_chars = max(len(before_text), len(after_text))
    if before_text and after_text:
        similarity = difflib.SequenceMatcher(
            None,
            before_text,
            after_text,
            autojunk=False,
        ).ratio()
        change_ratio = round(1 - similarity, 4)
    else:
        change_ratio = 1.0

    major = (
        (max_chars >= 160 and change_ratio >= 0.28)
        or max(before_count, after_count) >= 3
        or (max_chars >= 80 and change_ratio >= 0.45)
    )
    if major:
        return "high", True, change_ratio
    if max_chars >= 40 or change_ratio >= 0.2:
        return "medium", False, change_ratio
    return "low", False, change_ratio


def build_change_groups(before_text: str, after_text: str) -> dict:
    """按段落/行生成可评论的改动块，并标记较大修改。"""

    before_blocks = split_review_blocks(before_text)
    after_blocks = split_review_blocks(after_text)
    matcher = difflib.SequenceMatcher(
        None,
        before_blocks,
        after_blocks,
        autojunk=False,
    )
    groups: list[dict] = []
    for index, (tag, start_before, end_before, start_after, end_after) in enumerate(
        matcher.get_opcodes(),
        start=1,
    ):
        if tag == "equal":
            continue
        before_values = before_blocks[start_before:end_before]
        after_values = after_blocks[start_after:end_after]
        before_segment = "\n\n".join(before_values)
        after_segment = "\n\n".join(after_values)
        impact, is_major, change_ratio = _impact(
            before_segment,
            after_segment,
            len(before_values),
            len(after_values),
        )
        groups.append(
            {
                "id": f"change-{len(groups) + 1:03d}",
                "kind": tag,
                "impact": impact,
                "is_major": is_major,
                "change_ratio": change_ratio,
                "before_block_start": start_before + 1 if before_values else None,
                "before_block_end": end_before if before_values else None,
                "after_block_start": start_after + 1 if after_values else None,
                "after_block_end": end_after if after_values else None,
                "before_block_count": len(before_values),
                "after_block_count": len(after_values),
                "before_char_count": len(before_segment),
                "after_char_count": len(after_segment),
                "before": _clip(before_segment, MAX_GROUP_TEXT),
                "after": _clip(after_segment, MAX_GROUP_TEXT),
            }
        )

    major_ids = [group["id"] for group in groups if group["is_major"]]
    return {
        "before_block_count": len(before_blocks),
        "after_block_count": len(after_blocks),
        "total_groups": len(groups),
        "major_group_count": len(major_ids),
        "major_group_ids": major_ids,
        "groups": groups,
        "added_blocks": sum(group["after_block_count"] for group in groups),
        "removed_blocks": sum(group["before_block_count"] for group in groups),
    }


class ArticleReviewAnalysisError(ValueError):
    """LLM 输出无法整理成文章复盘分析对象。"""

    def __init__(self, message: str, *, raw_output: str = "") -> None:
        super().__init__(message)
        self.raw_output = raw_output


_SYSTEM_PROMPT = """你是内部内容团队的文章复盘助手。
你的任务是比较同一篇文章的改前稿和改后稿，只分析输入里真实出现的变化，帮助团队理解“改了什么、为什么改、改完带来了什么效果”，最后提炼可以复用的方法论。

严格规则：
1. 只根据提供的改动块和人工评论作判断，不编造文章没有出现的事实。
2. 每条 key_changes 必须引用一个真实的 change_group_id；无法判断修改原因时，明确写“需要人工确认”，不要伪造动机。
3. methodology_candidates 必须是可复用的写作判断规则，而不是对本篇文章的复述；证据只能来自对应改动块。
4. 只输出一个 JSON 对象，不要输出 Markdown、解释或代码围栏。

输出格式：
{
  "summary": "本次复盘最重要的变化和结果，用 1-3 句话概括",
  "key_changes": [
    {
      "group_id": "change-001",
      "what_changed": "具体改了什么",
      "likely_reason": "修改原因；无法确认时写需要人工确认",
      "effect": "改后对读者理解、结构或转化可能带来的影响",
      "confidence": 0.0
    }
  ],
  "methodology_candidates": [
    {
      "title": "方法论名称",
      "rule": "以后遇到类似文章时可以复用的判断规则",
      "rationale": "为什么这个规则成立",
      "example": "本次复盘中的具体例子",
      "evidence_group_ids": ["change-001"]
    }
  ],
  "open_questions": ["仍需人工确认的问题"]
}""".strip()


def _text(value: Any, *, max_length: int = 2_000) -> Optional[str]:
    if value is None or isinstance(value, (dict, list)):
        return None
    value = str(value).strip()
    return value[:max_length] if value else None


def normalize_article_review_analysis(
    payload: Any,
    *,
    raw_output: str = "",
    parse_status: str = "parsed",
    allow_empty: bool = False,
) -> dict:
    if not isinstance(payload, dict):
        raise ArticleReviewAnalysisError("LLM 输出不是 JSON 对象", raw_output=raw_output)
    summary = _text(payload.get("summary"), max_length=4_000)
    raw_changes = payload.get("key_changes") or payload.get("changes") or []
    raw_candidates = payload.get("methodology_candidates") or payload.get("methodology") or []
    raw_questions = payload.get("open_questions") or payload.get("questions") or []
    if isinstance(raw_changes, dict):
        raw_changes = [raw_changes]
    if isinstance(raw_candidates, dict):
        raw_candidates = [raw_candidates]
    if isinstance(raw_questions, str):
        raw_questions = [raw_questions]
    if not isinstance(raw_changes, list):
        raise ArticleReviewAnalysisError("LLM 输出的 key_changes 不是数组", raw_output=raw_output)
    if not isinstance(raw_candidates, list):
        raise ArticleReviewAnalysisError(
            "LLM 输出的 methodology_candidates 不是数组",
            raw_output=raw_output,
        )
    if not isinstance(raw_questions, list):
        raw_questions = []

    key_changes = []
    for item in raw_changes[:30]:
        if not isinstance(item, dict):
            continue
        group_id = _text(item.get("group_id") or item.get("id"), max_length=80)
        what_changed = _text(item.get("what_changed") or item.get("change"), max_length=2_000)
        if not group_id or not what_changed:
            continue
        confidence = item.get("confidence", 0.0)
        try:
            confidence = max(0.0, min(1.0, float(confidence)))
        except (TypeError, ValueError):
            confidence = 0.0
        key_changes.append(
            {
                "group_id": group_id,
                "what_changed": what_changed,
                "likely_reason": _text(
                    item.get("likely_reason") or item.get("reason"),
                    max_length=2_000,
                ),
                "effect": _text(item.get("effect") or item.get("impact"), max_length=2_000),
                "confidence": round(confidence, 3),
            }
        )

    candidates = []
    for item in raw_candidates[:20]:
        if isinstance(item, str):
            item = {"title": item, "rule": item}
        if not isinstance(item, dict):
            continue
        rule = _text(item.get("rule") or item.get("content") or item.get("principle"), max_length=2_000)
        if not rule:
            continue
        evidence_ids = item.get("evidence_group_ids") or item.get("group_ids") or []
        if isinstance(evidence_ids, str):
            evidence_ids = [evidence_ids]
        if not isinstance(evidence_ids, list):
            evidence_ids = []
        candidates.append(
            {
                "title": _text(item.get("title") or item.get("name") or rule, max_length=160) or "未命名方法",
                "rule": rule,
                "rationale": _text(item.get("rationale") or item.get("reason"), max_length=2_000),
                "example": _text(item.get("example") or item.get("application"), max_length=2_000),
                "evidence_group_ids": [
                    value for value in (_text(item_id, max_length=80) for item_id in evidence_ids[:10]) if value
                ],
            }
        )

    questions = [
        value
        for value in (_text(item, max_length=1_000) for item in raw_questions[:20])
        if value
    ]
    if not allow_empty and not summary and not key_changes and not candidates:
        raise ArticleReviewAnalysisError("LLM 输出没有可沉淀的复盘内容", raw_output=raw_output)
    return {
        "status": "succeeded",
        "summary": summary,
        "key_changes": key_changes,
        "methodology_candidates": candidates,
        "open_questions": questions,
        "parse_status": parse_status if parse_status in {"parsed", "repaired", "manual"} else "parsed",
        "raw_output": raw_output,
    }


async def analyze_article_review(
    *,
    title: str,
    change_groups: list[dict],
    comments: Optional[list[dict]] = None,
    llm_client: Optional[LLMClient] = None,
) -> dict:
    """调用统一 LLM Client 分析改动块。"""

    if not change_groups:
        return {
            "status": "succeeded",
            "summary": "改前稿和改后稿没有检测到文本变化。",
            "key_changes": [],
            "methodology_candidates": [],
            "open_questions": [],
            "parse_status": "parsed",
            "raw_output": "",
        }
    selected = sorted(
        change_groups,
        key=lambda group: (not group.get("is_major", False), group.get("id", "")),
    )[:MAX_ANALYSIS_GROUPS]
    context = {
        "title": title,
        "changes": selected,
        "human_comments": comments or [],
    }
    client = llm_client or get_llm_client()
    try:
        result = await client.chat(
            [
                ChatMessage(role="system", content=_SYSTEM_PROMPT),
                ChatMessage(
                    role="user",
                    content=json.dumps(context, ensure_ascii=False),
                ),
            ],
            temperature=0.2,
            max_tokens=6_000,
            json_mode=True,
        )
    except Exception as exc:
        raise ArticleReviewAnalysisError(str(exc)[:1_000]) from exc

    raw_output = result.text or ""
    payload = result.parsed if isinstance(result.parsed, dict) else parse_json_loose(raw_output)
    if not isinstance(payload, dict):
        raise ArticleReviewAnalysisError("LLM 输出无法解析为文章复盘 JSON", raw_output=raw_output)
    parse_status = "repaired" if result.finish_reason in {"length", "max_tokens"} else "parsed"
    analysis = normalize_article_review_analysis(
        payload,
        raw_output=raw_output,
        parse_status=parse_status,
    )
    analysis.update(
        {
            "model": result.model,
            "usage": result.usage,
            "finish_reason": result.finish_reason,
        }
    )
    return analysis


def build_review_experience_content(
    review: Any,
    *,
    group_ids: Optional[list[str]] = None,
    custom_content: Optional[str] = None,
) -> str:
    """把人工确认后的复盘结果整理成经验库中的可追溯正文。"""

    if custom_content and custom_content.strip():
        return custom_content.strip()[:50_000]
    groups = list(review.change_groups or [])
    selected_ids = set(group_ids or [group.get("id") for group in groups])
    selected = [group for group in groups if group.get("id") in selected_ids]
    analysis = review.ai_analysis if isinstance(review.ai_analysis, dict) else {}
    sections = [
        "【文章复盘方法论】",
        f"复盘主题：{review.title}",
        f"改前稿：{review.before_filename}",
        f"改后稿：{review.after_filename}",
        "",
        "【AI 差异总结】",
        analysis.get("summary") or "尚未生成 AI 总结，以下保留人工确认的改动。",
    ]
    key_changes = [
        item for item in (analysis.get("key_changes") or [])
        if not selected_ids or item.get("group_id") in selected_ids
    ]
    if key_changes:
        sections.append("\n【关键修改】")
        for item in key_changes:
            sections.append(
                f"- {item.get('group_id')}: {item.get('what_changed')}; "
                f"原因：{item.get('likely_reason') or '需要人工确认'}; "
                f"效果：{item.get('effect') or '待观察'}"
            )
    candidates = analysis.get("methodology_candidates") or []
    if candidates:
        sections.append("\n【可复用方法论】")
        for item in candidates:
            evidence = ", ".join(item.get("evidence_group_ids") or []) or "未标注"
            sections.extend(
                [
                    f"- {item.get('title') or '未命名方法'}：{item.get('rule') or ''}",
                    f"  为什么：{item.get('rationale') or '未说明'}",
                    f"  例子：{item.get('example') or '未说明'}",
                    f"  证据改动块：{evidence}",
                ]
            )
    if selected:
        sections.append("\n【原文证据】")
        for group in selected:
            sections.extend(
                [
                    f"改动块 {group.get('id')}（{group.get('impact')}）",
                    f"改前：{group.get('before') or '（无）'}",
                    f"改后：{group.get('after') or '（无）'}",
                ]
            )
    comments = list(review.comments or [])
    if comments:
        sections.append("\n【人工评论】")
        for comment in comments:
            group_label = comment.change_group_id or "整体"
            sections.append(f"- {group_label}：{comment.body}")
    return "\n".join(sections).strip()[:50_000]
