"""Agent C - 读者挑刺员。

职责：以目标读者身份模拟阅读，找出"会跳读/会划走/觉得无聊"的节，给出修改建议。
"""

import logging
from pathlib import Path
from typing import Optional

from app.services.llm import get_llm_client, LLMClient
from app.services.llm.llm_client import ChatMessage, parse_json_loose
from app.services.outline_generation.schemas import (
    AgentCInput,
    AgentCOutput,
    SectionWithTags,
)

logger = logging.getLogger(__name__)

PROMPTS_DIR = Path(__file__).parent / "prompts"


def _load_system_prompt() -> str:
    return (PROMPTS_DIR / "agent_c_system.txt").read_text(encoding="utf-8")


def _build_user_prompt(input_data: AgentCInput) -> str:
    sections_str = ""
    for s in input_data.sections:
        tags_str = ", ".join(s.propagation_tags) if s.propagation_tags else "无"
        sections_str += f"""
节{s.section_number}: {s.title}
  核心信息点: {', '.join(s.core_points)}
  字数: {s.word_count}
  传播标签: {tags_str}
  备注: {s.notes or '无'}
"""

    return f"""【这篇文章的大纲】
选题ID: {input_data.outline_id}
标题: {input_data.title}

大纲内容：
{sections_str}

【输出格式】
严格输出 JSON，格式如下：
{{
  "overall_feeling": "整体感受（1-2 句话总评）",
  "problem_sections": [
    {{
      "section_number": 2,
      "problem_type": "信息密度低 / 没有新增 / 读起来累 / 跳脱主线",
      "feedback": "具体反馈",
      "suggestion": "修改建议"
    }}
  ],
  "revised_sections": [
    {{
      "section_number": 1,
      "title": "小标题",
      "core_points": ["核心信息点1", "核心信息点2"],
      "word_count": 350,
      "propagation_tags": ["开头钩子", "痛点共鸣"],
      "notes": "备注"
    }}
  ]
}}"""


MAX_RETRIES = 3


async def criticize_outline(
    input_data: AgentCInput,
    *,
    llm_client: Optional[LLMClient] = None,
    model: Optional[str] = None,
) -> AgentCOutput:
    """Agent C 主入口：以读者视角挑刺并修订大纲。

    Schema 校验失败时自动重试，最多 3 次。
    """
    client = llm_client or get_llm_client()

    system_prompt = _load_system_prompt()
    user_prompt = _build_user_prompt(input_data)

    logger.info(f"Agent C 开始处理: outline_id={input_data.outline_id}")

    last_error = None
    for attempt in range(1, MAX_RETRIES + 1):
        extra_hint = ""
        if attempt > 1:
            extra_hint = (
                "\n\n【重要】上一次输出格式不符合要求。"
                "请严格输出 JSON，必须包含 overall_feeling、problem_sections、revised_sections 字段。"
                "不要输出任何 markdown 标记或解释文字。"
            )

        messages = [
            ChatMessage(role="system", content=system_prompt + extra_hint),
            ChatMessage(role="user", content=user_prompt),
        ]

        result = await client.chat(
            messages=messages,
            model=model,
            temperature=0.5,
            max_tokens=6000,
            json_mode=True,
        )

        parsed = parse_json_loose(result.text)
        if not parsed or "overall_feeling" not in parsed:
            last_error = ValueError("Agent C 输出格式不符合 schema")
            logger.warning(f"Agent C 第 {attempt}/{MAX_RETRIES} 次输出解析失败: {result.text[:300]}")
            continue

        output = AgentCOutput(**parsed)

        if "不想看" in output.overall_feeling or "关了" in output.overall_feeling:
            logger.warning(f"Agent C 反馈全篇都不想看: {output.overall_feeling}")

        logger.info(f"Agent C 完成（第 {attempt} 次）: outline_id={input_data.outline_id}, 问题节数={len(output.problem_sections)}")
        return output

    logger.error(f"[Agent C] {MAX_RETRIES} 次尝试均失败")
    raise last_error
