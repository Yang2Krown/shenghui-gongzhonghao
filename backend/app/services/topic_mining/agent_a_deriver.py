"""Agent A - 选题衍生员。

职责：接收 1 条 InfoCluster，衍生 3-8 个候选选题（含 4 Persona 评议）。
调用《选题套路库》作为提示词资产。
"""

import logging
from pathlib import Path
from typing import List, Optional

from app.services.llm import get_llm_client, LLMClient
from app.services.llm.llm_client import ChatMessage, parse_json_loose
from app.services.topic_mining.schemas import (
    InfoClusterInput,
    CandidateFromA,
    AgentAOutput,
    PersonaReviewItem,
)

logger = logging.getLogger(__name__)

PROMPTS_DIR = Path(__file__).parent / "prompts"
ASSETS_DIR = Path(__file__).parent / "assets"

# 衍生量约束
DERIVE_LIMITS = {
    "资讯型": (5, 8),
    "实操案例型": (4, 6),
    "观点分享型": (4, 6),
    "教程型": (3, 5),
}


def _load_system_prompt() -> str:
    return (PROMPTS_DIR / "agent_a_system.txt").read_text(encoding="utf-8")


def _load_routine_library() -> str:
    return (ASSETS_DIR / "选题套路库.md").read_text(encoding="utf-8")


def _build_user_prompt(info: InfoClusterInput) -> str:
    elements_str = "\n".join(f"  {k}: {v}" for k, v in info.elements.items()) if info.elements else "  （无）"
    source_str = "\n".join(f"  - {u}" for u in info.source_urls[:5]) if info.source_urls else "  （无）"

    lo, hi = DERIVE_LIMITS.get(info.info_type, (4, 6))

    return f"""【输入信息】
信息ID: {info.cluster_id}
核心标题: {info.core_title}
原文摘要: {info.summary or '（无）'}
信息类型: {info.info_type}
方向: {info.direction or '（待定）'}
要素:
{elements_str}
时效新鲜度: {info.freshness or '未知'}
热度评分: {info.heat_score}
低粉爆款标记: {'是' if info.low_fan_hit else '否'}
来源列表:
{source_str}

【衍生量约束】
本条信息类型为「{info.info_type}」，请衍生 {lo}-{hi} 个候选选题。

【输出格式】
严格输出 JSON，格式如下：
{{
  "candidates": [
    {{
      "candidate_id": "T-001",
      "title": "14-22字标题",
      "direction": "方向",
      "routine": "X.X.X 套路名",
      "dimension_combo": ["维度=值"],
      "value_promise": "价值承诺",
      "angle_note": "切入说明",
      "persona_reviews": [
        {{"persona": "AI专家", "score": 8, "rationale": "..."}},
        {{"persona": "百万粉博主", "score": 9, "rationale": "..."}},
        {{"persona": "产品经理", "score": 7, "rationale": "..."}},
        {{"persona": "运营专家", "score": 8, "rationale": "..."}}
      ],
      "persona_divergence": 2.0,
      "persona_divergence_flag": false
    }}
  ]
}}"""


async def _attempt_derive(
    info: InfoClusterInput,
    client: LLMClient,
    model: Optional[str],
    system_full: str,
    user_prompt: str,
    extra_hint: str = "",
) -> List[CandidateFromA]:
    """单次 derive 尝试：调 LLM + 解析 + Pydantic 校验。失败抛异常。"""
    messages = [
        ChatMessage(role="system", content=system_full + extra_hint),
        ChatMessage(role="user", content=user_prompt),
    ]
    result = await client.chat(
        messages=messages,
        model=model,
        temperature=0.4,
        max_tokens=6000,
        json_mode=True,
    )

    parsed = parse_json_loose(result.text)
    if not parsed or "candidates" not in parsed:
        raise ValueError(f"Agent A 输出格式不符合 schema: {result.text[:200]}")

    # 兼容 LLM 返回的 persona_reviews 变体字段名
    for cand in parsed.get("candidates", []):
        if "persona_reviews" in cand:
            cand["persona_reviews"] = [
                PersonaReviewItem.from_llm_output(pr).model_dump()
                for pr in cand["persona_reviews"]
            ]
    output = AgentAOutput(**parsed)
    return output.candidates


async def derive_candidates(
    info: InfoClusterInput,
    *,
    llm_client: Optional[LLMClient] = None,
    model: Optional[str] = None,
) -> List[CandidateFromA]:
    """Agent A 主入口：从 1 条信息衍生候选选题列表。

    对齐设计文档 4.2 节异常处理：
    - schema 不符 → 重试 1 次，仍失败抛
    - 衍生数量低于下限 → 重试 1 次，仍不足则降级返回已有候选
    """
    client = llm_client or get_llm_client()
    system_prompt = _load_system_prompt()
    routine_lib = _load_routine_library()
    user_prompt = _build_user_prompt(info)
    system_full = system_prompt + "\n\n【参考资产】\n《选题套路库》完整内容：\n" + routine_lib

    lo, hi = DERIVE_LIMITS.get(info.info_type, (4, 6))
    logger.info(f"Agent A 开始处理: cluster_id={info.cluster_id}, type={info.info_type}, expect {lo}-{hi}")

    # 第一次：schema 失败允许重试 1 次
    try:
        candidates = await _attempt_derive(info, client, model, system_full, user_prompt)
    except ValueError as e:
        logger.warning(f"Agent A schema 失败，重试 1 次: {e}")
        candidates = await _attempt_derive(
            info, client, model, system_full, user_prompt,
            extra_hint="\n\n【重要】上次输出格式不对，请严格按 JSON schema 输出 candidates 数组。",
        )

    # 数量低于下限 → 重试 1 次（要求模型补足）
    if len(candidates) < lo:
        logger.warning(f"Agent A 衍生数量 {len(candidates)} 低于下限 {lo}，重试补足")
        try:
            retry = await _attempt_derive(
                info, client, model, system_full, user_prompt,
                extra_hint=f"\n\n【重要】上次只衍生 {len(candidates)} 个，必须达到 {lo}-{hi} 个。请补足多角度候选。",
            )
            # 用新结果如果数量更多就替换
            if len(retry) > len(candidates):
                candidates = retry
        except Exception as e:
            logger.warning(f"Agent A 补足重试失败，降级返回 {len(candidates)} 个: {e}")

    logger.info(f"Agent A 完成: cluster_id={info.cluster_id}, 衍生 {len(candidates)} 个候选")
    return candidates
