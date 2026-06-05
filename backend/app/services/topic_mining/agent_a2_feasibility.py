"""Agent A2 - 选题可写性审计员。

职责：接收 Agent A 的候选列表，通过联网搜索验证每个选题的可写性。
使用 Moonshot（Kimi）API + $web_search 联网搜索工具。

设计思路：
- Agent A 按套路模板衍生选题，但不验证选题内容是否成立
- Agent A2 用联网搜索验证选题的核心声称是否真实
- 不合格的选题会被标记为 fail，后续不进入 Agent B 评分
"""

import logging
from pathlib import Path
from typing import List, Optional

from app.services.llm import get_llm_client, LLMClient
from app.services.llm.llm_client import ChatMessage, parse_json_loose
from app.services.topic_mining.schemas import (
    AgentA2Input,
    AgentA2Output,
    CandidateFeasibility,
    FeasibilityEvidence,
)

logger = logging.getLogger(__name__)

PROMPTS_DIR = Path(__file__).parent / "prompts"

# 可写性门槛
FEASIBILITY_THRESHOLD_PASS = 7.0
FEASIBILITY_THRESHOLD_WEAK = 5.0

MAX_RETRIES = 3


def _load_system_prompt() -> str:
    return (PROMPTS_DIR / "agent_a2_system.txt").read_text(encoding="utf-8")


def _build_user_prompt(input_data: AgentA2Input) -> str:
    candidates_str = ""
    for c in input_data.candidates:
        reviews_str = "\n".join(
            f"    - {r.persona}: {r.score} - {r.rationale}" for r in c.persona_reviews
        )
        candidates_str += f"""
---
候选ID: {c.candidate_id}
标题: {c.title}
原始简介: {c.summary or '（无）'}
方向: {c.direction}
套路: {c.routine}
价值承诺: {c.value_promise}
切入说明: {c.angle_note}
Persona 评议:
{reviews_str}
---
"""

    source_str = "\n".join(f"  - {u}" for u in input_data.source_urls[:5]) if input_data.source_urls else "  （无）"

    return f"""【输入：待审计的候选选题列表】
源信息ID: {input_data.cluster_id}
核心标题: {input_data.core_title}
信息类型: {input_data.info_type}
原文摘要: {input_data.summary or '（无）'}
来源列表:
{source_str}

候选选题（来自 Agent A 衍生）：
{candidates_str}

【你的任务】
对每个候选选题执行可写性审计：
1. 拆解选题的核心声称
2. 用联网搜索验证这些声称
3. 给出可写性判定

请先对每个选题分析需要搜索什么，然后执行搜索，最后综合判断。

【输出格式】
严格输出 JSON，格式如下：
{{
  "candidates": [
    {{
      "candidate_id": "T-001",
      "title": "原标题",
      "feasibility_score": 8.0,
      "feasibility_passed": true,
      "verdict": "pass",
      "search_queries": ["实际搜索的关键词1", "关键词2"],
      "evidence": [
        {{"source": "来源", "snippet": "关键摘录", "supports": true}}
      ],
      "reasoning": "判断理由",
      "rewrite_suggestion": null
    }}
  ]
}}

注意：
- verdict 必须是 pass / weak_pass / fail 之一
- feasibility_score >= 7.0 → pass, 5.0-7.0 → weak_pass, < 5.0 → fail
- search_queries 列出你实际搜索的关键词
- evidence 基于搜索结果填写，不要编造
- fail/weak_pass 时 rewrite_suggestion 必须给出具体改写建议"""


async def _attempt_audit(
    input_data: AgentA2Input,
    client: LLMClient,
    model: Optional[str],
    system_full: str,
    user_prompt: str,
    extra_hint: str = "",
) -> List[CandidateFeasibility]:
    """单次审计尝试。"""
    messages = [
        ChatMessage(role="system", content=system_full + extra_hint),
        ChatMessage(role="user", content=user_prompt),
    ]

    # 判断是否为 Moonshot client（支持 web_search）
    from app.services.llm.moonshot_client import MoonshotClient
    use_web_search = isinstance(client, MoonshotClient)

    result = await client.chat(
        messages=messages,
        model=model,
        temperature=0.2,
        max_tokens=6000,
        json_mode=not use_web_search,  # Moonshot 用 tool_calls 时不用 json_mode
        web_search=use_web_search,
    )

    parsed = parse_json_loose(result.text)
    if not parsed or "candidates" not in parsed:
        raise ValueError(f"Agent A2 输出格式不符合 schema: {result.text[:200]}")

    # Pydantic 校验
    candidates = []
    for cand in parsed["candidates"]:
        # 兼容 evidence 字段缺失
        if "evidence" not in cand:
            cand["evidence"] = []
        # 兼容 search_queries 字段缺失
        if "search_queries" not in cand:
            cand["search_queries"] = []
        candidates.append(CandidateFeasibility(**cand))

    return candidates


