"""初稿诊断：召回已确认经验并让模型输出可引用的诊断结果。"""

from __future__ import annotations

import json
import logging
from typing import Any, Iterable, Optional

from app.services.llm.llm_client import (
    ChatMessage,
    LLMClient,
    get_llm_client,
    parse_json_loose,
)

logger = logging.getLogger(__name__)

MAX_PROMPT_DRAFT_CHARS = 60_000
MAX_PROMPT_EXPERIENCE_CHARS = 4_000
MAX_BRIEF_CONTEXT_TEXT = 12_000


def normalize_brief_context(value: Any) -> Optional[dict]:
    """保留 brief 解析结果中可用于诊断的字段，并限制快照大小。"""

    if not isinstance(value, dict):
        return None

    context: dict[str, Any] = {}
    scalar_limits = {
        "product": 300,
        "brief": 5_000,
        "core_message": 1_000,
        "tone": 500,
        "cta": 500,
        "audience": 500,
        "publish": 500,
        "review_notes": 2_000,
        "notes": 2_000,
        "raw_text": MAX_BRIEF_CONTEXT_TEXT,
    }
    for key, max_length in scalar_limits.items():
        text = _text(value.get(key), max_length)
        if text:
            context[key] = text

    for key in ("must_cover", "banned"):
        items = value.get(key)
        if not isinstance(items, list):
            continue
        cleaned = []
        for item in items[:20]:
            text = _text(item, 1_000)
            if text:
                cleaned.append(text)
        if cleaned:
            context[key] = cleaned

    return context or None


class DraftDiagnosisAnalysisError(RuntimeError):
    """模型没有返回符合约定的初稿诊断 JSON。"""

    def __init__(self, message: str, *, raw_output: str = "") -> None:
        super().__init__(message)
        self.raw_output = raw_output


def _text(value: Any, max_length: int) -> Optional[str]:
    if value is None:
        return None
    value = str(value).strip()
    return value[:max_length] if value else None


def _list(value: Any) -> list:
    return value if isinstance(value, list) else []


def _experience_ids(value: Any, allowed_ids: set[int]) -> list[int]:
    result: list[int] = []
    for raw_id in _list(value):
        try:
            card_id = int(raw_id)
        except (TypeError, ValueError):
            continue
        if card_id in allowed_ids and card_id not in result:
            result.append(card_id)
    return result


def _normalize_strengths(value: Any) -> list[dict]:
    strengths: list[dict] = []
    for item in _list(value)[:8]:
        if isinstance(item, str):
            title, detail, evidence = None, item, None
        elif isinstance(item, dict):
            title = _text(item.get("title"), 160)
            detail = _text(item.get("detail") or item.get("description"), 2_000)
            evidence = _text(item.get("evidence"), 1_500)
        else:
            continue
        if detail or title:
            strengths.append({
                "title": title or "已有基础",
                "detail": detail or title or "",
                "evidence": evidence,
            })
    return strengths


def _normalize_issues(value: Any, allowed_ids: set[int]) -> list[dict]:
    issues: list[dict] = []
    for index, item in enumerate(_list(value)[:20]):
        if not isinstance(item, dict):
            continue
        title = _text(item.get("title") or item.get("problem"), 200)
        problem = _text(item.get("problem") or item.get("description"), 2_000)
        recommendation = _text(
            item.get("recommendation") or item.get("suggestion") or item.get("action"),
            3_000,
        )
        evidence = _text(item.get("evidence"), 2_000)
        severity = str(item.get("severity") or "medium").strip().lower()
        if severity not in {"high", "medium", "low"}:
            severity = "medium"
        if not (title or problem or recommendation):
            continue
        issues.append({
            "index": index,
            "title": title or "待优化问题",
            "severity": severity,
            "problem": problem or title or "",
            "evidence": evidence,
            "recommendation": recommendation or "建议结合上下文进一步补充和验证。",
            "experience_ids": _experience_ids(
                item.get("experience_ids") or item.get("related_experience_ids"),
                allowed_ids,
            ),
        })
    return issues


def _normalize_plan(value: Any, allowed_ids: set[int]) -> list[dict]:
    plan: list[dict] = []
    for index, item in enumerate(_list(value)[:12]):
        if isinstance(item, str):
            action, why, priority = item, None, index + 1
            related_ids: list[int] = []
        elif isinstance(item, dict):
            action = _text(item.get("action") or item.get("recommendation"), 2_000)
            why = _text(item.get("why") or item.get("reason"), 1_500)
            try:
                priority = max(1, min(5, int(item.get("priority") or index + 1)))
            except (TypeError, ValueError):
                priority = index + 1
            related_ids = _experience_ids(
                item.get("experience_ids") or item.get("related_experience_ids"),
                allowed_ids,
            )
        else:
            continue
        if not action:
            continue
        plan.append({
            "priority": priority,
            "action": action,
            "why": why,
            "experience_ids": related_ids,
        })
    return plan


