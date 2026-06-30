"""Agent C — 去 AI 味改写员。

职责：按《去 AI 味规则》对全文做扫描和改写，把 LLM 默认的"AI 味"文字净化成"人话"。
规则来源：https://github.com/MatchaDog/stop-slop-cn（MIT License）
"""

import logging
import re
from typing import List, Optional
from pathlib import Path

from app.services.llm import get_llm_client
from app.services.llm.llm_client import ChatMessage, parse_json_loose
from app.services.content_generation.schemas import (
    AgentAOutput,
    AgentBOutput,
    AgentCOutput,
    AITasteIssue,
)

logger = logging.getLogger(__name__)

# 获取当前文件所在目录
CURRENT_DIR = Path(__file__).parent

# ──────────────────────────────────────────────
# 去 AI 味规则（从文件加载）
# ──────────────────────────────────────────────

ASSETS_DIR = CURRENT_DIR / "assets"


def _load_asset(filename: str) -> str:
    """从 assets/ 目录加载参考文件。"""
    filepath = ASSETS_DIR / filename
    if filepath.exists():
        return filepath.read_text(encoding="utf-8")
    logger.warning(f"[Agent C] 资源文件不存在: {filepath}")
    return ""


def _load_deai_rules() -> str:
    """加载去 AI 味核心规则（检查清单 + 短语表 + 结构表）。"""
    checklist = _load_asset("去AI味检查清单.md")
    phrases = _load_asset("phrases.md")
    structures = _load_asset("structures.md")
    parts = [p for p in [checklist, phrases, structures] if p]
    return "\n\n".join(parts) if parts else "# 去 AI 味规则\n\n按 9 条核心规则改写：删除铺垫套话、拆掉公式化结构、让人做主语、写具体、把读者放进现场、调整节奏、相信读者、删除金句腔、消掉翻译腔。"


def _load_examples() -> str:
    """加载修改示例。"""
    return _load_asset("examples.md")


def _load_system_prompt() -> str:
    """从文件加载系统提示词模板，注入规则和示例。"""
    prompt_file = CURRENT_DIR / "prompts" / "agent_c_system.txt"
    if prompt_file.exists():
        template = prompt_file.read_text(encoding="utf-8")
        return template.format(
            deai_rules=_load_deai_rules(),
            deai_examples=_load_examples(),
        )
    # 回退到精简版硬编码提示词
    return (
        "你是去 AI 味改写员。任务是把中文正文里的 AI 腔去掉。\n\n"
        "核心规则：\n"
        "1. 删除铺垫套话\n2. 拆掉公式化结构\n3. 让人做主语\n"
        "4. 写具体\n5. 把读者放进现场\n6. 调整节奏\n"
        "7. 相信读者\n8. 删除金句腔\n9. 消掉翻译腔\n\n"
        "工作流：逐段扫描 → 改写执行 → 质量自检（5 维评分）\n\n"
        "硬约束：字数变化 ≤ ±10%，金句不改，必须删除排版符号。\n\n"
        f"【修改示例】\n\n{_load_examples()}"
    )


