"""文案润色编排器。

串联 Agent B → D → E → C，对用户提供的文本进行润色。
跳过 Agent A（正文创作），直接从用户文本构造虚拟的 AgentAOutput。
"""

import logging
import re
import time
from typing import Callable, List, Optional

from app.services.content_generation.schemas import (
    AgentAOutput,
    AgentBOutput,
    AgentCOutput,
    AgentDOutput,
    AgentEOutput,
    ContentGenerationInput,
    GoldSentenceSeed,
    SectionBrief,
    SectionContent,
)
from app.services.content_generation.agent_b_gold_sentence import catalyze_gold_sentences
from app.services.content_generation.agent_d_inspector import summarize_factual_errors
from app.services.content_generation.agent_e_kimi_corrector import kimi_correct_facts
from app.services.content_generation.agent_c_deai import deai_rewrite

from app.services.content_polish.schemas import PolishInput, PolishOutput

logger = logging.getLogger(__name__)


def _clean_punctuation(text: str) -> str:
    """清理金句/正文中不必要的标点符号。

    公众号文章不需要新闻报纸式的排版符号，保持排版美观、阅读流畅。
    """
    # 去掉双引号 "" ""
    text = text.replace('\u201c', '').replace('\u201d', '')
    text = text.replace('\u2018', '').replace('\u2019', '')
    # 去掉书名号 《》
    text = text.replace('《', '').replace('》', '')
    # 破折号 —— 改成句号或逗号
    text = text.replace('——', '，')
    # 省略号 …… 保留但限制（这里不处理，由 Agent C 控制）
    return text.strip()


def _build_virtual_agent_a_output(text: str, title: Optional[str] = None) -> tuple:
    """从用户文本构造虚拟的 AgentAOutput 和 ContentGenerationInput。

    按段落拆分文本，每段作为一个 section。
    如果文本没有明显分段，则整体作为一个 section。

    Returns:
        tuple: (AgentAOutput, ContentGenerationInput)
    """
    # 按双换行或单换行拆段落，过滤空段
    raw_paragraphs = re.split(r'\n{2,}', text.strip())
    paragraphs = [p.strip() for p in raw_paragraphs if p.strip()]

    # 如果只有一个段落但很长，尝试按单换行再拆
    if len(paragraphs) == 1 and len(paragraphs[0]) > 500:
        sub_paragraphs = [p.strip() for p in paragraphs[0].split('\n') if p.strip()]
        if len(sub_paragraphs) > 1:
            paragraphs = sub_paragraphs

    sections = []
    for i, para in enumerate(paragraphs):
        # 取前 30 字作为 subtitle
        subtitle = para[:30].replace('\n', ' ').strip()
        if len(para) > 30:
            subtitle += "..."
        sections.append(SectionContent(
            section_number=i + 1,
            subtitle=subtitle,
            content=para,
            word_count=len(para),
            gold_seed=None,
        ))

    if not sections:
        # 极端情况：文本为空或全是空白
        sections = [SectionContent(
            section_number=1,
            subtitle="正文",
            content=text.strip(),
            word_count=len(text.strip()),
            gold_seed=None,
        )]

    # 构造大纲 sections（供 Agent D 使用 ContentGenerationInput.sections）
    brief_sections = [
        SectionBrief(
            section_number=s.section_number,
            subtitle=s.subtitle,
            word_estimate=s.word_count,
        )
        for s in sections
    ]

    return AgentAOutput(
        style_anchor="用户原文风格",
        full_text=text.strip(),
        total_word_count=len(text.strip()),
        section_count=len(sections),
        sections=sections,
        gold_seeds=[],
    ), ContentGenerationInput(
        topic_title=title or "文案润色",
        sections=brief_sections,
    )


def _update_gold_sentences_for_rewritten_text(
    gold_sentences: list,
    rewritten_text: str,
) -> list:
    """Agent C 改写后，金句文本可能已变化，用模糊匹配更新金句 content。"""

    def normalize(s: str) -> str:
        return re.sub(r'[\s　]+', '', re.sub(r'[，。！？；：（）【】、""''—–\-.,!?;:()\[\]{}"\'\']', '', s))

    def strip_prefix(s: str) -> str:
        return re.sub(r'^[\s—–\-:=：·•>】\]）)]*(?:金句|金句内容|金句文本|去AI味|改写|rewrite|句子|内容|文本)[\s：:—–\-]*', '', s).strip()

    def find_best_match(gold_text: str, text: str) -> str:
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
        content = gs.get("content", "") if isinstance(gs, dict) else gs.content
        new_content = find_best_match(content, rewritten_text)
        if isinstance(gs, dict):
            gs_copy = dict(gs)
            gs_copy["content"] = new_content
            gs_copy["word_count"] = len(new_content)
            updated.append(gs_copy)
        else:
            if new_content != content:
                updated.append(gs.model_copy(update={
                    'content': new_content,
                    'word_count': len(new_content),
                }))
            else:
                updated.append(gs)
    return updated


