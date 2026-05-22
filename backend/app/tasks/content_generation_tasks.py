"""正文生成 Celery 任务。

编排：Agent A（正文创作）→ Agent B（金句催化）→ Agent C（去 AI 味）→ Agent D（整合自检）。
与选题挖掘任务（topic_mining_tasks）完全独立，不干扰选题流程。
"""

import asyncio
import logging
from typing import Optional

from sqlalchemy.orm import Session

from app.core.celery_app import celery_app
from app.db.session import SessionLocal
from app.models.creation import ContentCreation
from app.models.outline import Outline
from app.models.topic_candidate import TopicCandidate
from app.services.content_generation.schemas import (
    ContentGenerationInput,
    SectionBrief,
    StyleParams,
)

logger = logging.getLogger(__name__)


def _build_input_from_db(
    db: Session,
    candidate_id: int,
    outline_id: int,
    user_id: Optional[int] = None,
    style_params: Optional[dict] = None,
) -> ContentGenerationInput:
    """从数据库构建 ContentGenerationInput。"""
    # 查询选题候选
    candidate = db.query(TopicCandidate).filter(TopicCandidate.id == candidate_id).first()
    if not candidate:
        raise ValueError(f"TopicCandidate {candidate_id} 不存在")

    # 查询大纲
    outline = db.query(Outline).filter(Outline.id == outline_id).first()
    if not outline:
        raise ValueError(f"Outline {outline_id} 不存在")

    # 构建大纲节列表
    sections = []
    for i, sec in enumerate(outline.sections or []):
        sections.append(SectionBrief(
            section_number=i + 1,
            subtitle=sec.get("subtitle", sec.get("title", f"第{i+1}节")),
            core_points=sec.get("core_points", []),
            spread_role=sec.get("spread_role"),
            word_estimate=sec.get("word_estimate", 500),
            notes=sec.get("notes"),
        ))

    # 构建风格参数
    sp = None
    if style_params:
        sp = StyleParams(
            tone=style_params.get("tone"),
            banned_words=style_params.get("banned_words", []),
            preferred_words=style_params.get("preferred_words", []),
            sample_articles=style_params.get("sample_articles", []),
        )

    return ContentGenerationInput(
        topic_title=candidate.title,
        topic_direction=candidate.direction,
        topic_routine=candidate.routine,
        value_promise=candidate.value_promise,
        outline_id=outline_id,
        sections=sections,
        style_params=sp,
        candidate_id=candidate_id,
        user_id=user_id,
    )


@celery_app.task(
    bind=True,
    name="content.generate_article",
    max_retries=1,
    default_retry_delay=60,
    time_limit=300,
    soft_time_limit=270,
)
def generate_article_task(
    self,
    candidate_id: int,
    outline_id: int,
    user_id: Optional[int] = None,
    style_params: Optional[dict] = None,
) -> dict:
    """正文生成 Celery 任务。

    流程：Agent A → Agent B → Agent C → Agent D → 落库。

    Args:
        candidate_id: 选题候选 ID
        outline_id: 大纲 ID
        user_id: 用户 ID（可选）
        style_params: 风格参数（可选）

    Returns:
        {
            "creation_id": int,
            "final_word_count": int,
            "total_score": float,
            "recommended_action": str,
            "gold_sentence_count": int,
            "rewrite_count": int,
        }
    """
    from app.services.content_generation.orchestrator import generate_content

    db = SessionLocal()
    try:
        # 构建输入
        inp = _build_input_from_db(db, candidate_id, outline_id, user_id, style_params)

        logger.info(f"开始正文生成，选题: {inp.topic_title}")

        # 执行 4 Agent 流程
        output = asyncio.run(generate_content(inp))

        # 落库：创建 ContentCreation 记录
        creation = ContentCreation(
            user_id=user_id or 1,
            topic_id=candidate_id,
            title=inp.topic_title,
            content=output.final_text,
            status="draft",
            word_count=output.final_word_count,
            summary=output.gold_sentences[0].content if output.gold_sentences else None,
        )
        db.add(creation)
        db.flush()

        # 保存诊断报告到 creation 的 tags 或单独的表
        # 这里暂时用 tags 存储关键信息
        creation.tags = [
            f"score:{output.diagnosis.total_score}",
            f"action:{output.diagnosis.recommended_action}",
            f"gold:{len(output.gold_sentences)}",
            f"rewrite:{len(output.rewrite_table)}",
        ]

        db.commit()

        logger.info(
            f"正文生成完成，creation_id: {creation.id}，"
            f"字数: {output.final_word_count}，"
            f"总分: {output.diagnosis.total_score}/10"
        )

        return {
            "creation_id": creation.id,
            "final_word_count": output.final_word_count,
            "total_score": output.diagnosis.total_score,
            "recommended_action": output.diagnosis.recommended_action,
            "gold_sentence_count": len(output.gold_sentences),
            "rewrite_count": len(output.rewrite_table),
        }

    except Exception as exc:
        db.rollback()
        logger.exception(f"正文生成任务失败: {exc}")
        raise self.retry(exc=exc)
    finally:
        db.close()