async def audit_feasibility(
    input_data: AgentA2Input,
    *,
    llm_client: Optional[LLMClient] = None,
    model: Optional[str] = None,
) -> AgentA2Output:
    """Agent A2 主入口：对候选选题列表进行可写性审计。

    使用 Moonshot API + 联网搜索验证选题的可写性。
    Schema 校验失败时自动重试，最多 3 次。
    """
    # 默认用 Moonshot client（联网搜索）
    if llm_client is None:
        from app.services.llm.moonshot_client import MoonshotClient
        try:
            client = MoonshotClient()
        except RuntimeError:
            logger.warning("Moonshot API 未配置，Agent A2 跳过可写性审计，全部 pass")
            return _build_passthrough_output(input_data)
    else:
        client = llm_client

    system_prompt = _load_system_prompt()
    user_prompt = _build_user_prompt(input_data)

    logger.info(
        f"Agent A2 开始处理: cluster_id={input_data.cluster_id}, "
        f"候选数={len(input_data.candidates)}"
    )

    candidates = None
    last_error = None
    for attempt in range(1, MAX_RETRIES + 1):
        extra_hint = ""
        if attempt > 1:
            extra_hint = (
                "\n\n【重要】上一次输出格式不符合要求。"
                "请严格输出 JSON，必须包含 candidates 数组，每个候选含 "
                "candidate_id、title、feasibility_score、feasibility_passed、"
                "verdict、search_queries、evidence、reasoning 字段。"
                "不要输出任何 markdown 标记或解释文字。"
            )
        try:
            candidates = await _attempt_audit(
                input_data, client, model, system_prompt, user_prompt, extra_hint
            )
            break
        except (ValueError, Exception) as e:
            last_error = e
            logger.warning(f"Agent A2 第 {attempt}/{MAX_RETRIES} 次失败: {e}")
            continue

    if candidates is None:
        logger.error(f"[Agent A2] {MAX_RETRIES} 次尝试均失败，降级为全部 pass")
        return _build_passthrough_output(input_data)

    # 二次校验：确保 verdict 与 score 一致
    for cand in candidates:
        if cand.feasibility_score >= FEASIBILITY_THRESHOLD_PASS:
            if cand.verdict != "pass":
                cand.verdict = "pass"
            cand.feasibility_passed = True
        elif cand.feasibility_score >= FEASIBILITY_THRESHOLD_WEAK:
            if cand.verdict not in ("pass", "weak_pass"):
                cand.verdict = "weak_pass"
            cand.feasibility_passed = False
        else:
            if cand.verdict != "fail":
                cand.verdict = "fail"
            cand.feasibility_passed = False

    # 统计
    stats = {"total": len(candidates)}
    stats["passed"] = sum(1 for c in candidates if c.verdict == "pass")
    stats["weak_pass"] = sum(1 for c in candidates if c.verdict == "weak_pass")
    stats["failed"] = sum(1 for c in candidates if c.verdict == "fail")

    logger.info(
        f"Agent A2 完成: cluster_id={input_data.cluster_id}, "
        f"通过={stats['passed']}, 弱通过={stats['weak_pass']}, 失败={stats['failed']}"
    )

    return AgentA2Output(candidates=candidates, stats=stats)


def _build_passthrough_output(input_data: AgentA2Input) -> AgentA2Output:
    """降级：Moonshot 未配置时，所有选题默认 pass。"""
    candidates = []
    for c in input_data.candidates:
        candidates.append(CandidateFeasibility(
            candidate_id=c.candidate_id,
            title=c.title,
            enriched_summary=c.summary or "",
            feasibility_score=7.0,
            feasibility_passed=True,
            verdict="pass",
            search_queries=[],
            evidence=[],
            reasoning="Moonshot API 未配置，跳过可写性审计，默认通过",
            rewrite_suggestion=None,
        ))
    return AgentA2Output(
        candidates=candidates,
        stats={"total": len(candidates), "passed": len(candidates), "weak_pass": 0, "failed": 0},
    )
