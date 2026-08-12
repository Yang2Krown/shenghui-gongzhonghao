"""文章版本语义差异摘要 Celery 任务。"""

import asyncio
import logging
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.celery_app import celery_app
from app.core.progress import progress_store
from app.core.timezone import utcnow
from app.db.session import AsyncSessionLocal
from app.models.content_version import ContentVersion, ExperienceCard
from app.services.content_version_service import (
    build_experience_content,
    build_text_diff,
    get_pair_summary,
    set_pair_summary,
    summarize_version_diff,
)

logger = logging.getLogger(__name__)


async def _push(run_id: Optional[str], event: dict) -> None:
    if run_id:
        await progress_store.push(run_id, event)


async def _run_version_diff_summary(
    creation_id: int,
    before_version_id: int,
    after_version_id: int,
    run_id: Optional[str],
    task_id: Optional[str],
) -> dict:
    async with AsyncSessionLocal() as db:
        versions = (await db.execute(
            select(ContentVersion)
            .where(ContentVersion.id.in_([before_version_id, after_version_id]))
            .options(selectinload(ContentVersion.suggestion))
        )).scalars().all()
        by_id = {version.id: version for version in versions}
        before = by_id.get(before_version_id)
        after = by_id.get(after_version_id)
        if before is None or after is None:
            await _push(run_id, {"event": "error", "data": {"message": "版本不存在"}})
            return {"status": "failed", "error": "版本不存在"}
        if before.creation_id != creation_id or after.creation_id != creation_id:
            await _push(run_id, {"event": "error", "data": {"message": "版本不属于当前文章"}})
            return {"status": "failed", "error": "版本不属于当前文章"}

        existing = get_pair_summary(after.diff_summary, before_version_id, after_version_id)
        if existing and existing.get("status") == "succeeded":
            await _push(run_id, {"event": "result", "data": existing})
            return existing
        if existing and existing.get("task_id") not in (None, task_id):
            # API 层的行锁已保证同一版本对只投递一条任务；旧消息即使晚到，
            # 也不能覆盖用户刚刚重试后创建的新任务。
            return {"status": "skipped", "task_id": existing.get("task_id")}

        running = {
            **(existing or {}),
            "status": "running",
            "task_id": task_id or (existing or {}).get("task_id"),
            "run_id": run_id or (existing or {}).get("run_id"),
            "before_version_id": before_version_id,
            "after_version_id": after_version_id,
        }
        after.diff_summary = set_pair_summary(
            after.diff_summary,
            before_version_id,
            after_version_id,
            running,
        )
        await db.commit()

        await _push(
            run_id,
            {
                "event": "step_start",
                "data": {
                    "step": 1,
                    "agent": "version-diff-summarizer",
                    "action": "正在根据两个文章版本整理真实修改点",
                },
            },
        )
        try:
            suggestion_text = None
            if after.suggestion is not None:
                suggestion_text = after.suggestion.content
            elif before.suggestion is not None:
                suggestion_text = before.suggestion.content
            semantic = await summarize_version_diff(
                before.content_text,
                after.content_text,
                suggestion_text,
            )
            result = {
                "status": "succeeded",
                "task_id": task_id or running.get("task_id"),
                "run_id": run_id or running.get("run_id"),
                "before_version_id": before_version_id,
                "after_version_id": after_version_id,
                "summary": semantic["summary"],
                "changes": semantic["changes"],
                "suggestion_match": semantic.get("suggestion_match"),
                "raw_output": semantic.get("raw_output") or "",
                "parsed_at": utcnow().isoformat(),
                "model": semantic.get("model"),
                "usage": semantic.get("usage"),
                "finish_reason": semantic.get("finish_reason"),
            }
            # 重新查询并检查 task_id，避免一条晚到的旧任务覆盖重试结果。
            await db.refresh(after)
            current = get_pair_summary(after.diff_summary, before_version_id, after_version_id)
            if current and current.get("task_id") not in (None, result["task_id"]):
                return {"status": "skipped", "task_id": current.get("task_id")}
            after.diff_summary = set_pair_summary(
                after.diff_summary,
                before_version_id,
                after_version_id,
                result,
            )

            # 若用户在保存版本时先沉淀了经验，语义摘要完成后补充同一张卡片正文。
            cards = (await db.execute(
                select(ExperienceCard).where(
                    ExperienceCard.creation_id == creation_id,
                    ExperienceCard.source_type == "meeting_diff",
                )
            )).scalars().all()
            text_diff = build_text_diff(
                before.content_text,
                after.content_text,
                before_label=f"v{before.version_no}",
                after_label=f"v{after.version_no}",
            )
            updated_card_ids = []
            for card in cards:
                if not isinstance(card.version_pair, dict):
                    continue
                if not (
                    (card.version_pair.get("before") in (before_version_id, str(before_version_id), None))
                    and card.version_pair.get("after") in (after_version_id, str(after_version_id))
                ):
                    continue
                card.content = build_experience_content(
                    before_version=before,
                    after_version=after,
                    text_diff=text_diff,
                    note=after.note,
                    suggestion_text=suggestion_text,
                    semantic_summary=semantic,
                )
                card.embedding = None
                card.embedding_status = "pending"
                card.embedding_error = None
                updated_card_ids.append(card.id)

            await db.commit()
            if updated_card_ids:
                # 语义摘要补全了卡片正文后，原向量已经失效；重新走同一个
                # embedding 队列，避免卡片长期停留在 pending 状态。
                from app.services.experience_service import enqueue_embedding

                for card_id in updated_card_ids:
                    refreshed_card = (await db.execute(
                        select(ExperienceCard).where(ExperienceCard.id == card_id)
                    )).scalar_one_or_none()
                    if refreshed_card is not None:
                        await enqueue_embedding(refreshed_card, db)
            await _push(run_id, {"event": "step_done", "data": {"step": 1}})
            await _push(run_id, {"event": "result", "data": result})
            return result
        except Exception as exc:
            await db.rollback()
            raw_output = getattr(exc, "raw_output", "") or ""
            message = str(exc)[:1000] or "语义差异摘要失败"
            failed = (await db.execute(
                select(ContentVersion).where(ContentVersion.id == after_version_id)
            )).scalar_one_or_none()
            if failed is not None:
                current = get_pair_summary(failed.diff_summary, before_version_id, after_version_id) or {}
                if current.get("task_id") in (None, task_id):
                    failure = {
                        **current,
                        "status": "failed",
                        "task_id": task_id or current.get("task_id"),
                        "run_id": run_id or current.get("run_id"),
                        "before_version_id": before_version_id,
                        "after_version_id": after_version_id,
                        "summary": None,
                        "changes": [],
                        "suggestion_match": None,
                        "raw_output": raw_output,
                        "error": message,
                        "parsed_at": None,
                    }
                    failed.diff_summary = set_pair_summary(
                        failed.diff_summary,
                        before_version_id,
                        after_version_id,
                        failure,
                    )
                    await db.commit()
            logger.warning(
                "文章版本语义摘要失败 creation_id=%s before=%s after=%s: %s",
                creation_id,
                before_version_id,
                after_version_id,
                exc,
                exc_info=True,
            )
            await _push(run_id, {"event": "error", "data": {"message": message}})
            return {
                "status": "failed",
                "task_id": task_id,
                "run_id": run_id,
                "before_version_id": before_version_id,
                "after_version_id": after_version_id,
                "error": message,
                "raw_output": raw_output,
            }


@celery_app.task(bind=True, name="versions.summarize_diff", max_retries=0)
def summarize_version_diff_task(
    self,
    creation_id: int,
    before_version_id: int,
    after_version_id: int,
    run_id: Optional[str] = None,
) -> dict:
    task_id = getattr(getattr(self, "request", None), "id", None)
    return asyncio.run(
        _run_version_diff_summary(
            creation_id,
            before_version_id,
            after_version_id,
            run_id,
            task_id,
        )
    )
