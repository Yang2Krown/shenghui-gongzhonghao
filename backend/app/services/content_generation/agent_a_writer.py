"""Agent A — 正文创作员。

职责：基于选题 + 大纲 + 标题 + 风格参数，一次性生成 2500-3000 字的正文骨干。
设计对齐：《正文生成 Agent 设计文档 v1.1》第 2 节。
"""

import logging
from typing import Optional
from pathlib import Path

from app.services.llm import get_llm_client
from app.services.llm.llm_client import ChatMessage, parse_json_loose
from app.services.content_generation.schemas import (
    ContentGenerationInput,
    AgentAOutput,
    SectionContent,
    GoldSentenceSeed,
)

logger = logging.getLogger(__name__)

# 获取当前文件所在目录
CURRENT_DIR = Path(__file__).parent

# ──────────────────────────────────────────────
# 提示词模板
# ──────────────────────────────────────────────

def _load_system_prompt() -> str:
    """从文件加载系统提示词"""
    prompt_file = CURRENT_DIR / "prompts" / "agent_a_system.txt"
    if prompt_file.exists():
        return prompt_file.read_text(encoding="utf-8")
    # 回退到硬编码版本
    return """\
你是一位资深 AI 公众号正文写手。你的任务是基于选题、大纲、标题，一次性生成 2500-3000 字的正文。

【硬约束】
1. 总字数 2500-3000 字，目标 ≥ 2500
2. 单节字数 400-600，偏离 ±20% 内
3. 每节小标题严格使用大纲提供的版本（不允许重写）
4. 每节内容必须覆盖大纲给的核心信息点
5. 必须兑现标题承诺（如标题说"3 个用法"必须可见 3 个用法）
6. 在开头节末尾、结尾节开头各埋 1 个"准金句"种子
7. 如有禁用词清单，硬性不允许出现
8. 整篇保持风格锚点一致

【关于风格 — 主动避免 AI 味】
- 第一人称叙述（用"我"）
- 具体优于抽象（用数字、人名、时间、场景）
- 避免书面体（"在……的情况下""进行……操作"等）
- 段落 ≤ 4 行
- 长短句交替
- 避免典型 AI 词：首先/其次/最后/综上所述/总而言之/由此可见/一方面/另一方面
- 避免学院体：在……的情况下/对于……而言/在……过程中/进行……操作
- 避免营销话术：革命性/颠覆性/划时代/强大的/极致/完美/赋能
- 避免程度副词滥用：非常/特别/十分/相当/极其
- 避免客观中立模糊词：在某种程度上/客观地讲/各有所长

【关于金句种子】
在以下位置主动埋 1-2 个"准金句"种子（作为后续金句催化的基础）：
- 开头节末尾（结束钩子的位置）
- 结尾节开头（开始升华的位置）
金句特征：反差 / 抽象提炼 / 共鸣表达 / 强观点，15-50 字。
"""


def _build_user_prompt(inp: ContentGenerationInput) -> str:
    """构建用户提示词。"""
    lines = []

    # 选题信息
    lines.append("【选题】")
    lines.append(f"标题（已选定）: {inp.topic_title}")
    if inp.topic_direction:
        lines.append(f"方向: {inp.topic_direction}")
    if inp.topic_routine:
        lines.append(f"套路: {inp.topic_routine}")
    if inp.value_promise:
        lines.append(f"价值承诺: {inp.value_promise}")
    lines.append("")

    # 大纲
    lines.append("【大纲】")
    for sec in inp.sections:
        lines.append(f"第{sec.section_number}节: {sec.subtitle}")
        if sec.core_points:
            lines.append(f"  核心信息点: {'; '.join(sec.core_points)}")
        if sec.spread_role:
            lines.append(f"  传播角色: {sec.spread_role}")
        lines.append(f"  字数预估: {sec.word_estimate}")
        if sec.notes:
            lines.append(f"  备注: {sec.notes}")
    lines.append("")

    # 风格参数
    if inp.style_params:
        lines.append("【风格参数】")
        if inp.style_params.tone:
            lines.append(f"语气: {inp.style_params.tone}")
        if inp.style_params.banned_words:
            lines.append(f"禁用词: {', '.join(inp.style_params.banned_words)}")
        if inp.style_params.preferred_words:
            lines.append(f"偏好用词: {', '.join(inp.style_params.preferred_words)}")
        lines.append("")

    # 输出格式要求
    lines.append("【输出格式】")
    lines.append("请严格按以下 JSON 格式输出，不要输出其他内容：")
    lines.append("""```json
{
  "style_anchor": "本文语气：xxx",
  "sections": [
    {
      "section_number": 1,
      "subtitle": "小标题（必须与大纲一致）",
      "content": "该节正文内容...",
      "gold_seed": {
        "section_number": 1,
        "position": "第1节末尾",
        "seed_text": "准金句文本"
      }
    }
  ]
}
```""")
    lines.append("")
    lines.append("注意：")
    lines.append("1. gold_seed 只在开头节末尾和结尾节开头各放1个，其他节 gold_seed 设为 null")
    lines.append("2. 每节 content 直接写正文，不要加小标题（小标题由 subtitle 字段单独提供）")
    lines.append("3. 总字数必须 ≥ 2500")

    return "\n".join(lines)