def _build_user_prompt(
    agent_a_output: AgentAOutput,
    agent_b_output: AgentBOutput,
    weave_gold_sentences: bool = False,
) -> str:
    """构建用户提示词。

    Args:
        weave_gold_sentences: True 时，金句尚未在正文中，要求把金句融入正文对应位置
            （用于文案润色流程）；False 时金句已在正文中，仅作不可改保护（用于正文生成流程）。
    """
    lines = []

    # 正文
    lines.append("【正文】")
    lines.append(agent_a_output.full_text)
    lines.append("")

    if weave_gold_sentences:
        # 金句尚未在正文中，需要插入
        lines.append("【待融入金句（请插入正文对应位置）】")
        lines.append(
            "以下金句目前【不在】上面的正文里，请把它们自然地融入正文 location 指定的位置"
            "（例如\"第1节末尾\"就放在第1节结尾，\"开头\"就放在段落开头），"
            "衔接要顺，不要生硬堆砌。融入后这些句子视为不可改。"
        )
        for s in agent_b_output.sentences:
            lines.append(f"- 第{s.section_number}节 {s.location}（{s.sentence_type}）: \"{s.content}\"")
        lines.append("")
    else:
        # 金句清单（已在正文中，不可改）
        lines.append("【金句清单（不可改段落）】")
        for s in agent_b_output.sentences:
            lines.append(f"- 第{s.section_number}节 {s.location}: \"{s.content}\"")
        lines.append("")

    # 输出格式
    lines.append("【输出格式】")
    lines.append("请严格按以下 JSON 格式输出：")
    lines.append("""```json
{
  "rewritten_text": "改写后的完整正文（含小标题标记）",
  "rewrite_table": [
    {
      "location": "第1节第2段",
      "ai_taste_type": "铺垫套话",
      "ai_taste_subtype": "开场清嗓",
      "priority": "🚫",
      "original_text": "原文片段",
      "rewritten_text": "改写后片段",
      "reason": "改写理由"
    }
  ],
  "skipped_sections": [
    "第1节末尾金句：'金句内容'"
  ],
  "stats": {
    "total_issues": 15,
    "rewrite_counts": {"🚫": 10, "⚠️": 5},
    "skipped": 3
  },
  "quality_check": {
    "original_word_count": 2680,
    "rewritten_word_count": 2620,
    "word_change_pct": -2.2,
    "original_kept": true,
    "new_ai_taste": false,
    "score": {
      "direct": 8,
      "rhythm": 7,
      "trust": 8,
      "real": 7,
      "density": 8,
      "total": 38
    }
  }
}
```""")

    return "\n".join(lines)


def _strip_gold_sentence_list(text: str) -> str:
    """剥掉 LLM 可能粘在末尾的金句清单段落。"""
    if not text:
        return text
    # 剥掉「金句种子：xxx」前缀（LLM 有时保留 Agent A 的种子标记）
    text = re.sub(r"金句种子[：:]\s*", "", text)
    # 匹配 【金句清单（不可改段落）】 或 【金句清单】 及其后的列表行
    pattern = r"\n*【金句清单[^】]*】[\s\S]*$"
    cleaned = re.sub(pattern, "", text)
    return cleaned.rstrip()


def _parse_llm_output(raw: dict, original_word_count: int) -> AgentCOutput:
    """解析 LLM 输出为 AgentCOutput。"""
    # 后处理：剥掉 LLM 可能粘在 rewritten_text 末尾的金句清单
    rewritten = raw.get("rewritten_text", "")
    rewritten = _strip_gold_sentence_list(rewritten)

    rewrite_table = []
    for item in raw.get("rewrite_table", []):
        rewrite_table.append(AITasteIssue(
            location=item.get("location", ""),
            ai_taste_type=item.get("ai_taste_type", ""),
            ai_taste_subtype=item.get("ai_taste_subtype", ""),
            priority=item.get("priority", "⚠️"),
            original_text=item.get("original_text", ""),
            rewritten_text=item.get("rewritten_text", ""),
            reason=item.get("reason", ""),
        ))

    qc = raw.get("quality_check", {})
    rewritten_count = qc.get("rewritten_word_count", len(raw.get("rewritten_text", "")))
    word_change = qc.get("word_change_pct", 0.0)
    if word_change == 0.0 and original_word_count > 0:
        word_change = round((rewritten_count - original_word_count) / original_word_count * 100, 1)

    return AgentCOutput(
        rewritten_text=rewritten,
        rewritten_word_count=rewritten_count,
        original_word_count=qc.get("original_word_count", original_word_count),
        word_change_pct=word_change,
        rewrite_table=rewrite_table,
        skipped_sections=raw.get("skipped_sections", []),
        stats=raw.get("stats", {}),
        quality_check=qc,
    )


MAX_RETRIES = 3


