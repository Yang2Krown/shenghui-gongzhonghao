"""Agent D — 整合 + 自检诊断员。

职责：把金句精准嵌入、做 8 维度自检评分、输出诊断报告。
设计对齐：《正文生成 Agent 设计文档 v1.1》第 5 节。
"""

import logging
from typing import List, Dict, Any
from pathlib import Path

from app.services.llm import get_llm_client
from app.services.llm.llm_client import ChatMessage, parse_json_loose
from app.services.content_generation.schemas import (
    AgentAOutput,
    AgentBOutput,
    AgentCOutput,
    AgentDOutput,
    DimensionScore,
    ContentGenerationInput,
    ContentGenerationOutput,
    GoldSentence,
)

logger = logging.getLogger(__name__)

# 获取当前文件所在目录
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
你是正文生成的最后一道工序——整合 + 自检诊断员。

【你的工作（3 步）】

Step 1 - 金句嵌入复核
检查去 AI 味后的正文中，所有金句是否在正确位置。如发现遗失或位置错误，补正。

Step 2 - 8 维度自检评分
对最终正文按以下 8 个维度打分（0-10）：

| 维度 | 权重 | 评分依据 |
|------|------|---------|
| 标题承诺兑现度 | 20% | 标题说的事正文里都给到了吗 |
| 大纲结构对应度 | 15% | 每节是否按大纲展开 |
| 字数合规 | 10% | 总字数 + 单节字数是否合规 |
| 风格统一性 | 15% | 全文语气是否一致 |
| 去 AI 味彻底度 | 15% | 是否还有残留的 AI 味 |
| 金句完整度 | 10% | 3-5 个金句是否到位、分布是否合理 |
| 开头质量 | 10% | 前 200 字是否抓人 |
| 结尾升华度 | 5% | 是否避免烂尾 |

评分锚点：
- 9-10：优秀，无明显问题
- 7-8：良好，有小瑕疵
- 4-6：一般，有明显问题
- 1-3：差，严重问题

Step 3 - 输出诊断报告
- 各维度分数 + 评价
- 每个扣分点的具体改进建议
- 总结建议（高/中/低优先级修改）
- 处理路径建议（接受发布 / 局部手改 / 整篇重写）