# 前置流水线产物（B/D/E 的结果），供单模型和多模型对比共享
PolishPrefix = tuple  # (agent_a_output, cg_input, agent_b_output, agent_d_output, agent_e_output)


async def run_polish_prefix(
    inp: PolishInput,
    provider: Optional[str] = None,
    progress_callback: Optional[Callable] = None,
) -> PolishPrefix:
    """运行润色前置流水线：构造虚拟 A → Agent B → D → E。

    这部分与「用哪个模型改写」无关（Agent E 始终用 Kimi），
    多模型对比时只需跑一次共享，避免把最慢的联网纠错重复跑多遍。
    """
    title = inp.title or "文案润色"
    logger.info(f"[文案润色] 前置流水线开始，标题: {title}，原始字数: {len(inp.text)}")

    agent_a_output, cg_input = _build_virtual_agent_a_output(inp.text, inp.title)

    # Phase 0: 从用户原文提取事实素材包，注入 cg_input 供 Agent D 对比检测
    try:
        from app.services.user_source_extractor import extract_facts_from_user_text
        source_material = await extract_facts_from_user_text(inp.text, task_type="polish", provider=provider)
        if source_material:
            cg_input = cg_input.model_copy(update={"source_materials": source_material})
            logger.info("[文案润色] 事实素材包已注入")
    except Exception as e:
        logger.warning(f"[文案润色] 事实提取失败（不影响主流程）: {e}")

    # Step 1: Agent B — 金句催化员
    logger.info("[文案润色] Step 1/4: Agent B 金句催化")
    if progress_callback:
        await progress_callback({
            "event": "step_start",
            "data": {
                "step": 1,
                "agent": "居怀金 · 金句催化员",
                "action": "正在催化 3-5 个金句...",
                "avatar": "/agents/content-b.png",
            },
        })
    try:
        agent_b_output = await catalyze_gold_sentences(
            agent_a_output=agent_a_output,
            topic_title=title,
            provider=provider,
        )
    except Exception as e:
        logger.error(f"[文案润色] Agent B 失败: {e}")
        raise RuntimeError(f"文案润色失败（Agent B 金句催化）: {e}") from e

    for gs in agent_b_output.sentences:
        gs.content = _clean_punctuation(gs.content)

    if progress_callback:
        await progress_callback({"event": "step_done", "data": {"step": 1, "agent": "Agent B"}})

    # Step 2: Agent D — 事实总结员
    logger.info("[文案润色] Step 2/4: Agent D 事实性错误扫描")
    if progress_callback:
        await progress_callback({
            "event": "step_start",
            "data": {
                "step": 2,
                "agent": "韩知微 · 事实总结员",
                "action": "正在扫描事实性陈述...",
                "avatar": "/agents/content-d.png",
            },
        })
    try:
        agent_d_output = await summarize_factual_errors(
            inp=cg_input,
            agent_a_output=agent_a_output,
            agent_b_output=agent_b_output,
            provider=provider,
        )
    except Exception as e:
        logger.error(f"[文案润色] Agent D 失败: {e}")
        raise RuntimeError(f"文案润色失败（Agent D 事实扫描）: {e}") from e

    if progress_callback:
        await progress_callback({"event": "step_done", "data": {"step": 2, "agent": "Agent D"}})

    # Step 3: Agent E — Kimi 联网纠错员
    logger.info("[文案润色] Step 3/4: Agent E 联网纠错")
    if progress_callback:
        await progress_callback({
            "event": "step_start",
            "data": {
                "step": 3,
                "agent": "齐鉴真 · 联网纠错员",
                "action": "正在联网验证事实...",
                "avatar": "/agents/content-e.png",
            },
        })
    try:
        agent_e_output = await kimi_correct_facts(
            inp=cg_input,
            agent_a_output=agent_a_output,
            agent_b_output=agent_b_output,
            agent_d_output=agent_d_output,
        )
    except Exception as e:
        logger.error(f"[文案润色] Agent E 失败: {e}")
        raise RuntimeError(f"文案润色失败（Agent E 联网纠错）: {e}") from e

    if progress_callback:
        await progress_callback({"event": "step_done", "data": {"step": 3, "agent": "Agent E"}})

    return (agent_a_output, cg_input, agent_b_output, agent_d_output, agent_e_output)