def normalize_draft_diagnosis_analysis(
    payload: Any,
    *,
    allowed_experience_ids: Iterable[int],
    raw_output: str = "",
) -> dict:
    """裁剪并校验模型输出，只保留真实召回到的经验引用。"""

    if not isinstance(payload, dict):
        raise DraftDiagnosisAnalysisError("LLM 输出不是 JSON 对象", raw_output=raw_output)
    summary = _text(payload.get("summary") or payload.get("overall_assessment"), 4_000)
    if not summary:
        raise DraftDiagnosisAnalysisError("LLM 输出缺少诊断总结", raw_output=raw_output)

    score = payload.get("overall_score")
    try:
        score = max(0, min(100, int(score))) if score is not None else None
    except (TypeError, ValueError):
        score = None

    allowed_ids = {int(value) for value in allowed_experience_ids}
    return {
        "summary": summary,
        "overall_score": score,
        "overall_assessment": _text(payload.get("overall_assessment"), 4_000),
        "strengths": _normalize_strengths(payload.get("strengths")),
        "issues": _normalize_issues(payload.get("issues"), allowed_ids),
        "improvement_plan": _normalize_plan(payload.get("improvement_plan"), allowed_ids),
        "questions": [
            text
            for text in (
                _text(item, 1_000)
                for item in _list(payload.get("questions"))[:8]
            )
            if text
        ],
        "referenced_experience_ids": _experience_ids(
            payload.get("referenced_experience_ids"),
            allowed_ids,
        ),
    }


def _build_system_prompt() -> str:
    return """
你是一个帮助团队复盘文章初稿的资深编辑。你的任务不是直接代写，而是根据初稿、可选的文章上下文，以及系统召回的已确认方法论，给出有证据的诊断。

请只输出严格 JSON，不要输出 Markdown、解释文字或代码围栏。结构必须是：
{
  "summary": "一句话总结当前初稿最关键的问题或优势",
  "overall_score": 0,
  "overall_assessment": "对文章当前状态的完整判断",
  "strengths": [{"title": "已有基础", "detail": "具体说明", "evidence": "正文依据"}],
  "issues": [{"title": "问题名称", "severity": "high|medium|low", "problem": "问题是什么", "evidence": "正文中的依据", "recommendation": "下一步怎么改", "experience_ids": [1]}],
  "improvement_plan": [{"priority": 1, "action": "具体动作", "why": "为什么先做", "experience_ids": [1]}],
  "questions": ["需要作者补充确认的问题"],
  "referenced_experience_ids": [1]
}

规则：
1. 只评价输入中真实存在或明确缺失的内容，不要臆造事实、受众反馈或数据。
2. 每个问题都要尽量引用原文中的位置、句子或可核对的现象；没有证据就写“正文未提供”。
3. 经验卡片只可以通过它给出的数字 ID 引用，不能编造 ID；如果没有相关经验，experience_ids 使用空数组。
4. 优先给出可执行的修改动作，而不是泛泛而谈的“加强表达”。
5. 文章目标、受众、渠道可能为空；为空时可以给通用诊断，但不要假装知道具体目标。
6. 如果提供了商单 brief，请把其中的核心主张、必须覆盖、禁忌、调性和审核要求当作诊断约束；不要把 brief 中尚未确认的宣传话术当成文章事实。
""".strip()


async def diagnose_draft(
    content: str,
    *,
    title: Optional[str] = None,
    goal: Optional[str] = None,
    audience: Optional[str] = None,
    channel: Optional[str] = None,
    brief_context: Optional[dict] = None,
    matched_experiences: Optional[list[dict]] = None,
    llm_client: Optional[LLMClient] = None,
) -> dict:
    """调用 LLM 对初稿做结构化诊断。"""

    experiences = matched_experiences or []
    experience_context = [
        {
            "id": item.get("id"),
            "title": item.get("title"),
            "category": item.get("category"),
            "content": _text(item.get("content"), MAX_PROMPT_EXPERIENCE_CHARS),
        }
        for item in experiences
        if item.get("id") is not None
    ]
    user_payload = {
        "title": _text(title, 200),
        "goal": _text(goal, 5_000),
        "audience": _text(audience, 500),
        "channel": _text(channel, 100),
        "commercial_brief": normalize_brief_context(brief_context),
        "draft": _text(content, MAX_PROMPT_DRAFT_CHARS),
        "confirmed_experiences": experience_context,
    }

    client = llm_client or get_llm_client()
    result = await client.chat(
        [
            ChatMessage(role="system", content=_build_system_prompt()),
            ChatMessage(
                role="user",
                content=json.dumps(user_payload, ensure_ascii=False),
            ),
        ],
        temperature=0.2,
        max_tokens=12_000,
        json_mode=True,
    )
    raw_output = result.text or ""
    parsed = result.parsed if isinstance(result.parsed, dict) else parse_json_loose(raw_output)
    return normalize_draft_diagnosis_analysis(
        parsed,
        allowed_experience_ids=[item.get("id") for item in experiences],
        raw_output=raw_output,
    )
