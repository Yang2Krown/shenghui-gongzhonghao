"""Agent D - 大纲自检员。

职责：按"好大纲 6 特征"给出量化评分，不参与创作。
"""

import logging
from pathlib import Path
from typing import Optional

from app.services.llm import get_llm_client, LLMClient
from app.services.llm.llm_client import ChatMessage, parse_json_loose
from app.services.outline_generation.schemas import (
    AgentDInput,
    AgentDOutput,
    DimensionScore,
    SectionWithTags,
)

logger = logging.getLogger(__name__)

PROMPTS_DIR = Path(__file__).parent / "prompts"


def _load_system_prompt() -> str:
    return (PROMPTS_DIR / "agent_d_system.txt").read_text(encoding="utf-8")


def _build_user_prompt(input_data: AgentDInput) -> str:
    sections_str = ""
    for s in input_data.sections:
        tags_str = ", ".join(s.propagation_tags) if s.propagation_tags else "无"
        sections_str += f"""
节{s.section_number}: {s.title}
  核心信息点: {', '.join(s.core_points)}
  字数: {s.word_count}
  传播标签: {tags_str}
"""

    return f"""【待评分大纲】
选题ID: {input_data.outline_id}
标题: {input_data.title}

大纲内容：
{sections_str}

【输出格式】
严格输出 JSON，格式如下：
{{
  "hook_score": {{"score": 8, "evidence": "评分依据"}},
  "value_ladder_score": {{"score": 9, "evidence": "评分依据"}},
  "rhythm_score": {{"score": 8, "evidence": "评分依据"}},
  "title_scan_score": {{"score": 9, "evidence": "评分依据"}},
  "trigger_score": {{"score": 9, "evidence": "评分依据"}},
  "length_score": {{"score": 10, "evidence": "评分依据"}},
  "total_score": 8.7,
  "verdict": "passed",
  "deduction_reasons": []
}}"""


# 权重
WEIGHTS = {
    "hook": 0.20,
    "value_ladder": 0.20,
    "rhythm": 0.15,
    "title_scan": 0.15,
    "trigger": 0.20,
    "length": 0.10,
}

# 通过门槛
THRESHOLD_PASSED = 7.0


def _calculate_total_score(output: AgentDOutput) -> float:
    """计算加权总分。"""
    return (
        WEIGHTS["hook"] * output.hook_score.score
        + WEIGHTS["value_ladder"] * output.value_ladder_score.score
        + WEIGHTS["rhythm"] * output.rhythm_score.score
        + WEIGHTS["title_scan"] * output.title_scan_score.score
        + WEIGHTS["trigger"] * output.trigger_score.score
        + WEIGHTS["length"] * output.length_score.score
    )


def _determine_verdict(output: AgentDOutput) -> str:
    """判定通过/不通过。"""
    if output.total_score >= THRESHOLD_PASSED:
        return "passed"
    return "failed"


async def inspect_outline(
    input_data: AgentDInput,
    *,
    llm_client: Optional[LLMClient] = None,
    model: Optional[str] = None,
) -> AgentDOutput:
    """Agent D 主入口：对大纲进行自检评分。"""
    client = llm_client or get_llm_client()

    system_prompt = _load_system_prompt()
    user_prompt = _build_user_prompt(input_data)

    messages = [
        ChatMessage(role="system", content=system_prompt),
        ChatMessage(role="user", content=user_prompt),
    ]

    logger.info(f"Agent D 开始处理: outline_id={input_data.outline_id}")

    result = await client.chat(
        messages=messages,
        model=model,
        temperature=0.2,
        max_tokens=4000,
        json_mode=True,
    )

    parsed = parse_json_loose(result.text)
    if not parsed or "total_score" not in parsed:
        logger.error(f"Agent D 输出解析失败: {result.text[:300]}")
        raise ValueError("Agent D 输出格式不符合 schema")

    output = AgentDOutput(**parsed)

    # 二次校验：重新计算总分和判定
    output.total_score = round(_calculate_total_score(output), 2)
    output.verdict = _determine_verdict(output)

    # 如果不通过，确保有扣分理由
    if output.verdict == "failed" and not output.deduction_reasons:
        logger.warning(f"Agent D 判定不通过但无扣分理由")

    logger.info(f"Agent D 完成: outline_id={input_data.outline_id}, 总分={output.total_score}, 判定={output.verdict}")
    return output
