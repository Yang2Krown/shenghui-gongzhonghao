"""正文生成编排器。

串联 Agent A → B → D → E → C，完成从选题+大纲到最终正文的全流程。
5 步：生成正文 → 金句催化 → 事实总结 → 联网纠错 → 去 AI 味
"""

import logging
import re
import time
from typing import Callable, List, Optional

from app.services.content_generation.schemas import (
    ContentGenerationInput,
    ContentGenerationOutput,
    GoldSentence,
)
from app.services.content_generation.agent_a_writer import generate_article
from app.services.content_generation.agent_b_gold_sentence import catalyze_gold_sentences
from app.services.content_generation.agent_d_inspector import summarize_factual_errors
from app.services.content_generation.agent_e_kimi_corrector import kimi_correct_facts
from app.services.content_generation.agent_c_deai import deai_rewrite

logger = logging.getLogger(__name__)


def _update_gold_sentences_for_rewritten_text(
    gold_sentences: List[GoldSentence],
    rewritten_text: str,
) -> List[GoldSentence]:
    """Agent C 改写后，金句文本可能已变化，用模糊匹配更新金句 content。"""

    def normalize(s: str) -> str:
        """去空白+标点，用于模糊比对。"""
        return re.sub(r'[\s　]+', '', re.sub(r'[，。！？；：（）【】、""''—–\-.,!?;:()\[\]{}"\'\']', '', s))

    def strip_prefix(s: str) -> str:
        """去掉 LLM 可能添加的装饰性前缀。"""
        return re.sub(r'^[\s—–\-:=：·•>】\]）)]*(?:金句|金句内容|金句文本|去AI味|改写|rewrite|句子|内容|文本)[\s：:—–\-]*', '', s).strip()

    def find_best_match(gold_text: str, text: str) -> str:
        """在 text 中找与 gold_text 最匹配的子串，返回匹配到的原文。"""
        gold_text = strip_prefix(gold_text)
        gold_norm = normalize(gold_text)
        if not gold_norm or len(gold_norm) < 4:
            return gold_text

        if gold_text in text:
            return gold_text

        seed = gold_norm[:16]
        if len(seed) >= 4:
            text_norm = normalize(text)
            idx = text_norm.find(seed)
            if idx >= 0:
                norm_pos = 0
                char_pos = 0
                for i, ch in enumerate(text):
                    if norm_pos >= idx:
                        char_pos = i
                        break
                    if normalize(ch):
                        norm_pos += 1
                end = char_pos
                target_len = len(gold_text)
                while end < len(text) and end - char_pos < target_len * 1.5:
                    if text[end] in '。！？\n':
                        break
                    end += 1
                matched = text[char_pos:end].strip()
                if len(matched) >= 4:
                    return matched

        return gold_text

    updated = []
    for gs in gold_sentences:
        new_content = find_best_match(gs.content, rewritten_text)
        if new_content != gs.content:
            updated.append(gs.model_copy(update={
                'content': new_content,
                'word_count': len(new_content),
            }))
        else:
            updated.append(gs)
    return updated


