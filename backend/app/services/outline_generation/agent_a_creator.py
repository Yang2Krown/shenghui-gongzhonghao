"""Agent A - 大纲创作员。

职责：接收 1 条选题，生成 3 个差异化的中粒度大纲候选。
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


# def _load_template_library() -> str:
#     """已禁用：不再依赖模板库，由提示词直接指导 AI 生成。"""
#     return (ASSETS_DIR / "大纲模板库.md").read_text(encoding="utf-8")


def _build_user_prompt(info: OutlineInput) -> str:
    angle_guidance_text = (
        info.creation_guidance.get("prompt_text")
        if info.creation_guidance
        else "【创作角度体检】\n（无）"
    )
    target_words_text = (
        f"{info.target_words} 字（请把这个总字数合理分配到各节，各节 word_count 之和约等于它）"
        if info.target_words
        else "未指定（按内容需要自行决定，总字数 2000-3000）"
    )
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
目标总字数: {target_words_text}

{angle_guidance_text}

【输出格式】
严格输出 JSON，格式如下：
{{
  "candidates": [
    {{
      "candidate_number": 1,
      "hook_type": "痛点共鸣",
      "skeleton_feature": "用一句话描述这个候选的整体叙事思路",
      "sections": [
        {{
          "section_number": 1,
          "part": "intro",
          "title": "小标题",
          "description": "这一节要写什么的人话说明，完整具体、看了就知道怎么落笔",
          "word_count": 300,
          "notes": "备注（可选）"
        }}
      ],
      "total_words": {info.target_words or 2500}
    }}
  ]
}}"""


MAX_RETRIES = 3


async def create_outline_candidates(
    info: OutlineInput,
    *,
    llm_client: Optional[LLMClient] = None,
    model: Optional[str] = None,
) -> List[OutlineCandidateItem]:
    """Agent A 主入口：从 1 条选题生成 3 个候选大纲。

    Schema 校验失败时自动重试，最多 3 次。
    """
    client = llm_client or get_llm_client()

    system_prompt = _load_system_prompt()
    user_prompt = _build_user_prompt(info)

    logger.info(f"Agent A 开始处理: candidate_id={info.candidate_id}, direction={info.direction}")

    last_error = None
    for attempt in range(1, MAX_RETRIES + 1):
        extra_hint = ""
        if attempt > 1:
            extra_hint = (
                "\n\n【重要】上一次输出格式不符合要求。"
                "请严格输出 JSON，必须包含 candidates 数组，每个元素含 candidate_number、"
                "hook_type、skeleton_feature、sections、total_words 字段。"
                "不要输出任何 markdown 标记或解释文字。"
            )

        messages = [
            ChatMessage(role="system", content=system_prompt + extra_hint),
            ChatMessage(role="user", content=user_prompt),
        ]

        result = await client.chat(
            messages=messages,
            model=model,
            temperature=0.4,
            max_tokens=8000,
            json_mode=True,
        )

        parsed = parse_json_loose(result.text)
        if not parsed or "candidates" not in parsed:
            last_error = ValueError("Agent A 输出格式不符合 schema")
            logger.warning(f"Agent A 第 {attempt}/{MAX_RETRIES} 次输出解析失败: {result.text[:300]}")
            continue

        output = AgentAOutput(**parsed)
        candidates = output.candidates

        if len(candidates) != 3:
            logger.warning(f"Agent A 候选数量 {len(candidates)} 不等于 3")

        hook_types = [c.hook_type for c in candidates]
        if len(set(hook_types)) < 3:
            logger.warning(f"Agent A 钩子类型未充分差异化: {hook_types}")

        logger.info(f"Agent A 完成（第 {attempt} 次）: candidate_id={info.candidate_id}, 生成 {len(candidates)} 个候选")
        return candidates

    logger.error(f"[Agent A] {MAX_RETRIES} 次尝试均失败")
    raise last_error