async def run_polish_factcheck(
    inp: PolishInput,
    provider: Optional[str] = None,
    progress_callback: Optional[Callable] = None,
) -> tuple:
    """共享前置（仅事实核查 D + 联网纠错 E）。

    金句不参与这一步（用空清单），因此可在多模型对比时只跑一次共享：
    各方案的金句各自催化，但事实核查 / 联网纠错的结果是同一份。

    Returns:
        (agent_a_output, cg_input, agent_d_output, agent_e_output)
    """
    agent_a_output, cg_input = _build_virtual_agent_a_output(inp.text, inp.title)

    # Phase 0: 从用户原文提取事实素材包，注入 cg_input 供 Agent D 对比检测
    try:
        from app.services.user_source_extractor import extract_facts_from_user_text
        source_material = await extract_facts_from_user_text(inp.text, task_type="polish", provider=provider)
        if source_material:
            cg_input = cg_input.model_copy(update={"source_materials": source_material})
    except Exception as e:
        logger.warning(f"[文案润色] 事实提取失败（不影响主流程）: {e}")

    # 空金句清单（绕过 min_length=3 校验），D/E 只核查原文事实
    empty_b = AgentBOutput.model_construct(sentences=[], stats={})

    # Step: Agent D — 事实总结员
    logger.info("[文案润色] 共享前置 D 事实性错误扫描")
    if progress_callback:
        await progress_callback({
            "event": "step_start",
            "data": {
                "step": 2,
                "agent": "韩知微 · 事实总结员",
                "action": "正在扫描事实性陈述...",
                "avatar": "/agents/content-d.png",
            },
        })
    try:
        agent_d_output = await summarize_factual_errors(
            inp=cg_input,
            agent_a_output=agent_a_output,
            agent_b_output=empty_b,
            provider=provider,
        )
    except Exception as e:
        logger.error(f"[文案润色] Agent D 失败: {e}")
        raise RuntimeError(f"文案润色失败（Agent D 事实扫描）: {e}") from e
    if progress_callback:
        await progress_callback({"event": "step_done", "data": {"step": 2, "agent": "Agent D"}})

    # Step: Agent E — Kimi 联网纠错员
    logger.info("[文案润色] 共享前置 E 联网纠错")
    if progress_callback:
        await progress_callback({
            "event": "step_start",
            "data": {
                "step": 3,
                "agent": "齐鉴真 · 联网纠错员",
                "action": "正在联网验证事实...",
                "avatar": "/agents/content-e.png",
            },
        })
    try:
        agent_e_output = await kimi_correct_facts(
            inp=cg_input,
            agent_a_output=agent_a_output,
            agent_b_output=empty_b,
            agent_d_output=agent_d_output,
        )
    except Exception as e:
        logger.error(f"[文案润色] Agent E 失败: {e}")
        raise RuntimeError(f"文案润色失败（Agent E 联网纠错）: {e}") from e
    if progress_callback:
        await progress_callback({"event": "step_done", "data": {"step": 3, "agent": "Agent E"}})

    return (agent_a_output, cg_input, agent_d_output, agent_e_output)


async def run_gold_sentences(
    inp: PolishInput,
    agent_a_output: AgentAOutput,
    provider: Optional[str] = None,
) -> AgentBOutput:
    """单独催化金句（Agent B）。多模型对比时各方案各跑各的，金句不共享。"""
    title = inp.title or "文案润色"
    try:
        agent_b_output = await catalyze_gold_sentences(
            agent_a_output=agent_a_output,
            topic_title=title,
            provider=provider,
        )
    except Exception as e:
        logger.error(f"[文案润色] Agent B 失败: {e}")
        raise RuntimeError(f"文案润色失败（Agent B 金句催化）: {e}") from e
    for gs in agent_b_output.sentences:
        gs.content = _clean_punctuation(gs.content)
    return agent_b_output


