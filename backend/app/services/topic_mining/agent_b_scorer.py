"""Agent B - 选题评分员。

职责：接收 Agent A 的候选列表，按《选题评分卡》进行一票否决 + 6 维度评分 + 入选判定。
"""

import logging
from pathlib import Path
from typing import List, Optional

from app.services.llm import get_llm_client, LLMClient
from app.services.llm.llm_client import ChatMessage, parse_json_loose
from app.services.topic_mining.schemas import (
    AgentBInput,
    CandidateFromA,
    CandidateScored,
    AgentBOutput,
    PersonaReviewItem,
)

logger = logging.getLogger(__name__)

PROMPTS_DIR = Path(__file__).parent / "prompts"
ASSETS_DIR = Path(__file__).parent / "assets"

# 权重
WEIGHTS = {
    "pain_point": 0.20,
    "value_density": 0.20,
    "propagation": 0.15,
    "differentiation": 0.15,
    "freshness": 0.10,
    "audience_fit": 0.20,
}

# 判定阈值
THRESHOLD_SELECTED = 7.0
THRESHOLD_BACKUP = 5.0


def _load_system_prompt() -> str:
    return (PROMPTS_DIR / "agent_b_system.txt").read_text(encoding="utf-8")


def _load_score_card() -> str:
    return (ASSETS_DIR / "选题评分卡.md").read_text(encoding="utf-8")


def _build_user_prompt(input_data: AgentBInput) -> str:
    candidates_str = ""
    for c in input_data.candidates:
        reviews_str = "\n".join(
            f"    - {r.persona}: {r.score} - {r.rationale}" for r in c.persona_reviews
        )
        candidates_str += f"""
---
候选ID: {c.candidate_id}
标题: {c.title}
方向: {c.direction}
套路: {c.routine}
维度组合: {', '.join(c.dimension_combo) if c.dimension_combo else '无'}
价值承诺: {c.value_promise}
切入说明: {c.angle_note}
Persona 评议:
{reviews_str}
Persona 分歧度: {c.persona_divergence}{' ⚠️' if c.persona_divergence_flag else ''}
---
"""

    return f"""【输入：候选选题列表】
源信息ID: {input_data.cluster_id}
核心标题: {input_data.core_title}
信息类型: {input_data.info_type}
时效新鲜度: {input_data.freshness or '未知'}

候选选题：
{candidates_str}

【输出格式】
严格输出 JSON，格式如下：
{{
  "candidates": [
    {{
      "candidate_id": "T-001",
      "title": "标题",
      "direction": "方向",
      "routine": "套路",
      "dimension_combo": [],
      "value_promise": "价值承诺",
      "veto_passed": true,
      "veto_reasons": [],
      "pain_point": {{"score": 7, "evidence": "依据"}},
      "value_density": {{"score": 8, "evidence": "依据"}},
      "propagation": {{"score": 8, "evidence": "依据"}},
      "differentiation": {{"score": 7, "evidence": "依据"}},
      "freshness": {{"score": 9, "evidence": "依据"}},
      "audience_fit": {{"score": 9, "evidence": "依据"}},
      "weighted_score": 7.95,
      "verdict": "selected",
      "persona_reviews": [...],
      "persona_divergence": 2.0,
      "persona_divergence_flag": false
    }}
  ]
}}

注意：
- 每个维度必须有 score 和 evidence
- weighted_score 按公式计算：0.20×痛点 + 0.20×价值 + 0.15×传播 + 0.15×差异化 + 0.10×新鲜度 + 0.20×受众
- verdict 根据 weighted_score 判定：>=7.0 → selected, 5.0-7.0 → backup, <5.0 → rejected
- 被一票否决的 verdict 为 "vetoed"
- 保留 persona_reviews、persona_divergence、persona_divergence_flag"""


def _calculate_weighted_score(scored: CandidateScored) -> float:
    """计算加权总分。"""
    return (
        WEIGHTS["pain_point"] * scored.pain_point.score
        + WEIGHTS["value_density"] * scored.value_density.score
        + WEIGHTS["propagation"] * scored.propagation.score
        + WEIGHTS["differentiation"] * scored.differentiation.score
        + WEIGHTS["freshness"] * scored.freshness.score
        + WEIGHTS["audience_fit"] * scored.audience_fit.score
    )


def _determine_verdict(scored: CandidateScored) -> str:
    """判定入选/备选/淘汰。"""
    if not scored.veto_passed:
        return "vetoed"
    if scored.weighted_score >= THRESHOLD_SELECTED:
        return "selected"
    if scored.weighted_score >= THRESHOLD_BACKUP:
        return "backup"
    return "rejected"


async def score_candidates(
    input_data: AgentBInput,
    *,
    llm_client: Optional[LLMClient] = None,
    model: Optional[str] = None,
) -> AgentBOutput:
    """Agent B 主入口：对候选选题列表评分。"""
    client = llm_client or get_llm_client()

    system_prompt = _load_system_prompt()
    score_card = _load_score_card()
    user_prompt = _build_user_prompt(input_data)

    messages = [
        ChatMessage(role="system", content=system_prompt + "\n\n【参考资产】\n《选题评分卡》完整内容：\n" + score_card),
        ChatMessage(role="user", content=user_prompt),
    ]

    logger.info(f"Agent B 开始处理: cluster_id={input_data.cluster_id}, 候选数={len(input_data.candidates)}")

    result = await client.chat(
        messages=messages,
        model=model,
        temperature=0.2,
        max_tokens=8000,
        json_mode=True,
    )

    parsed = parse_json_loose(result.text)
    if not parsed or "candidates" not in parsed:
        logger.error(f"Agent B 输出解析失败: {result.text[:300]}")
        raise ValueError("Agent B 输出格式不符合 schema")

    # 用 Agent A 原始 persona_reviews 覆盖 LLM 输出（防丢 rationale）
    a_reviews_by_id = {c.candidate_id: c.persona_reviews for c in input_data.candidates}
    a_divergence_by_id = {
        c.candidate_id: (c.persona_divergence, c.persona_divergence_flag)
        for c in input_data.candidates
    }
    for cand in parsed.get("candidates", []):
        cid = cand.get("candidate_id", "")
        if cid in a_reviews_by_id:
            cand["persona_reviews"] = [pr.model_dump() for pr in a_reviews_by_id[cid]]
            cand["persona_divergence"], cand["persona_divergence_flag"] = a_divergence_by_id[cid]
        elif "persona_reviews" in cand:
            # 兜底：LLM 输出，归一化字段名
            cand["persona_reviews"] = [
                PersonaReviewItem.from_llm_output(pr).model_dump()
                for pr in cand["persona_reviews"]
            ]

    output = AgentBOutput(**parsed)

    # 二次校验：重新计算 weighted_score 和 verdict
    for scored in output.candidates:
        scored.weighted_score = round(_calculate_weighted_score(scored), 2)
        scored.verdict = _determine_verdict(scored)

    # 统计
    stats = {"total": len(output.candidates)}
    for v in ["selected", "backup", "rejected", "vetoed"]:
        stats[v] = sum(1 for c in output.candidates if c.verdict == v)
    output.stats = stats

    logger.info(
        f"Agent B 完成: cluster_id={input_data.cluster_id}, "
        f"入选={stats['selected']}, 备选={stats['backup']}, 淘汰={stats['rejected']}, 否决={stats['vetoed']}"
    )
    return output