async def generate_content(
    inp: ContentGenerationInput,
    progress_callback: Optional[Callable] = None,
) -> ContentGenerationOutput:
    """正文生成主流程：Agent A → B → D → E → C。

    Args:
        inp: 正文生成总输入（选题 + 大纲 + 标题 + 风格参数）

    Returns:
        ContentGenerationOutput: 最终正文 + 金句 + 改写对照表 + 事实纠错报告

    Raises:
        ValueError: 输入校验失败
        RuntimeError: Agent 执行异常
    """
    start_time = time.time()
    logger.info(f"[正文生成] 开始，标题: {inp.topic_title}")

    # ──────────────────────────────────────────
    # Step 1: Agent A — 正文创作员
    # ──────────────────────────────────────────
    logger.info("[正文生成] Step 1/5: Agent A 生成正文骨干")
    if progress_callback:
        await progress_callback({"event": "step_start", "data": {"step": 1, "agent": "温如言 · 正文创作员", "action": "正在按节撰写初稿...", "avatar": "/agents/content-a.png"}})
    try:
        agent_a_output = await generate_article(inp)
    except Exception as e:
        logger.error(f"[正文生成] Agent A 失败: {e}")
        raise RuntimeError(f"正文生成失败（Agent A）: {e}") from e

    if progress_callback:
        await progress_callback({"event": "step_done", "data": {"step": 1, "agent": "Agent A"}})

    # 异常处理：字数严重不足
    if agent_a_output.total_word_count < 1700:
        logger.warning(
            f"[正文生成] Agent A 字数严重不足: {agent_a_output.total_word_count}，"
            f"建议丢回重试"
        )

    # ──────────────────────────────────────────
    # Step 2: Agent B — 金句催化员
    # ──────────────────────────────────────────
    logger.info("[正文生成] Step 2/5: Agent B 催化金句")
    if progress_callback:
        await progress_callback({"event": "step_start", "data": {"step": 2, "agent": "居怀金 · 正文催化员", "action": "正在催化 3-5 个金句...", "avatar": "/agents/content-b.png"}})
    try:
        agent_b_output = await catalyze_gold_sentences(
            agent_a_output=agent_a_output,
            topic_title=inp.topic_title,
        )
    except Exception as e:
        logger.error(f"[正文生成] Agent B 失败: {e}")
        raise RuntimeError(f"正文生成失败（Agent B）: {e}") from e

    if progress_callback:
        await progress_callback({"event": "step_done", "data": {"step": 2, "agent": "Agent B"}})

    # ──────────────────────────────────────────
    # Step 3: Agent D — 事实总结员
    # ──────────────────────────────────────────
    logger.info("[正文生成] Step 3/5: Agent D 事实性错误扫描")
    if progress_callback:
        await progress_callback({"event": "step_start", "data": {"step": 3, "agent": "韩知微 · 事实总结员", "action": "正在扫描事实性陈述...", "avatar": "/agents/content-d.png"}})
    try:
        agent_d_output = await summarize_factual_errors(
            inp=inp,
            agent_a_output=agent_a_output,
            agent_b_output=agent_b_output,
        )
    except Exception as e:
        logger.error(f"[正文生成] Agent D 失败: {e}")
        raise RuntimeError(f"正文生成失败（Agent D）: {e}") from e

    if progress_callback:
        await progress_callback({"event": "step_done", "data": {"step": 3, "agent": "Agent D"}})

    # ──────────────────────────────────────────
    # Step 4: Agent E — Kimi 联网纠错员
    # ──────────────────────────────────────────
    logger.info("[正文生成] Step 4/5: Agent E 联网纠错")
    if progress_callback:
        await progress_callback({"event": "step_start", "data": {"step": 4, "agent": "齐鉴真 · 联网纠错员", "action": "正在联网验证事实...", "avatar": "/agents/content-e.png"}})
    try:
        agent_e_output = await kimi_correct_facts(
            inp=inp,
            agent_a_output=agent_a_output,
            agent_b_output=agent_b_output,
            agent_d_output=agent_d_output,
        )
    except Exception as e:
        logger.error(f"[正文生成] Agent E 失败: {e}")
        raise RuntimeError(f"正文生成失败（Agent E）: {e}") from e

    if progress_callback:
        await progress_callback({"event": "step_done", "data": {"step": 4, "agent": "Agent E"}})

    # ──────────────────────────────────────────
    # Step 5: Agent C — 去 AI 味改写员
    # ──────────────────────────────────────────
    logger.info("[正文生成] Step 5/5: Agent C 去 AI 味改写")
    if progress_callback:
        await progress_callback({"event": "step_start", "data": {"step": 5, "agent": "景澄之 · 正文改写员", "action": "正在去 AI 味改写...", "avatar": "/agents/content-c.png"}})
    try:
        agent_c_output = await deai_rewrite(
            agent_a_output=agent_a_output,
            agent_b_output=agent_b_output,
            corrected_text=agent_e_output.corrected_text,
        )
    except Exception as e:
        logger.error(f"[正文生成] Agent C 失败: {e}")
        raise RuntimeError(f"正文生成失败（Agent C）: {e}") from e

    if progress_callback:
        await progress_callback({"event": "step_done", "data": {"step": 5, "agent": "Agent C"}})

    # 异常处理：改写字数变化超限
    if abs(agent_c_output.word_change_pct) > 10:
        logger.warning(
            f"[正文生成] Agent C 字数变化超限: {agent_c_output.word_change_pct}%，"
            f"建议回退到改写前版本"
        )

    # ──────────────────────────────────────────
    # 汇总输出
    # ──────────────────────────────────────────

    # 更新金句文本匹配
    updated_gold_sentences = _update_gold_sentences_for_rewritten_text(
        agent_b_output.sentences,
        agent_c_output.rewritten_text,
    )

    output = ContentGenerationOutput(
        final_text=agent_c_output.rewritten_text,
        final_word_count=agent_c_output.rewritten_word_count,
        section_count=agent_a_output.section_count,
        section_word_counts=[s.word_count for s in agent_a_output.sections],
        gold_sentences=updated_gold_sentences,
        rewrite_table=agent_c_output.rewrite_table,
        factual_summary=agent_d_output,
        factual_corrections=agent_e_output,
        agent_a_word_count=agent_a_output.total_word_count,
        agent_b_sentence_count=len(agent_b_output.sentences),
        agent_c_rewrite_count=len(agent_c_output.rewrite_table),
        agent_d_error_count=agent_d_output.error_count,
        agent_e_correction_count=agent_e_output.total_corrections,
        style_anchor=agent_a_output.style_anchor,
    )

    elapsed = time.time() - start_time
    logger.info(
        f"[正文生成] 完成，耗时: {elapsed:.1f}s，"
        f"最终字数: {output.final_word_count}，"
        f"事实纠错: {output.agent_e_correction_count} 处"
    )

    if progress_callback:
        await progress_callback({"event": "complete", "data": {"step": 5, "agent": "Agent C"}})

    return output
