"""会议协作 Celery 任务。"""

import asyncio
import logging
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.celery_app import celery_app
from app.core.progress import progress_store
from app.db.session import AsyncSessionLocal
from app.models.meeting import Meeting, MeetingSynthesis
from app.services.meeting_synthesis import extract_meeting_synthesis
from app.services.meeting_methodology_dedup import sync_methodology_clusters

logger = logging.getLogger(__name__)


async def _push(run_id: Optional[str], event: dict) -> None:
    if run_id:
        await progress_store.push(run_id, event)


async def _run_meeting_extraction(meeting_id: int, run_id: Optional[str], task_id: Optional[str]) -> dict:
    async with AsyncSessionLocal() as db:
        meeting = (await db.execute(
            select(Meeting)
            .where(Meeting.id == meeting_id)
            .options(selectinload(Meeting.synthesis))
            .with_for_update()
        )).scalar_one_or_none()
        if meeting is None:
            await _push(run_id, {"event": "error", "data": {"message": "会议不存在"}})
            return {"status": "failed", "meeting_id": meeting_id, "error": "会议不存在"}

        if run_id is None:
            run_id = progress_store.create_run(user_id=meeting.created_by)

        # API 层已用 extracting 状态做重复请求保护；旧消息或 Celery 重投时，
        # 已完成的会议直接跳过，避免重新插入建议。
        if meeting.status != "extracting":
            await _push(
                run_id,
                {
                    "event": "result",
                    "data": {"meeting_id": meeting.id, "skipped": True},
                },
            )
            return {"status": "skipped", "meeting_id": meeting.id}

        if task_id and not meeting.extract_task_id:
            meeting.extract_task_id = task_id
            await db.commit()

        await _push(
            run_id,
            {
                "event": "step_start",
                "data": {
                    "step": 1,
                    "agent": "meeting-synthesizer",
                    "action": "正在阅读会议纪要并整理结论、方法论和对齐清单",
                },
            },
        )

        try:
            synthesis_data = await extract_meeting_synthesis(
                meeting.raw_text,
                meeting.title,
            )
            synthesis = meeting.synthesis
            if synthesis is None:
                synthesis = MeetingSynthesis(meeting_id=meeting.id)
                db.add(synthesis)

            if not synthesis.is_manually_edited:
                for field in (
                    "summary",
                    "methodology",
                    "checklist",
                    "decisions",
                    "disagreements",
                    "open_questions",
                    "follow_ups",
                    "raw_json",
                    "parse_status",
                ):
                    setattr(synthesis, field, synthesis_data[field])
                dedup_synthesis = synthesis_data
            else:
                # 人工修订的正文不被重新提取覆盖，但保留新一轮原始输出，
                # 方便人工比较和决定是否采纳新的沉淀。
                synthesis.raw_json = synthesis_data["raw_json"]
                synthesis.parse_status = synthesis_data["parse_status"]
                dedup_synthesis = {
                    "methodology": synthesis.methodology or [],
                    "checklist": synthesis.checklist or [],
                }

            methodology_count = len(dedup_synthesis.get("methodology") or [])
            checklist_count = len(dedup_synthesis.get("checklist") or [])
            open_question_count = len(synthesis.open_questions or [])
            manually_preserved = bool(synthesis.is_manually_edited)
            meeting.status = "ready"
            await db.commit()
            dedup_stats = {"source_count": 0, "new_clusters": 0, "merged": 0, "reviewed": 0}
            try:
                dedup_stats = await sync_methodology_clusters(
                    db,
                    meeting.id,
                    dedup_synthesis,
                )
                await db.commit()
            except Exception as dedup_exc:
                # 语义投影是可重建的，不能因为 embedding/归并失败把主整理标记成失败。
                await db.rollback()
                logger.warning(
                    "会议方法论语义归并失败，保留主沉淀 meeting_id=%s: %s",
                    meeting.id,
                    dedup_exc,
                    exc_info=True,
                )
            await _push(run_id, {"event": "step_done", "data": {"step": 1}})
            result = {
                "meeting_id": meeting.id,
                "methodology_count": methodology_count,
                "checklist_count": checklist_count,
                "open_question_count": open_question_count,
                "manually_preserved": manually_preserved,
                "dedup": dedup_stats,
                "status": "ready",
            }
            await _push(run_id, {"event": "result", "data": result})
            return result
        except Exception as exc:
            await db.rollback()
            logger.error("会议方法论整理失败 meeting_id=%s: %s", meeting_id, exc, exc_info=True)
            failed_meeting = (await db.execute(
                select(Meeting).where(Meeting.id == meeting_id)
            )).scalar_one_or_none()
            if failed_meeting is not None:
                failed_meeting.status = "failed"
                await db.commit()
            message = str(exc)[:500] or "会议方法论整理失败"
            await _push(run_id, {"event": "error", "data": {"message": message}})
            return {"meeting_id": meeting_id, "status": "failed", "error": message}


@celery_app.task(bind=True, name="meetings.extract_suggestions", max_retries=0)
def extract_meeting_suggestions_task(
    self,
    meeting_id: int,
    run_id: Optional[str] = None,
) -> dict:
    """异步整理会议方法论；保留旧 task 名以兼容已提交的 Celery 消息。"""
    task_id = getattr(getattr(self, "request", None), "id", None)
    return asyncio.run(_run_meeting_extraction(meeting_id, run_id, task_id))
