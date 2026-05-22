"""Agent A - 大纲创作员。

职责：接收 1 条选题，生成 3 个差异化的中粒度大纲候选。
调用《大纲模板库》作为提示词资产。
"""

import logging
from pathlib import Path
from typing import List, Optional

from app.services.llm import get_llm_client, LLMClient
from app.services.llm.llm_client import ChatMessage, parse_json_loose
from app.services.outline_generation.schemas import (
    OutlineInput,
    OutlineCandidateItem,
    AgentAOutput,
)

logger = logging.getLogger(__name__)

PROMPTS_DIR = Path(__file__).parent / "prompts"
ASSETS_DIR = Path(__file__).parent / "assets"


def _load_system_prompt() -> str:
    return (PROMPTS_DIR / "agent_a_system.txt").read_text(encoding="utf-8")


def _load_template_library() -> str:
    return (ASSETS_DIR / "大纲模板库.md").read_text(encoding="utf-8")


def _build_user_prompt(info: OutlineInput) -> str:
    return f"""【输入选题】
选题ID: {info.candidate_id}
标题: {info.title}
方向: {info.direction}
套路: {info.routine or '（无）'}
价值承诺: {info.value_promise or '（无）'}
切入说明: {info.angle_note or '（无）'}
信息簇ID: {info.info_cluster_id or '（无）'}
核心标题: {info.core_title or '（无）'}
原文摘要: {info.summary or '（无）'}

【模板参考】
请根据选题的方向，从大纲模板库中找到对应的 2-3 个骨架模板作为参考。
至少 1 个候选应基于模板改造，其余可自由发挥。

【输出格式】
严格输出 JSON，格式如下：
{{
  "candidates": [
    {{
      "candidate_number": 1,
      "hook_type": "痛点共鸣",
      "skeleton_feature": "痛点开场 → 替代方案对比 → 局限承认 → 行动指南 → 升华",
      "sections": [
        {{
          "section_number": 1,
          "title": "小标题",
          "core_points": ["核心信息点1", "核心信息点2"],
          "word_count": 350,
          "notes": "备注"
        }}
      ],
      "total_words": 2050
    }}
  ]
}}"""


async def create_outline_candidates(
    info: OutlineInput,
    *,
    llm_client: Optional[LLMClient] = None,
    model: Optional[str] = None,
) -> List[OutlineCandidateItem]:
    """Agent A 主入口：从 1 条选题生成 3 个候选大纲。"""
    client = llm_client or get_llm_client()

    system_prompt = _load_system_prompt()
    template_lib = _load_template_library()
    user_prompt = _build_user_prompt(info)

    messages = [
        ChatMessage(role="system", content=system_prompt + "\n\n【参考资产】\n《大纲模板库》完整内容：\n" + template_lib),
        ChatMessage(role="user", content=user_prompt),
    ]

    logger.info(f"Agent A 开始处理: candidate_id={info.candidate_id}, direction={info.direction}")

    result = await client.chat(
        messages=messages,
        model=model,
        temperature=0.4,
        max_tokens=8000,
        json_mode=True,
    )

    parsed = parse_json_loose(result.text)
    if not parsed or "candidates" not in parsed:
        logger.error(f"Agent A 输出解析失败: {result.text[:300]}")
        raise ValueError("Agent A 输出格式不符合 schema")

    output = AgentAOutput(**parsed)
    candidates = output.candidates

    # 校验候选数量
    if len(candidates) != 3:
        logger.warning(f"Agent A 候选数量 {len(candidates)} 不等于 3")

    # 校验钩子类型差异化
    hook_types = [c.hook_type for c in candidates]
    if len(set(hook_types)) < 3:
        logger.warning(f"Agent A 钩子类型未充分差异化: {hook_types}")

    logger.info(f"Agent A 完成: candidate_id={info.candidate_id}, 生成 {len(candidates)} 个候选")
    return candidates
