"""创作角度体检的三个独立 Agent。"""

import json
import logging
from typing import Optional

from app.services.angle_inspection.schemas import (
    AngleAuditOutput,
    RhythmAuditOutput,
    SelectedTopicInput,
    SourceAuditOutput,
)
from app.services.llm import LLMClient, get_llm_client
from app.services.llm.llm_client import ChatMessage, parse_json_loose

logger = logging.getLogger(__name__)


def _topic_json(topic: SelectedTopicInput) -> str:
    return json.dumps(topic.model_dump(), ensure_ascii=False, indent=2)


MAX_RETRIES = 3

_SYSTEM_SOURCE = (
    "你是创作角度体检的第一关：信息源审计员。"
    "只判断素材来源是否多元、是否有跨领域交叉点，并给出补充建议。"
    "输出必须是严格 JSON。"
)

_SYSTEM_ANGLE = (
    "你是创作角度体检的第二关：角度陌生化检验员。"
    "角度权重最高，必须直接、犀利、不和稀泥。"
    "第一直觉角度不能用；好角度必须同时预料之外、情理之中。"
    "输出必须是严格 JSON。"
)

_SYSTEM_RHYTHM = (
    "你是创作角度体检的第三关：节奏设计师。"
    "你负责把已确认的创作角度转成情绪地图、升番结构、开头钩子和结尾余震。"
    "输出必须是严格 JSON。"
)


async def audit_sources(
    topic: SelectedTopicInput,
    *,
    llm_client: Optional[LLMClient] = None,
    model: Optional[str] = None,
) -> SourceAuditOutput:
    """第一关：信息源审计。Schema 校验失败时自动重试，最多 3 次。"""
    client = llm_client or get_llm_client()

    user_content = f"""【输入选题】
{_topic_json(topic)}

【检查要求】
1. 识别当前选题涉及的领域。
2. 领域数量：1 个=🔴 红灯，2 个=🟡 黄灯，3 个及以上=🟢 绿灯。
3. 判断有没有跨领域交叉点。
4. 如果不是绿灯，给历史类比/商业案例/日常观察/影视作品/其他领域热点中的具体补充建议。

【输出 JSON】
{{
  "verdict": "🟢 绿灯 / 🟡 黄灯 / 🔴 红灯",
  "source_domains": ["领域1：说明", "领域2：说明"],
  "intersection": "有/无 - 具体交叉点",
  "supplement_suggestions": ["建议1", "建议2"]
}}"""

    last_error = None
    for attempt in range(1, MAX_RETRIES + 1):
        extra = ""
        if attempt > 1:
            extra = "\n\n【重要】上一次输出格式不符合要求。请严格输出 JSON，必须包含 verdict、source_domains、intersection、supplement_suggestions 字段。不要输出 markdown 或解释文字。"

        messages = [
            ChatMessage(role="system", content=_SYSTEM_SOURCE + extra),
            ChatMessage(role="user", content=user_content),
        ]
        result = await client.chat(messages=messages, model=model, temperature=0.25, max_tokens=2500, json_mode=True)
        parsed = parse_json_loose(result.text)
        if not parsed:
            last_error = ValueError("信息源审计输出格式不符合 schema")
            logger.warning("信息源审计第 %d/%d 次输出解析失败: %s", attempt, MAX_RETRIES, result.text[:300])
            continue
        return SourceAuditOutput(**parsed)

    raise last_error


