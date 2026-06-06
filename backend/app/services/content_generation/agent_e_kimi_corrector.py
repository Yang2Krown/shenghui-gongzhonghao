"""Agent E — Kimi 联网纠错员。

职责：基于 Agent D 的事实性错误清单，调用 Moonshot (Kimi) 联网搜索验证并纠错。
输出：纠错后的完整正文 + 纠错对照表。
"""

import json
import logging
from pathlib import Path

from app.services.llm.llm_client import ChatMessage, parse_json_loose
from app.services.content_generation.schemas import (
    AgentAOutput,
    AgentBOutput,
    AgentDOutput,
    AgentEOutput,
    FactualCorrection,
    ContentGenerationInput,
)

logger = logging.getLogger(__name__)

CURRENT_DIR = Path(__file__).parent

# ──────────────────────────────────────────────
# 提示词模板
# ──────────────────────────────────────────────

def _load_system_prompt() -> str:
    """从文件加载系统提示词"""
    prompt_file = CURRENT_DIR / "prompts" / "agent_e_system.txt"
    if prompt_file.exists():
        return prompt_file.read_text(encoding="utf-8")
    return """\
你是一位事实核查编辑。你的任务是根据联网搜索结果，修正公众号正文中的事实性错误。

【工作原则】

1. 只改事实性错误：时间、产品名、版本号、数据、人名、机构、价格等可验证信息
2. 不改观点、评论、修辞、金句（金句标为不可改）
3. 如果搜索结果证实原文正确，不要修改
4. 如果搜索结果不确定，保持原文不变，在 corrections 中标注置信度为"低"
5. 修改时保持原文风格和语感，不要让修正后的文字显得突兀
6. 修正要精确到具体措辞，不要整段重写

【金句保护】
- 标记为"金句"的句子不允许修改
- 如果金句中有事实性错误，只在 corrections 中指出，但不修改金句文本

【输出要求】
- corrected_text：修正后的完整正文（只改了事实错误，其他保持原样）
- corrections：每处修正的详细记录
- 如果没有任何需要修正的，corrected_text 就是原文，corrections 为空
"""


def _build_user_prompt(
    inp: ContentGenerationInput,
    agent_a_output: AgentAOutput,
    agent_b_output: AgentBOutput,
    agent_d_output: AgentDOutput,
) -> str:
    """构建用户提示词。"""
    lines = []

    # 选题标题
    lines.append(f"【选题标题】{inp.topic_title}")
    lines.append("")

    # 正文全文
    lines.append("【正文】")
    lines.append(agent_a_output.full_text)
    lines.append("")

    # 金句清单（不可改）
    lines.append("【金句清单（不可改段落）】")
    for s in agent_b_output.sentences:
        lines.append(f"- 第{s.section_number}节 {s.location}: \"{s.content}\"")
    lines.append("")

    # Agent D 的事实总结 + 潜在错误
    lines.append("【事实核查任务】")
    lines.append(f"Agent D 的总结：{agent_d_output.summary_text}")
    lines.append("")
    lines.append(f"共发现 {agent_d_output.error_count} 条潜在错误，需要联网验证：")
    for i, err in enumerate(agent_d_output.potential_errors, 1):
        lines.append(f"  {i}. [{err.error_type}] \"{err.claim}\"")
        lines.append(f"     原因：{err.reason}")
        lines.append(f"     搜索关键词：{err.search_query}")
    lines.append("")

    # 输出格式
    lines.append("【输出格式】")
    lines.append("请严格按以下 JSON 格式输出：")
    lines.append("""```json
{
  "corrected_text": "修正后的完整正文（只改事实错误，其他保持原样）",
  "corrections": [
    {
      "original_claim": "原文中的错误陈述",
      "corrected_claim": "纠正后的正确陈述",
      "error_type": "产品名",
      "section_number": 2,
      "search_result": "搜索依据简述",
      "confidence": "高"
    }
  ],
  "search_queries_used": ["实际使用的搜索词1", "搜索词2"],
  "total_corrections": 2,
  "high_confidence_corrections": 1,
  "stats": {
    "claims_verified": 5,
    "claims_corrected": 2,
    "claims_confirmed_correct": 3
  }
}
```""")

    return "\n".join(lines)


def _parse_llm_output(raw: dict, original_text: str) -> AgentEOutput:
    """解析 LLM 输出为 AgentEOutput。"""
    corrections = []
    for item in raw.get("corrections", []):
        corrections.append(FactualCorrection(
            original_claim=item.get("original_claim", ""),
            corrected_claim=item.get("corrected_claim", ""),
            error_type=item.get("error_type", "其他"),
            section_number=item.get("section_number", 0),
            search_result=item.get("search_result", ""),
            confidence=item.get("confidence", "中"),
        ))

    corrected_text = raw.get("corrected_text", original_text)
    stats = raw.get("stats", {})

    return AgentEOutput(
        corrected_text=corrected_text,
        corrected_word_count=len(corrected_text),
        corrections=corrections,
        search_queries_used=raw.get("search_queries_used", []),
        total_corrections=raw.get("total_corrections", len(corrections)),
        high_confidence_corrections=raw.get("high_confidence_corrections",
                                            sum(1 for c in corrections if c.confidence == "高")),
        stats=stats,
    )