【重要】
- 不触发任何重生——决策权 100% 在人工
- 评分要客观，不要因为是 AI 生成就放宽标准
"""


def _build_user_prompt(
    inp: ContentGenerationInput,
    agent_a_output: AgentAOutput,
    agent_b_output: AgentBOutput,
    agent_c_output: AgentCOutput,
) -> str:
    """构建用户提示词。"""
    lines = []

    # 选题和标题
    lines.append(f"【选题标题】{inp.topic_title}")
    if inp.value_promise:
        lines.append(f"【价值承诺】{inp.value_promise}")
    lines.append("")

    # 大纲
    lines.append("【大纲】")
    for sec in inp.sections:
        lines.append(f"第{sec.section_number}节: {sec.subtitle}（字数预估: {sec.word_estimate}）")
    lines.append("")

    # 金句清单
    lines.append("【金句清单】")
    for s in agent_b_output.sentences:
        lines.append(f"- [{s.sentence_type}] 第{s.section_number}节 {s.location}: \"{s.content}\"")
    lines.append("")

    # 去 AI 味后的正文
    lines.append("【去 AI 味后的正文】")
    lines.append(agent_c_output.rewritten_text)
    lines.append("")

    # Agent A 的风格锚点
    lines.append(f"【风格锚点】{agent_a_output.style_anchor}")
    lines.append("")

    # Agent C 的改写统计
    lines.append(f"【去 AI 味统计】改写处数: {len(agent_c_output.rewrite_table)}，字数变化: {agent_c_output.word_change_pct}%")
    lines.append("")

    # 输出格式
    lines.append("【输出格式】")
    lines.append("请严格按以下 JSON 格式输出：")
    lines.append("""```json
{
  "final_text": "最终正文（含金句嵌入的完整正文）",
  "dimensions": {
    "title_fulfillment": {
      "score": 9,
      "weight": 0.20,
      "evaluation": "标题承诺的'3个能力'在正文第3节明确兑现",
      "suggestions": []
    },
    "outline_alignment": {
      "score": 8,
      "weight": 0.15,
      "evaluation": "5节大纲全部对应",
      "suggestions": ["第4节偏短，建议补充案例"]
    },
    "word_compliance": {
      "score": 8,
      "weight": 0.10,
      "evaluation": "2620字，达到目标",
      "suggestions": []
    },
    "style_consistency": {
      "score": 7,
      "weight": 0.15,
      "evaluation": "整体一致，但有1处书面体残留",
      "suggestions": ["第4节第5段：'对于使用者来说' → '对用户来说'"]
    },
    "deai_thoroughness": {
      "score": 8,
      "weight": 0.15,
      "evaluation": "Agent C净化效果好，残留2处⚪项",
      "suggestions": ["第2节：'非常实用' → 改成具体说明"]
    },
    "gold_sentence_completeness": {
      "score": 8,
      "weight": 0.10,
      "evaluation": "4个金句到位，分布合理",
      "suggestions": []
    },
    "opening_quality": {
      "score": 7,
      "weight": 0.10,
      "evaluation": "前200字进入具体场景，但少了数字冲击",
      "suggestions": ["加入具体数字"]
    },
    "ending_quality": {
      "score": 6,
      "weight": 0.05,
      "evaluation": "结尾偏总结性，缺少升华",
      "suggestions": ["加1句开放问题或行业判断"]
    }
  },
  "high_priority": [],
  "medium_priority": ["结尾升华", "第4节书面体残留"],
  "low_priority": ["开头加数字", "第2节程度副词残留"],
  "recommended_action": "局部手改"
}
```""")

    return "\n".join(lines)


def _calculate_weighted_score(dimensions: Dict[str, DimensionScore]) -> float:
    """计算加权总分。"""
    total = 0.0
    for dim in dimensions.values():
        total += dim.score * dim.weight
    return round(total, 1)


def _parse_llm_output(
    raw: dict,
    inp: ContentGenerationInput,
    agent_a_output: AgentAOutput,
    agent_b_output: AgentBOutput,
    agent_c_output: AgentCOutput,
) -> AgentDOutput:
    """解析 LLM 输出为 AgentDOutput。"""
    dims = raw.get("dimensions", {})

    def _parse_dim(key: str, default_weight: float) -> DimensionScore:
        d = dims.get(key, {})
        return DimensionScore(
            score=d.get("score", 5),
            weight=d.get("weight", default_weight),
            evaluation=d.get("evaluation", ""),
            suggestions=d.get("suggestions", []),
        )

    title_fulfillment = _parse_dim("title_fulfillment", 0.20)
    outline_alignment = _parse_dim("outline_alignment", 0.15)
    word_compliance = _parse_dim("word_compliance", 0.10)
    style_consistency = _parse_dim("style_consistency", 0.15)
    deai_thoroughness = _parse_dim("deai_thoroughness", 0.15)
    gold_sentence_completeness = _parse_dim("gold_sentence_completeness", 0.10)
    opening_quality = _parse_dim("opening_quality", 0.10)
    ending_quality = _parse_dim("ending_quality", 0.05)

    all_dims = {
        "title_fulfillment": title_fulfillment,
        "outline_alignment": outline_alignment,
        "word_compliance": word_compliance,
        "style_consistency": style_consistency,
        "deai_thoroughness": deai_thoroughness,
        "gold_sentence_completeness": gold_sentence_completeness,
        "opening_quality": opening_quality,
        "ending_quality": ending_quality,
    }
    total_score = _calculate_weighted_score(all_dims)

    final_text = raw.get("final_text", agent_c_output.rewritten_text)
    final_word_count = len(final_text)

    return AgentDOutput(
        final_text=final_text,
        final_word_count=final_word_count,
        title_fulfillment=title_fulfillment,
        outline_alignment=outline_alignment,
        word_compliance=word_compliance,
        style_consistency=style_consistency,
        deai_thoroughness=deai_thoroughness,
        gold_sentence_completeness=gold_sentence_completeness,
        opening_quality=opening_quality,
        ending_quality=ending_quality,
        total_score=total_score,
        high_priority=raw.get("high_priority", []),
        medium_priority=raw.get("medium_priority", []),
        low_priority=raw.get("low_priority", []),
        recommended_action=raw.get("recommended_action", "局部手改"),
        process_archive={
            "agent_a_word_count": agent_a_output.total_word_count,
            "agent_b_sentence_count": len(agent_b_output.sentences),
            "agent_c_rewrite_count": len(agent_c_output.rewrite_table),
            "agent_c_word_change_pct": agent_c_output.word_change_pct,
            "agent_d_final_word_count": final_word_count,
            "style_anchor": agent_a_output.style_anchor,
        },
    )


async def integrate_and_inspect(
    inp: ContentGenerationInput,
    agent_a_output: AgentAOutput,
    agent_b_output: AgentBOutput,
    agent_c_output: AgentCOutput,
) -> AgentDOutput:
    """Agent D 主入口：整合金句 + 8 维度自检诊断。

    Args:
        inp: 正文生成总输入
        agent_a_output: Agent A 输出
        agent_b_output: Agent B 输出
        agent_c_output: Agent C 输出

    Returns:
        AgentDOutput: 最终正文 + 诊断报告
    """
    client = get_llm_client()
    user_prompt = _build_user_prompt(inp, agent_a_output, agent_b_output, agent_c_output)

    logger.info("[Agent D] 开始整合 + 自检诊断")

    messages = [
        ChatMessage(role="system", content=_load_system_prompt()),
        ChatMessage(role="user", content=user_prompt),
    ]

    result = await client.chat(
        messages=messages,
        temperature=0.3,
        max_tokens=8000,
        json_mode=True,
    )

    parsed = parse_json_loose(result.text)
    if parsed and "dimensions" not in parsed:
        for alias in ("evaluations", "scores", "维度", "评分", "评估"):
            if alias in parsed:
                logger.warning(f"[Agent D] LLM 用了别名 key '{alias}'，已映射到 dimensions")
                parsed["dimensions"] = parsed[alias]
                break
    if not parsed or "dimensions" not in parsed:
        logger.error(
            f"[Agent D] 输出解析失败 (len={len(result.text or '')}): "
            f"parsed_keys={list(parsed.keys()) if isinstance(parsed, dict) else type(parsed).__name__}, "
            f"原始响应前 800 字: {(result.text or '')[:800]!r}"
        )
        raise ValueError("Agent D 输出格式不符合 schema")

    output = _parse_llm_output(parsed, inp, agent_a_output, agent_b_output, agent_c_output)

    logger.info(
        f"[Agent D] 诊断完成，总分: {output.total_score}/10，"
        f"建议: {output.recommended_action}"
    )
    return output


def build_final_output(
    inp: ContentGenerationInput,
    agent_a_output: AgentAOutput,
    agent_b_output: AgentBOutput,
    agent_c_output: AgentCOutput,
    agent_d_output: AgentDOutput,
) -> ContentGenerationOutput:
    """汇总所有 Agent 输出为最终 ContentGenerationOutput。"""
    return ContentGenerationOutput(
        final_text=agent_d_output.final_text,
        final_word_count=agent_d_output.final_word_count,
        section_count=agent_a_output.section_count,
        section_word_counts=[s.word_count for s in agent_a_output.sections],
        gold_sentences=agent_b_output.sentences,
        rewrite_table=agent_c_output.rewrite_table,
        diagnosis=agent_d_output,
        agent_a_word_count=agent_a_output.total_word_count,
        agent_b_sentence_count=len(agent_b_output.sentences),
        agent_c_rewrite_count=len(agent_c_output.rewrite_table),
        agent_d_final_word_count=agent_d_output.final_word_count,
        style_anchor=agent_a_output.style_anchor,
    )
