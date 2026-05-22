"""正文生成编排器。

串联 Agent A → B → C → D，完成从选题+大纲到最终正文的全流程。
设计对齐：《正文生成 Agent 设计文档 v1.1》第 7 节。
"""

import logging
import time
from typing import Optional

from app.services.content_generation.schemas import (
    ContentGenerationInput,
    ContentGenerationOutput,
)
from app.services.content_generation.agent_a_writer import generate_article
from app.services.content_generation.agent_b_gold_sentence import catalyze_gold_sentences
from app.services.content_generation.agent_c_deai import deai_rewrite
from app.services.content_generation.agent_d_inspector import (
    integrate_and_inspect,
    build_final_output,
)

logger = logging.getLogger(__name__)


async def generate_content(inp: ContentGenerationInput) -> ContentGenerationOutput:
    """正文生成主流程：Agent A → B → C → D。

    Args:
        inp: 正文生成总输入（选题 + 大纲 + 标题 + 风格参数）

    Returns:
        ContentGenerationOutput: 最终正文 + 金句 + 改写对照表 + 诊断报告

    Raises:
        ValueError: 输入校验失败
        RuntimeError: Agent 执行异常
    """
    start_time = time.time()
    logger.info(f"[正文生成] 开始，标题: {inp.topic_title}")

    # ──────────────────────────────────────────
    # Step 1: Agent A — 正文创作员
    # ──────────────────────────────────────────
    logger.info("[正文生成] Step 1/4: Agent A 生成正文骨干")
    try:
        agent_a_output = await generate_article(inp)
    except Exception as e:
        logger.error(f"[正文生成] Agent A 失败: {e}")
        raise RuntimeError(f"正文生成失败（Agent A）: {e}") from e

    # 异常处理：字数严重不足
    if agent_a_output.total_word_count < 1700:
        logger.warning(
            f"[正文生成] Agent A 字数严重不足: {agent_a_output.total_word_count}，"
            f"建议丢回重试"
        )

    # ──────────────────────────────────────────
    # Step 2: Agent B — 金句催化员
    # ──────────────────────────────────────────
    logger.info("[正文生成] Step 2/4: Agent B 催化金句")
    try:
        agent_b_output = await catalyze_gold_sentences(
            agent_a_output=agent_a_output,
            topic_title=inp.topic_title,
        )
    except Exception as e:
        logger.error(f"[正文生成] Agent B 失败: {e}")
        raise RuntimeError(f"正文生成失败（Agent B）: {e}") from e

    # ──────────────────────────────────────────
    # Step 3: Agent C — 去 AI 味改写员
    # ──────────────────────────────────────────
    logger.info("[正文生成] Step 3/4: Agent C 去 AI 味改写")
    try:
        agent_c_output = await deai_rewrite(
            agent_a_output=agent_a_output,
            agent_b_output=agent_b_output,
        )
    except Exception as e:
        logger.error(f"[正文生成] Agent C 失败: {e}")
        raise RuntimeError(f"正文生成失败（Agent C）: {e}") from e

    # 异常处理：改写字数变化超限
    if abs(agent_c_output.word_change_pct) > 10:
        logger.warning(
            f"[正文生成] Agent C 字数变化超限: {agent_c_output.word_change_pct}%，"
            f"建议回退到改写前版本"
        )

    # ──────────────────────────────────────────
    # Step 4: Agent D — 整合 + 自检诊断员
    # ──────────────────────────────────────────
    logger.info("[正文生成] Step 4/4: Agent D 整合 + 自检诊断")
    try:
        agent_d_output = await integrate_and_inspect(
            inp=inp,
            agent_a_output=agent_a_output,
            agent_b_output=agent_b_output,
            agent_c_output=agent_c_output,
        )
    except Exception as e:
        logger.error(f"[正文生成] Agent D 失败: {e}")
        raise RuntimeError(f"正文生成失败（Agent D）: {e}") from e

    # ──────────────────────────────────────────
    # 汇总输出
    # ──────────────────────────────────────────
    output = build_final_output(
        inp=inp,
        agent_a_output=agent_a_output,
        agent_b_output=agent_b_output,
        agent_c_output=agent_c_output,
        agent_d_output=agent_d_output,
    )

    elapsed = time.time() - start_time
    logger.info(
        f"[正文生成] 完成，耗时: {elapsed:.1f}s，"
        f"最终字数: {output.final_word_count}，"
        f"总分: {output.diagnosis.total_score}/10，"
        f"建议: {output.diagnosis.recommended_action}"
    )

    return output