MAX_RETRIES = 3


async def kimi_correct_facts(
    inp: ContentGenerationInput,
    agent_a_output: AgentAOutput,
    agent_b_output: AgentBOutput,
    agent_d_output: AgentDOutput,
) -> AgentEOutput:
    """Agent E 主入口：Kimi 联网纠错。

    使用 MoonshotClient 的联网搜索能力，验证并修正事实性错误。
    如果 Moonshot 未配置，回退到普通 LLM（无联网搜索）。

    Args:
        inp: 正文生成总输入
        agent_a_output: Agent A 的输出
        agent_b_output: Agent B 的输出
        agent_d_output: Agent D 的输出（事实总结）

    Returns:
        AgentEOutput: 纠错后的正文 + 纠错对照表
    """
    # 尝试用 Moonshot 客户端（支持联网搜索）
    try:
        from app.services.llm.moonshot_client import MoonshotClient
        client = MoonshotClient()
        use_web_search = True
        logger.info("[Agent E] 使用 Moonshot (Kimi) 联网搜索纠错")
    except RuntimeError:
        logger.warning("[Agent E] Moonshot API 未配置，回退到默认 LLM（无联网搜索）")
        from app.services.llm import get_llm_client
        client = get_llm_client()
        use_web_search = False

    user_prompt = _build_user_prompt(inp, agent_a_output, agent_b_output, agent_d_output)
    system_prompt = _load_system_prompt()

    logger.info(
        f"[Agent E] 开始联网纠错，"
        f"潜在错误: {agent_d_output.error_count}"
    )

    last_error = None
    current_max_tokens = 32000
    for attempt in range(1, MAX_RETRIES + 1):
        extra_hint = ""
        if attempt > 1:
            extra_hint = (
                "\n\n【重要】上一次输出格式不符合要求。"
                "请严格输出 JSON，必须包含 corrected_text 字段（修正后的完整正文字符串），"
                "以及 corrections 数组、search_queries_used、total_corrections、"
                "high_confidence_corrections、stats 字段。"
                "不要输出任何 markdown 标记或解释文字。"
            )

        messages = [
            ChatMessage(role="system", content=system_prompt + extra_hint),
            ChatMessage(role="user", content=user_prompt),
        ]

        # Moonshot 用 tool_calls 时不用 json_mode
        if use_web_search:
            result = await client.chat(
                messages=messages,
                temperature=0.2,
                max_tokens=current_max_tokens,
                json_mode=False,
                web_search=True,  # type: ignore[call-arg]
            )
        else:
            result = await client.chat(
                messages=messages,
                temperature=0.2,
                max_tokens=current_max_tokens,
                json_mode=True,
            )

        # 检测截断，自动增大 max_tokens
        if getattr(result, 'finish_reason', None) == "length":
            logger.warning(f"[Agent E] 输出被截断 (max_tokens={current_max_tokens})，增大重试")
            current_max_tokens = min(current_max_tokens * 2, 65536)
            last_error = ValueError("Agent E 输出被 max_tokens 截断")
            continue

        parsed = parse_json_loose(result.text)
        if parsed and "corrected_text" not in parsed:
            for alias in ("text", "content", "result", "output", "正文"):
                if alias in parsed and isinstance(parsed[alias], str):
                    logger.warning(f"[Agent E] LLM 用了别名 key '{alias}'，已映射到 corrected_text")
                    parsed["corrected_text"] = parsed[alias]
                    break

        if not parsed or not isinstance(parsed.get("corrected_text"), str):
            last_error = ValueError("Agent E 输出格式不符合 schema")
            logger.warning(
                f"[Agent E] 第 {attempt}/{MAX_RETRIES} 次输出解析失败 "
                f"(len={len(result.text or '')}): "
                f"parsed_keys={list(parsed.keys()) if isinstance(parsed, dict) else type(parsed).__name__}, "
                f"原始响应前 800 字: {(result.text or '')[:800]!r}"
            )
            continue

        output = _parse_llm_output(parsed, agent_a_output.full_text)
        logger.info(
            f"[Agent E] 联网纠错完成（第 {attempt} 次），"
            f"纠错数: {output.total_corrections}，"
            f"高置信度: {output.high_confidence_corrections}，"
            f"字数: {output.corrected_word_count}"
        )
        return output

    logger.error(f"[Agent E] {MAX_RETRIES} 次尝试均失败")
    raise last_error