async def deai_rewrite(
    agent_a_output: AgentAOutput,
    agent_b_output: AgentBOutput,
    corrected_text: Optional[str] = None,
    provider: Optional[str] = None,
    weave_gold_sentences: bool = False,
) -> AgentCOutput:
    """Agent C 主入口：去 AI 味改写。

    Schema 校验失败时自动重试，最多 3 次。

    Args:
        agent_a_output: Agent A 的输出（正文骨干）
        agent_b_output: Agent B 的输出（金句清单，用于识别不可改段落）
        corrected_text: Agent E 纠错后的正文（如有）。如果提供，用此文本替代 agent_a_output.full_text
        provider: LLM provider 名称（可选，默认使用 settings.LLM_PROVIDER）

    Returns:
        AgentCOutput: 改写后正文 + 改写对照表
    """
    client = get_llm_client(provider)

    # 如果有纠错后的文本，创建一个临时的 agent_a_output 副本
    if corrected_text:
        import copy
        a_copy = copy.deepcopy(agent_a_output)
        a_copy.full_text = corrected_text
        a_copy.total_word_count = len(corrected_text)
        user_prompt = _build_user_prompt(a_copy, agent_b_output, weave_gold_sentences)
    else:
        user_prompt = _build_user_prompt(agent_a_output, agent_b_output, weave_gold_sentences)
    system_prompt = _load_system_prompt()
    if weave_gold_sentences:
        # 润色流程：金句需插入正文，放宽字数限制
        system_prompt += (
            "\n\n【本次特别说明】"
            "\n本次任务的金句【尚未】出现在正文中，属于「待融入金句」。"
            "请务必把它们逐条插入到正文 location 指定的位置，并让前后文衔接自然。"
            "因插入金句导致的字数增加是允许，不受 ±10% 字数变化限制约束；"
            "其余去 AI 味改写仍需遵守原有规则。"
            "rewritten_text 必须是【已经包含全部金句】的完整正文。"
        )

    logger.info(f"[Agent C] 开始去 AI 味改写，原文字数: {agent_a_output.total_word_count}")

    last_error = None
    current_max_tokens = 32000
    for attempt in range(1, MAX_RETRIES + 1):
        extra_hint = ""
        if attempt > 1:
            extra_hint = (
                "\n\n【重要】上一次输出格式不符合要求。"
                "请严格输出 JSON，必须包含 rewritten_text 字段（改写后的完整正文字符串），"
                "以及 rewrite_table、skipped_sections、stats、quality_check 字段。"
                "不要输出任何 markdown 标记或解释文字。"
            )

        messages = [
            ChatMessage(role="system", content=system_prompt + extra_hint),
            ChatMessage(role="user", content=user_prompt),
        ]

        result = await client.chat(
            messages=messages,
            temperature=0.5,
            max_tokens=current_max_tokens,
            json_mode=True,
        )

        # 检测截断，自动增大 max_tokens
        if getattr(result, 'finish_reason', None) == "length":
            logger.warning(f"[Agent C] 输出被截断 (max_tokens={current_max_tokens})，增大重试")
            current_max_tokens = min(current_max_tokens * 2, 65536)
            last_error = ValueError("Agent C 输出被 max_tokens 截断")
            continue

        parsed = parse_json_loose(result.text)
        if parsed and "rewritten_text" not in parsed:
            for alias in ("rewrite", "text", "content", "改写后", "result", "output"):
                if alias in parsed and isinstance(parsed[alias], str):
                    logger.warning(f"[Agent C] LLM 用了别名 key '{alias}'，已映射到 rewritten_text")
                    parsed["rewritten_text"] = parsed[alias]
                    break

        if not parsed or not isinstance(parsed.get("rewritten_text"), str):
            last_error = ValueError("Agent C 输出格式不符合 schema")
            logger.warning(
                f"[Agent C] 第 {attempt}/{MAX_RETRIES} 次输出解析失败 "
                f"(len={len(result.text or '')}): "
                f"parsed_keys={list(parsed.keys()) if isinstance(parsed, dict) else type(parsed).__name__}, "
                f"原始响应前 800 字: {(result.text or '')[:800]!r}"
            )
            continue

        output = _parse_llm_output(parsed, agent_a_output.total_word_count)
        _self_check(output, agent_a_output.total_word_count)
        logger.info(
            f"[Agent C] 去 AI 味完成（第 {attempt} 次），改写后字数: {output.rewritten_word_count}，"
            f"变化: {output.word_change_pct}%，改写处数: {len(output.rewrite_table)}"
        )
        return output

    logger.error(f"[Agent C] {MAX_RETRIES} 次尝试均失败")
    raise last_error


def _self_check(output: AgentCOutput, original_word_count: int):
    """Agent C 自检。"""
    warnings = []

    if abs(output.word_change_pct) > 10:
        warnings.append(f"字数变化超限: {output.word_change_pct}%（允许 ±10%）")

    if output.rewritten_word_count < 2000:
        warnings.append(f"改写后字数过少: {output.rewritten_word_count}")

    if warnings:
        logger.warning(f"[Agent C] 自检警告: {'; '.join(warnings)}")