async def audit_angle(
    topic: SelectedTopicInput,
    source_audit: SourceAuditOutput,
    *,
    llm_client: Optional[LLMClient] = None,
    model: Optional[str] = None,
) -> AngleAuditOutput:
    """第二关：角度陌生化检验。Schema 校验失败时自动重试，最多 3 次。"""
    client = llm_client or get_llm_client()

    user_content = f"""【输入选题】
{_topic_json(topic)}

【第一关结果】
{json.dumps(source_audit.model_dump(), ensure_ascii=False, indent=2)}

【检查要求】
1. 列出 2-3 个大多数人会写的第一直觉角度。
2. 判断当前切入说明/角度是否落入第一直觉。
3. 用"预料之外 + 情理之中"评估当前角度。
4. 无论是否通过，都生成 1-2 个备选陌生化角度。技巧从反面角度、视角翻转、载体转换、时间轴位移、跨领域嫁接中选。

【输出 JSON】
{{
  "obvious_angles": ["第一直觉角度1", "第一直觉角度2"],
  "why_avoid": "为什么这些角度不能选",
  "current_angle": "当前角度",
  "verdict": "✅ 通过 / ❌ 不通过 / ⚠️ 需调整",
  "unexpected": true,
  "reasonable": true,
  "core_tension": "核心张力一句话",
  "alternative_angles": [
    {{
      "angle": "备选角度",
      "contrast_type": "视角翻转",
      "unexpected": true,
      "reasonable": true,
      "core_tension": "核心张力"
    }}
  ]
}}"""

    last_error = None
    for attempt in range(1, MAX_RETRIES + 1):
        extra = ""
        if attempt > 1:
            extra = "\n\n【重要】上一次输出格式不符合要求。请严格输出 JSON，必须包含 obvious_angles、why_avoid、current_angle、verdict、unexpected、reasonable、core_tension、alternative_angles 字段。不要输出 markdown 或解释文字。"

        messages = [
            ChatMessage(role="system", content=_SYSTEM_ANGLE + extra),
            ChatMessage(role="user", content=user_content),
        ]
        result = await client.chat(messages=messages, model=model, temperature=0.35, max_tokens=3500, json_mode=True)
        parsed = parse_json_loose(result.text)
        if not parsed:
            last_error = ValueError("角度陌生化输出格式不符合 schema")
            logger.warning("角度陌生化第 %d/%d 次输出解析失败: %s", attempt, MAX_RETRIES, result.text[:300])
            continue
        return AngleAuditOutput(**parsed)

    raise last_error


async def audit_rhythm(
    topic: SelectedTopicInput,
    angle_audit: AngleAuditOutput,
    *,
    llm_client: Optional[LLMClient] = None,
    model: Optional[str] = None,
) -> RhythmAuditOutput:
    """第三关：节奏设计检查。Schema 校验失败时自动重试，最多 3 次。"""
    client = llm_client or get_llm_client()

    user_content = f"""【输入选题】
{_topic_json(topic)}

【角度检验结果】
{json.dumps(angle_audit.model_dump(), ensure_ascii=False, indent=2)}

【检查要求】
1. 设计情绪地图，避免平线。
2. 如果适合多案例/多轮故事，给升番排布。
3. 设计 3 秒内抓人的开头钩子。
4. 设计结尾余震，不能只是总结全文。
5. 如果适合多段式结构，给段落钩子线。

【输出 JSON】
{{
  "verdict": "🟢 有起伏 / 🟡 勉强可写 / 🔴 平线",
  "emotion_map": "共鸣→小胜→受挫→反转→余韵",
  "rhythm_curve": "对情绪走向的判断",
  "escalation_suggestion": "升番结构建议",
  "opening_hook": "开头钩子建议",
  "ending_aftershock": "结尾余震建议",
  "transition_hooks": ["段落钩子线1", "段落钩子线2"]
}}"""

    last_error = None
    for attempt in range(1, MAX_RETRIES + 1):
        extra = ""
        if attempt > 1:
            extra = "\n\n【重要】上一次输出格式不符合要求。请严格输出 JSON，必须包含 verdict、emotion_map、rhythm_curve、escalation_suggestion、opening_hook、ending_aftershock、transition_hooks 字段。不要输出 markdown 或解释文字。"

        messages = [
            ChatMessage(role="system", content=_SYSTEM_RHYTHM + extra),
            ChatMessage(role="user", content=user_content),
        ]
        result = await client.chat(messages=messages, model=model, temperature=0.35, max_tokens=3500, json_mode=True)
        parsed = parse_json_loose(result.text)
        if not parsed:
            last_error = ValueError("节奏设计输出格式不符合 schema")
            logger.warning("节奏设计第 %d/%d 次输出解析失败: %s", attempt, MAX_RETRIES, result.text[:300])
            continue
        return RhythmAuditOutput(**parsed)

    raise last_error
