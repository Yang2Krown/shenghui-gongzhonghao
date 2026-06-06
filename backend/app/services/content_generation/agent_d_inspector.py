"""Agent D — 事实总结员。

职责：扫描正文 + 金句中的事实性陈述，提取可能因 LLM 训练集截止而产生的错误。
输出：潜在事实性错误清单 + 建议搜索关键词，供 Agent E (Kimi 联网纠错) 使用。
"""

import logging
from typing import Optional
from pathlib import Path

from app.services.llm import get_llm_client
from app.services.llm.llm_client import ChatMessage, parse_json_loose
from app.services.content_generation.schemas import (
    AgentAOutput,
    AgentBOutput,
    AgentDOutput,
    PotentialFactualError,
    ContentGenerationInput,
)

logger = logging.getLogger(__name__)

CURRENT_DIR = Path(__file__).parent

# ──────────────────────────────────────────────
# 提示词模板
# ──────────────────────────────────────────────

def _load_system_prompt() -> str:
    """从文件加载系统提示词"""
    prompt_file = CURRENT_DIR / "prompts" / "agent_d_system.txt"
    if prompt_file.exists():
        return prompt_file.read_text(encoding="utf-8")
    # 回退到硬编码版本
    return """\
你是一位事实核查专家。你的任务是扫描公众号正文和金句，找出所有可能因大模型训练集时间截止而产生错误的事实性陈述。

【你需要重点检查的错误类型】

1. 时间/日期类：具体的发布日期、上线时间、事件发生时间（如"2024年3月发布"可能已过时）
2. 产品名/版本号：软件版本、模型名称（如"GPT-4"可能已出新版、"Claude 3"可能已更名）
3. 数据/统计：用户数、市场份额、价格、性能指标（这类数据变化很快）
4. 人名/职位：公司高管、技术负责人（人事变动频繁）
5. 机构/公司：公司名、产品线（可能已更名、合并、关闭）
6. 价格信息：API 价格、订阅费用（调价频繁）
7. 技术规格：参数量、上下文长度、支持的功能（迭代快）

【你不应该标记的内容】
- 通用观点、评论、分析（不需要事实核查）
- 修辞手法、比喻、金句中的夸张表达
- 历史公认事实（如"iPhone 于 2007 年发布"）
- 正文作者的主观判断

【输出要求】
- 对每个潜在错误，给出一个精确的搜索关键词（用于联网验证）
- 搜索关键词要具体，能直接搜到权威信息
- 如果全文没有可疑事实，输出空列表（这是正常的，不要硬凑）
"""


def _build_user_prompt(
    inp: ContentGenerationInput,
    agent_a_output: AgentAOutput,
    agent_b_output: AgentBOutput,
) -> str:
    """构建用户提示词。"""
    lines = []

    # 选题标题
    lines.append(f"【选题标题】{inp.topic_title}")
    lines.append("")

    # 正文全文（Agent A 的原始输出）
    lines.append("【正文】")
    lines.append(agent_a_output.full_text)
    lines.append("")

    # 金句清单
    lines.append("【金句清单】")
    for s in agent_b_output.sentences:
        lines.append(f"- [{s.sentence_type}] 第{s.section_number}节 {s.location}: \"{s.content}\"")
    lines.append("")

    # 输出格式
    lines.append("【输出格式】")
    lines.append("请严格按以下 JSON 格式输出：")
    lines.append("""```json
{
  "summary_text": "对正文中事实性内容的整体判断（1-3句话）",
  "potential_errors": [
    {
      "claim": "正文中的一句事实性陈述（原文引用）",
      "error_type": "产品名",
      "section_number": 2,
      "reason": "该产品可能已发布新版本或更名",
      "search_query": "产品名 最新版本 2026"
    }
  ],
  "total_claims_checked": 15,
  "error_count": 3
}
```""")

    return "\n".join(lines)


def _parse_llm_output(raw: dict) -> AgentDOutput:
    """解析 LLM 输出为 AgentDOutput。"""
    errors = []
    for item in raw.get("potential_errors", []):
        errors.append(PotentialFactualError(
            claim=item.get("claim", ""),
            error_type=item.get("error_type", "其他"),
            section_number=item.get("section_number", 0),
            reason=item.get("reason", ""),
            search_query=item.get("search_query", ""),
        ))

    return AgentDOutput(
        summary_text=raw.get("summary_text", ""),
        potential_errors=errors,
        total_claims_checked=raw.get("total_claims_checked", 0),
        error_count=raw.get("error_count", len(errors)),
    )


MAX_RETRIES = 3


async def summarize_factual_errors(
    inp: ContentGenerationInput,
    agent_a_output: AgentAOutput,
    agent_b_output: AgentBOutput,
    provider: Optional[str] = None,
) -> AgentDOutput:
    """Agent D 主入口：总结正文 + 金句中的潜在事实性错误。

    Args:
        inp: 正文生成总输入
        agent_a_output: Agent A 的输出（正文骨干）
        agent_b_output: Agent B 的输出（金句清单）
        provider: LLM provider 名称（可选，默认使用 settings.LLM_PROVIDER）

    Returns:
        AgentDOutput: 事实总结报告
    """
    client = get_llm_client(provider)
    user_prompt = _build_user_prompt(inp, agent_a_output, agent_b_output)
    system_prompt = _load_system_prompt()

    logger.info("[Agent D] 开始事实性错误扫描")

    last_error = None
    for attempt in range(1, MAX_RETRIES + 1):
        extra_hint = ""
        if attempt > 1:
            extra_hint = (
                "\n\n【重要】上一次输出格式不符合要求。"
                "请严格输出 JSON，必须包含 summary_text、potential_errors 数组、"
                "total_claims_checked、error_count 字段。"
                "不要输出任何 markdown 标记或解释文字。"
            )

        messages = [
            ChatMessage(role="system", content=system_prompt + extra_hint),
            ChatMessage(role="user", content=user_prompt),
        ]

        result = await client.chat(
            messages=messages,
            temperature=0.2,
            max_tokens=4000,
            json_mode=True,
        )

        parsed = parse_json_loose(result.text)
        if parsed and "potential_errors" not in parsed:
            for alias in ("errors", "issues", "claims", "问题", "错误"):
                if alias in parsed and isinstance(parsed[alias], list):
                    logger.warning(f"[Agent D] LLM 用了别名 key '{alias}'，已映射到 potential_errors")
                    parsed["potential_errors"] = parsed[alias]
                    break

        if not parsed or "summary_text" not in parsed:
            last_error = ValueError("Agent D 输出格式不符合 schema")
            logger.warning(
                f"[Agent D] 第 {attempt}/{MAX_RETRIES} 次输出解析失败 "
                f"(len={len(result.text or '')}): "
                f"parsed_keys={list(parsed.keys()) if isinstance(parsed, dict) else type(parsed).__name__}, "
                f"原始响应前 800 字: {(result.text or '')[:800]!r}"
            )
            continue

        output = _parse_llm_output(parsed)
        logger.info(
            f"[Agent D] 事实扫描完成（第 {attempt} 次），"
            f"检查陈述: {output.total_claims_checked}，"
            f"潜在错误: {output.error_count}"
        )
        return output

    logger.error(f"[Agent D] {MAX_RETRIES} 次尝试均失败")
    raise last_error