async def finalize_polish(
    prefix: PolishPrefix,
    provider: Optional[str] = None,
    progress_callback: Optional[Callable] = None,
) -> PolishOutput:
    """用指定 provider 跑 Agent C 去 AI 味改写，并汇总成 PolishOutput。

    prefix 为 run_polish_prefix 的产物，可被多个 provider 共享（只读）。
    """
    start_time = time.time()
    agent_a_output, cg_input, agent_b_output, agent_d_output, agent_e_output = prefix

    # Step 4: Agent C — 去 AI 味改写员
    logger.info("[文案润色] Step 4/4: Agent C 去 AI 味改写")
    if progress_callback:
        await progress_callback({
            "event": "step_start",
            "data": {
                "step": 4,
                "agent": "景澄之 · 正文改写员",
                "action": "正在去 AI 味改写...",
                "avatar": "/agents/content-c.png",
            },
        })
    try:
        agent_c_output = await deai_rewrite(
            agent_a_output=agent_a_output,
            agent_b_output=agent_b_output,
            corrected_text=agent_e_output.corrected_text,
            provider=provider,
            weave_gold_sentences=True,
        )
    except Exception as e:
        logger.error(f"[文案润色] Agent C 失败: {e}")
        raise RuntimeError(f"文案润色失败（Agent C 去AI味改写）: {e}") from e

    if progress_callback:
        await progress_callback({"event": "step_done", "data": {"step": 4, "agent": "Agent C"}})

    # ──────────────────────────────────────────
    # 汇总输出
    # ──────────────────────────────────────────

    # 更新金句文本匹配
    updated_gold_sentences = _update_gold_sentences_for_rewritten_text(
        agent_b_output.sentences,
        agent_c_output.rewritten_text,
    )

    # 序列化金句
    gold_sentences_data = []
    for gs in updated_gold_sentences:
        if isinstance(gs, dict):
            gold_sentences_data.append(gs)
        else:
            gold_sentences_data.append({
                "sentence_id": gs.sentence_id,
                "sentence_type": gs.sentence_type,
                "location": gs.location,
                "section_number": gs.section_number,
                "insert_method": gs.insert_method,
                "content": gs.content,
                "word_count": gs.word_count,
            })

    # 序列化事实总结
    factual_summary_data = None
    if agent_d_output:
        factual_summary_data = {
            "summary_text": agent_d_output.summary_text,
            "potential_errors": [
                {
                    "claim": e.claim,
                    "error_type": e.error_type,
                    "section_number": e.section_number,
                    "reason": e.reason,
                    "search_query": e.search_query,
                }
                for e in agent_d_output.potential_errors
            ],
            "total_claims_checked": agent_d_output.total_claims_checked,
            "error_count": agent_d_output.error_count,
        }

    # 序列化纠错报告
    factual_corrections_data = None
    if agent_e_output:
        factual_corrections_data = {
            "corrected_word_count": agent_e_output.corrected_word_count,
            "corrections": [
                {
                    "original_claim": c.original_claim,
                    "corrected_claim": c.corrected_claim,
                    "error_type": c.error_type,
                    "section_number": c.section_number,
                    "search_result": c.search_result,
                    "confidence": c.confidence,
                }
                for c in agent_e_output.corrections
            ],
            "total_corrections": agent_e_output.total_corrections,
            "high_confidence_corrections": agent_e_output.high_confidence_corrections,
        }

    # 序列化改写对照表
    rewrite_table_data = []
    for it in (agent_c_output.rewrite_table or []):
        rewrite_table_data.append({
            "location": it.location,
            "ai_taste_type": it.ai_taste_type,
            "ai_taste_subtype": it.ai_taste_subtype,
            "priority": it.priority,
            "original_text": it.original_text,
            "rewritten_text": it.rewritten_text,
            "reason": it.reason,
        })

    output = PolishOutput(
        polished_text=agent_c_output.rewritten_text,
        polished_word_count=agent_c_output.rewritten_word_count,
        original_word_count=agent_a_output.total_word_count,
        gold_sentences=gold_sentences_data,
        factual_summary=factual_summary_data,
        factual_corrections=factual_corrections_data,
        rewrite_table=rewrite_table_data,
        skipped_sections=agent_c_output.skipped_sections,
        quality_check=agent_c_output.quality_check,
        agent_b_sentence_count=len(agent_b_output.sentences),
        agent_c_rewrite_count=len(agent_c_output.rewrite_table),
        agent_d_error_count=agent_d_output.error_count,
        agent_e_correction_count=agent_e_output.total_corrections,
        word_change_pct=agent_c_output.word_change_pct,
    )

    elapsed = time.time() - start_time
    logger.info(
        f"[文案润色] 完成，耗时: {elapsed:.1f}s，"
        f"原始字数: {output.original_word_count}，"
        f"润色后字数: {output.polished_word_count}，"
        f"变化: {output.word_change_pct}%，"
        f"金句: {output.agent_b_sentence_count}，"
        f"纠错: {output.agent_e_correction_count} 处"
    )

    if progress_callback:
        await progress_callback({"event": "complete", "data": {"step": 4, "agent": "Agent C"}})

    return output


async def polish_content(
    inp: PolishInput,
    progress_callback: Optional[Callable] = None,
    provider: Optional[str] = None,
) -> PolishOutput:
    """文案润色主流程：Agent B → D → E → C。

    单模型路径：前置流水线 + 用同一 provider 跑改写。
    """
    prefix = await run_polish_prefix(inp, provider=provider, progress_callback=progress_callback)
    return await finalize_polish(prefix, provider=provider, progress_callback=progress_callback)
