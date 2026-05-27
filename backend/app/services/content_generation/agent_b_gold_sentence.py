"""Agent B — 金句催化员。

职责：基于正文骨干，催化生成 3-5 个金句，标注位置 + 不可改标签。
设计对齐：《正文生成 Agent 设计文档 v1.1》第 3 节。
"""

import logging
from typing import List
from pathlib import Path

from app.services.llm import get_llm_client
from app.services.llm.llm_client import ChatMessage, parse_json_loose
from app.services.content_generation.schemas import (
    AgentAOutput,
    AgentBOutput,
    GoldSentence,
    ContentGenerationInput,
)

logger = logging.getLogger(__name__)

# 获取当前文件所在目录
CURRENT_DIR = Path(__file__).parent

# ──────────────────────────────────────────────
# 提示词模板
# ──────────────────────────────────────────────

def _load_system_prompt() -> str:
    """从文件加载系统提示词"""
    prompt_file = CURRENT_DIR / "prompts" / "agent_b_system.txt"
    if prompt_file.exists():
        return prompt_file.read_text(encoding="utf-8")
    # 回退到硬编码版本
    return """\
你是一位金句精雕师，擅长把正文里的"准金句"打磨成可独立传播的金句。

【金句要素】
每个金句必须满足：
- 字数 15-50
- 含反差/抽象提炼/共鸣表达/强观点 中至少 1 种
- 脱离上下文也能独立成立（截图能传播）
- 不是流于表面的鸡汤

【金句类型】
- 反差金句：用对比制造张力（如"Cursor 让我从写代码变成写需求"）
- 抽象金句：把具体经历抽象成普适道理（如"工具便宜的时候我们用工具，工具贵了我们就要被工具用"）
- 共鸣金句：说出读者心里有但没说出口的话（如"AI 不会让我失业，但用 AI 的人会"）
- 强观点金句：不留余地的判断（如"X 不是升级，是拐点"）
- 自嘲金句：第一人称带点自我吐槽（如"我用了三个月才学会问 AI 闭嘴"）

【类型分布要求】
- 开头钩子金句：1 个（第 1 节内，开头 200 字内）
- 中段共鸣金句：1-2 个（第 2-3 节）
- 结尾升华金句：1 个（最后一节）
- 反差/反共识金句：0-1 个（任意位置）

【保护原则】
- 不允许重写正文骨干，只能在正文里"增强"或"补足"金句
- 每个金句要明确标注位置 + 插入方式（替换种子 or 新增）
- 每个金句打上"不可改"标签
"""


def _build_user_prompt(
    agent_a_output: AgentAOutput,
    topic_title: str,
) -> str:
    """构建用户提示词。"""
    lines = []

    lines.append(f"【选题标题】{topic_title}")
    lines.append("")

    # 正文（含金句种子位置标注）
    lines.append("【正文骨干】")
    for sec in agent_a_output.sections:
        lines.append(f"### 第{sec.section_number}节: {sec.subtitle}")
        if sec.gold_seed:
            lines.append(f"[金句种子位置: {sec.gold_seed.position}]")
            lines.append(f"[准金句: {sec.gold_seed.seed_text}]")
        lines.append(sec.content)
        lines.append("")

    # 输出格式
    lines.append("")
    lines.append("【输出格式】")
    lines.append("请严格按以下 JSON 格式输出：")
    lines.append("""```json
{
  "sentences": [
    {
      "sentence_id": 1,
      "sentence_type": "开头钩子金句（反差金句）",
      "location": "第1节末尾",
      "section_number": 1,
      "insert_method": "替换种子",
      "content": "金句内容",
      "word_count": 15
    }
  ],
  "stats": {
    "total": 4,
    "type_distribution": {
      "开头钩子": 1,
      "中段共鸣": 2,
      "结尾升华": 1
    }
  }
}
```""")
    lines.append("")
    lines.append("注意：")
    lines.append("1. 每个金句 immutable 字段固定为 true")
    lines.append("2. 如果原位置有金句种子，insert_method 填'替换种子'；如果是新增位置，填'新增'")
    lines.append("3. 金句数量 3-5 个")

    return "\n".join(lines)


