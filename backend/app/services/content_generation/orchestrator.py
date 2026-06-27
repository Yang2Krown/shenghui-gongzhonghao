"""正文生成编排器。

串联 资讯总结 → Agent A → Agent B → Agent C，完成从选题+大纲到最终正文的全流程。
4 步：资讯总结（防幻觉事实清单）→ 写正文 → 造金句 → 去 AI 味
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
from app.services.content_generation.agent_c_deai import deai_rewrite

logger = logging.getLogger(__name__)


def _clean_punctuation(text: str) -> str:
    """清理金句/正文中不必要的标点符号。

    公众号文章不需要新闻报纸式的排版符号，保持排版美观、阅读流畅。
    """
    # 双引号/单引号
    text = text.replace('“', '').replace('”', '')
    text = text.replace('‘', '').replace('’', '')
    text = text.replace('"', '').replace('"', '')
    # 书名号
    text = text.replace('《', '').replace('》', '')
    # 「」引号
    text = text.replace('「', '').replace('」', '')
    # 破折号
    text = text.replace('——', '，')
    return text.strip()


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
    db_session=None,
) -> ContentGenerationOutput:
    """正文生成主流程：资讯总结（Step 1）→ Agent A → Agent B → Agent C。

    资讯总结：读取该话题已落库的原始资讯（或用户上传的素材），提炼一份简短的
    防幻觉事实清单（时间/地点/事件/人物/产品名等），贯穿写正文及后续步骤，
    防止大模型幻觉。

    Args:
        inp: 正文生成总输入（选题 + 大纲 + 标题 + 风格参数）
        progress_callback: 进度回调（可选）
        db_session: 数据库会话（用于查询 RawInfo，可选）

    Returns:
        ContentGenerationOutput: 最终正文 + 金句 + 改写对照表

    Raises:
        ValueError: 输入校验失败
        RuntimeError: Agent 执行异常
    """
    start_time = time.time()
    logger.info(f"[正文生成] 开始，标题: {inp.topic_title}")

    # ──────────────────────────────────────────
    # Step 1: 资讯总结（读原始资讯，提炼防幻觉事实清单）
    # ──────────────────────────────────────────
    source_material_text = inp.source_materials  # 已有则跳过
    if not source_material_text and inp.candidate_id and db_session:
        logger.info("[正文生成] Step 1/4: 资讯总结，提炼事实清单")
        if progress_callback:
            await progress_callback({"event": "step_start", "data": {"step": 1, "agent": "沈觅源 · 资讯总结员", "action": "正在通读原始资讯，提炼关键事实...", "avatar": "/agents/source.png"}})
        try:
            from app.services.content_generation.source_collector import collect_source_materials
            # 查询 candidate 的 cluster_id
            cluster_id = None
            from sqlalchemy.ext.asyncio import AsyncSession
            if isinstance(db_session, AsyncSession):
                from sqlalchemy import select
                from app.models.topic_candidate import TopicCandidate
                cand_result = await db_session.execute(
                    select(TopicCandidate.info_cluster_id).where(TopicCandidate.id == inp.candidate_id)
                )
                row = cand_result.first()
                cluster_id = row[0] if row else None
            else:
                from app.models.topic_candidate import TopicCandidate
                cand = db_session.query(TopicCandidate.info_cluster_id).filter(
                    TopicCandidate.id == inp.candidate_id
                ).first()
                cluster_id = cand[0] if cand else None

            if cluster_id:
                material = await collect_source_materials(
                    cluster_id=cluster_id,
                    sections=inp.sections,
                    db_session=db_session,
                )
                if material and material.total_facts > 0:
                    source_material_text = material.to_prompt_text(inp.sections)
                    logger.info(f"[正文生成] 事实素材搜集完成: {material.total_facts} 条事实")
                else:
                    logger.warning("[正文生成] 未搜集到事实素材，将使用 source_summary 兜底")
            else:
                logger.warning("[正文生成] 无 cluster_id，跳过事实搜集")
        except Exception as e:
            logger.error(f"[正文生成] 事实搜集失败（不影响主流程）: {e}")

        if progress_callback:
            await progress_callback({"event": "step_done", "data": {"step": 1, "agent": "沈觅源 · 资讯总结员"}})

    # 将素材包注入 inp（不影响原始 inp，创建副本）
    if source_material_text:
        inp = inp.model_copy(update={"source_materials": source_material_text})

    # ──────────────────────────────────────────
    # Step 2: Agent A — 正文创作员
    # ──────────────────────────────────────────
    logger.info("[正文生成] Step 2/4: Agent A 生成正文骨干")
    if progress_callback:
        await progress_callback({"event": "step_start", "data": {"step": 2, "agent": "温如言 · 正文创作员", "action": "正在按节撰写初稿...", "avatar": "/agents/content-a.png"}})
    try:
        agent_a_output = await generate_article(inp)
    except Exception as e:
        logger.error(f"[正文生成] Agent A 失败: {e}")
        raise RuntimeError(f"正文生成失败（Agent A）: {e}") from e

    if progress_callback:
        await progress_callback({"event": "step_done", "data": {"step": 2, "agent": "Agent A"}})

    # 异常处理：字数严重不足
    if agent_a_output.total_word_count < 1700:
        logger.warning(
            f"[正文生成] Agent A 字数严重不足: {agent_a_output.total_word_count}，"
            f"建议丢回重试"
        )

    # ──────────────────────────────────────────
    # Step 3: Agent B — 金句催化员
    # ──────────────────────────────────────────
    logger.info("[正文生成] Step 3/4: Agent B 催化金句")
    if progress_callback:
        await progress_callback({"event": "step_start", "data": {"step": 3, "agent": "居怀金 · 正文催化员", "action": "正在催化 3-5 个金句...", "avatar": "/agents/content-b.png"}})
    try:
        agent_b_output = await catalyze_gold_sentences(
            agent_a_output=agent_a_output,
            topic_title=inp.topic_title,
        )
    except Exception as e:
        logger.error(f"[正文生成] Agent B 失败: {e}")
        raise RuntimeError(f"正文生成失败（Agent B）: {e}") from e

    # 清理金句中的不必要标点符号
    for gs in agent_b_output.sentences:
        gs.content = _clean_punctuation(gs.content)

    if progress_callback:
        await progress_callback({"event": "step_done", "data": {"step": 3, "agent": "Agent B"}})

    # ──────────────────────────────────────────
    # Step 4: Agent C — 去 AI 味改写员
    # ──────────────────────────────────────────
    logger.info("[正文生成] Step 4/4: Agent C 去 AI 味改写")
    if progress_callback:
        await progress_callback({"event": "step_start", "data": {"step": 4, "agent": "景澄之 · 正文改写员", "action": "正在去 AI 味改写...", "avatar": "/agents/content-c.png"}})
    try:
        agent_c_output = await deai_rewrite(
            agent_a_output=agent_a_output,
            agent_b_output=agent_b_output,
        )
    except Exception as e:
        logger.error(f"[正文生成] Agent C 失败: {e}")
        raise RuntimeError(f"正文生成失败（Agent C）: {e}") from e

    if progress_callback:
        await progress_callback({"event": "step_done", "data": {"step": 4, "agent": "Agent C"}})

    # 异常处理：改写字数变化超限
    if abs(agent_c_output.word_change_pct) > 10:
        logger.warning(
            f"[正文生成] Agent C 字数变化超限: {agent_c_output.word_change_pct}%，"
            f"建议回退到改写前版本"
        )

    # ──────────────────────────────────────────
    # 汇总输出
    # ──────────────────────────────────────────

    # 最终清理：去除 LLM 可能残留的节标签前缀
    final_text = agent_c_output.rewritten_text
    # 去掉正文段落中可能出现的 【引入】【正文】【总结】 等标签
    final_text = re.sub(r'^\s*[\[【](?:引入|正文|总结|引言|结尾|概述|结语|开头|主体|中间|结尾段)[\]】]\s*', '', final_text, flags=re.MULTILINE)
    # 去掉 "第X节" 前缀
    final_text = re.sub(r'^\s*第[一二三四五六七八九十\d]+节\s*', '', final_text, flags=re.MULTILINE)
    # 去除不必要的排版符号（双引号""、单引号''、《》、——），公众号排版更干净
    final_text = _clean_punctuation(final_text)

    # 更新金句文本匹配
    updated_gold_sentences = _update_gold_sentences_for_rewritten_text(
        agent_b_output.sentences,
        final_text,
    )

    output = ContentGenerationOutput(
        final_text=final_text,
        final_word_count=agent_c_output.rewritten_word_count,
        section_count=agent_a_output.section_count,
        section_word_counts=[s.word_count for s in agent_a_output.sections],
        gold_sentences=updated_gold_sentences,
        rewrite_table=agent_c_output.rewrite_table,
        agent_a_word_count=agent_a_output.total_word_count,
        agent_b_sentence_count=len(agent_b_output.sentences),
        agent_c_rewrite_count=len(agent_c_output.rewrite_table),
        style_anchor=agent_a_output.style_anchor,
    )

    elapsed = time.time() - start_time
    logger.info(
        f"[正文生成] 完成，耗时: {elapsed:.1f}s，"
        f"最终字数: {output.final_word_count}"
    )

    if progress_callback:
        await progress_callback({"event": "complete", "data": {"step": 4, "agent": "Agent C"}})

    return output
