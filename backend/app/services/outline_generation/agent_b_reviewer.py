"""Agent B - 大纲评审员。

职责：接收 Agent A 的 3 个候选大纲，选出最有传播潜力的版本，必要时融合多个候选的优点，
并为最终大纲的每一节标注传播角色。
"""

import logging
from pathlib import Path
from typing import List, Optional

from app.services.llm import get_llm_client, LLMClient
from app.services.llm.llm_client import ChatMessage, parse_json_loose
from app.services.outline_generation.schemas import (
    AgentBInput,
    OutlineCandidateItem,
    AgentBOutput,
    SectionWithTags,
)

logger = logging.getLogger(__name__)

PROMPTS_DIR = Path(__file__).parent / "prompts"


def _load_system_prompt() -> str:
    return (PROMPTS_DIR / "agent_b_system.txt").read_text(encoding="utf-8")


def _build_user_prompt(input_data: AgentBInput) -> str:
    candidates_str = ""
    for c in input_data.candidates:
        sections_str = "\n".join(
            f"      节{s.section_number}: {s.title} ({s.word_count}字)\n"
            f"        核心信息点: {', '.join(s.core_points)}"
            for s in c.sections
        )
        candidates_str += f"""
---
候选 {c.candidate_number}:
开头钩子类型: {c.hook_type}
骨架特点: {c.skeleton_feature}
总字数: {c.total_words}
节数: {len(c.sections)}
{sections_str}
---
"""

    return f"""【输入：3 个候选大纲】
选题ID: {input_data.outline_id}
标题: {input_data.title}
方向: {input_data.direction}

候选大纲：
{candidates_str}

【输出格式】
严格输出 JSON，格式如下：
{{
  "selected_candidate": 1,
  "review_reason": "为什么选这个 / 为什么这么融合",
  "sections": [
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


async def review_outline(
    input_data: AgentBInput,
    *,
    llm_client: Optional[LLMClient] = None,
    model: Optional[str] = None,
) -> AgentBOutput:
    """Agent B 主入口：评审候选大纲并补全传播标签。"""
    client = llm_client or get_llm_client()

    system_prompt = _load_system_prompt()
    user_prompt = _build_user_prompt(input_data)

    messages = [
        ChatMessage(role="system", content=system_prompt),
        ChatMessage(role="user", content=user_prompt),
    ]

    logger.info(f"Agent B 开始处理: outline_id={input_data.outline_id}, 候选数={len(input_data.candidates)}")

    result = await client.chat(
        messages=messages,
        model=model,
        temperature=0.3,
        max_tokens=6000,
        json_mode=True,
    )

    parsed = parse_json_loose(result.text)
    if not parsed or "selected_candidate" not in parsed:
        logger.error(f"Agent B 输出解析失败: {result.text[:300]}")
        raise ValueError("Agent B 输出格式不符合 schema")

    output = AgentBOutput(**parsed)

    # 校验传播标签完整性
    all_tags = set()
    for section in output.sections:
        all_tags.update(section.propagation_tags)
    
    required_tags = {"开头钩子", "价值密度", "转发理由", "收藏点"}
    missing_tags = required_tags - all_tags
    if missing_tags:
        logger.warning(f"Agent B 缺少必备传播标签: {missing_tags}")

    logger.info(f"Agent B 完成: outline_id={input_data.outline_id}, 选中候选={output.selected_candidate}")
    return output