def _parse_llm_output(raw: dict) -> AgentBOutput:
    """解析 LLM 输出为 AgentBOutput。"""
    sentences_raw = raw.get("sentences", [])
    sentences = []
    for s in sentences_raw:
        sentences.append(GoldSentence(
            sentence_id=s.get("sentence_id", 0),
            sentence_type=s.get("sentence_type", ""),
            location=s.get("location", ""),
            section_number=s.get("section_number", 0),
            insert_method=s.get("insert_method", "新增"),
            content=s.get("content", ""),
            word_count=s.get("word_count", len(s.get("content", ""))),
            immutable=True,
        ))

    stats = raw.get("stats", {"total": len(sentences)})

    return AgentBOutput(sentences=sentences, stats=stats)


MAX_RETRIES = 3


async def catalyze_gold_sentences(
    agent_a_output: AgentAOutput,
    topic_title: str,
) -> AgentBOutput:
    """Agent B 主入口：催化 3-5 个金句。

    Schema 校验失败时自动重试，最多 3 次。

    Args:
        agent_a_output: Agent A 的输出
        topic_title: 选题标题

    Returns:
        AgentBOutput: 金句清单
    """
    client = get_llm_client()
    user_prompt = _build_user_prompt(agent_a_output, topic_title)
    system_prompt = _load_system_prompt()

    logger.info(f"[Agent B] 开始催化金句，标题: {topic_title}")

    last_error = None
    current_max_tokens = 8000
    for attempt in range(1, MAX_RETRIES + 1):
        extra_hint = ""
        if attempt > 1:
            extra_hint = (
                "\n\n【重要】上一次输出格式不符合要求。"
                "请严格输出 JSON，必须包含 sentences 数组，每个元素含 sentence_id、sentence_type、"
                "location、section_number、insert_method、content、word_count 字段。"
                "不要输出任何 markdown 标记或解释文字。"
            )

        messages = [
            ChatMessage(role="system", content=system_prompt + extra_hint),
            ChatMessage(role="user", content=user_prompt),
        ]

        result = await client.chat(
            messages=messages,
            temperature=0.8,
            max_tokens=current_max_tokens,
            json_mode=True,
        )

        # 检测截断，自动增大 max_tokens
        if getattr(result, 'finish_reason', None) == "length":
            logger.warning(f"[Agent B] 输出被截断 (max_tokens={current_max_tokens})，增大重试")
            current_max_tokens = min(current_max_tokens * 2, 16000)
            last_error = ValueError("Agent B 输出被 max_tokens 截断")
            continue

        parsed = parse_json_loose(result.text)

        # LLM 经常用别的 key 名（gold_sentences / items / data...），都映射到 sentences
        if parsed and "sentences" not in parsed:
            for alias in ("gold_sentences", "金句", "items", "data", "results", "list"):
                if alias in parsed and isinstance(parsed[alias], list):
                    logger.warning(f"[Agent B] LLM 用了别名 key '{alias}'，已映射到 sentences")
                    parsed["sentences"] = parsed[alias]
                    break
            else:
                # 如果整个 parsed 本身就是个 list，包一层
                if isinstance(parsed, list):
                    parsed = {"sentences": parsed}

        if not parsed or not isinstance(parsed.get("sentences"), list):
            last_error = ValueError("Agent B 输出格式不符合 schema")
            logger.warning(
                f"[Agent B] 第 {attempt}/{MAX_RETRIES} 次输出解析失败 "
                f"(len={len(result.text or '')}): "
                f"parsed_keys={list(parsed.keys()) if isinstance(parsed, dict) else type(parsed).__name__}, "
                f"原始响应前 800 字: {(result.text or '')[:800]!r}"
            )
            continue

        output = _parse_llm_output(parsed)
        _self_check(output)
        logger.info(f"[Agent B] 金句催化完成（第 {attempt} 次），共 {len(output.sentences)} 个金句")
        return output

    logger.error(f"[Agent B] {MAX_RETRIES} 次尝试均失败")
    raise last_error


def _self_check(output: AgentBOutput):
    """Agent B 自检。"""
    warnings = []

    if len(output.sentences) < 3:
        warnings.append(f"金句数量不足: {len(output.sentences)}（期望 3-5 个）")

    for s in output.sentences:
        if s.word_count < 10:
            warnings.append(f"金句{s.sentence_id}过短: {s.word_count}字")
        elif s.word_count > 50:
            warnings.append(f"金句{s.sentence_id}过长: {s.word_count}字")

    if warnings:
        logger.warning(f"[Agent B] 自检警告: {'; '.join(warnings)}")