def _parse_llm_output(raw: dict, inp: ContentGenerationInput) -> AgentAOutput:
    """解析 LLM 输出为 AgentAOutput。"""
    style_anchor = raw.get("style_anchor", "本文语气：第一人称、信息密度高、避免书面体")
    sections_raw = raw.get("sections", [])

    sections = []
    gold_seeds = []
    total_words = 0

    for sec in sections_raw:
        content = sec.get("content", "")
        word_count = len(content)
        total_words += word_count

        seed = None
        seed_data = sec.get("gold_seed")
        if seed_data and seed_data.get("seed_text"):
            seed = GoldSentenceSeed(
                section_number=seed_data.get("section_number", sec.get("section_number", 0)),
                position=seed_data.get("position", ""),
                seed_text=seed_data["seed_text"],
            )
            gold_seeds.append(seed)

        sections.append(SectionContent(
            section_number=sec.get("section_number", 0),
            subtitle=sec.get("subtitle", ""),
            content=content,
            word_count=word_count,
            gold_seed=seed,
        ))

    # 拼接全文
    full_text = "\n\n".join(
        f"## {sec.subtitle}\n\n{sec.content}" for sec in sections
    )

    return AgentAOutput(
        style_anchor=style_anchor,
        full_text=full_text,
        total_word_count=total_words,
        section_count=len(sections),
        sections=sections,
        gold_seeds=gold_seeds,
    )


async def generate_article(inp: ContentGenerationInput) -> AgentAOutput:
    """Agent A 主入口：一次性生成 2500-3000 字正文骨干。

    Args:
        inp: 正文生成总输入

    Returns:
        AgentAOutput: 正文骨干 + 风格锚点 + 金句种子
    """
    client = get_llm_client()
    user_prompt = _build_user_prompt(inp)

    logger.info(f"[Agent A] 开始生成正文，标题: {inp.topic_title}")

    messages = [
        ChatMessage(role="system", content=_load_system_prompt()),
        ChatMessage(role="user", content=user_prompt),
    ]

    result = await client.chat(
        messages=messages,
        temperature=0.7,
        max_tokens=8000,
        json_mode=True,
    )

    parsed = parse_json_loose(result.text)
    if parsed and "sections" not in parsed:
        for alias in ("parts", "sections_list", "段落", "items", "节"):
            if alias in parsed and isinstance(parsed[alias], list):
                logger.warning(f"[Agent A] LLM 用了别名 key '{alias}'，已映射到 sections")
                parsed["sections"] = parsed[alias]
                break
        else:
            if isinstance(parsed, list):
                parsed = {"sections": parsed}
    if not parsed or not isinstance(parsed.get("sections"), list):
        logger.error(
            f"[Agent A] 输出解析失败 (len={len(result.text or '')}): "
            f"parsed_keys={list(parsed.keys()) if isinstance(parsed, dict) else type(parsed).__name__}, "
            f"原始响应前 800 字: {(result.text or '')[:800]!r}"
        )
        raise ValueError("Agent A 输出格式不符合 schema")

    output = _parse_llm_output(parsed, inp)

    # 自检
    _self_check(output, inp)

    logger.info(f"[Agent A] 正文生成完成，字数: {output.total_word_count}，节数: {output.section_count}")
    return output


def _self_check(output: AgentAOutput, inp: ContentGenerationInput):
    """Agent A 自检清单。"""
    warnings = []

    if output.total_word_count < 2000:
        warnings.append(f"字数严重不足: {output.total_word_count}（目标 ≥ 2500）")
    elif output.total_word_count < 2500:
        warnings.append(f"字数偏少: {output.total_word_count}（目标 ≥ 2500）")
    elif output.total_word_count > 3500:
        warnings.append(f"字数超额: {output.total_word_count}（目标 ≤ 3000）")

    for sec in output.sections:
        if sec.word_count < 300:
            warnings.append(f"第{sec.section_number}节字数过少: {sec.word_count}")
        elif sec.word_count > 700:
            warnings.append(f"第{sec.section_number}节字数过多: {sec.word_count}")

    if len(output.gold_seeds) < 2:
        warnings.append(f"金句种子不足: {len(output.gold_seeds)}（期望至少2个）")

    if warnings:
        logger.warning(f"[Agent A] 自检警告: {'; '.join(warnings)}")
