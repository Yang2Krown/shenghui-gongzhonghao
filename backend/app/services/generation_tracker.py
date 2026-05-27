"""生成记录追踪器 —— 在各 API 的入口和后台回调中自动写入记录。"""
from __future__ import annotations

import logging
from typing import Optional

from app.db.session import AsyncSessionLocal
from app.crud.generation_record import create_record, complete_record, fail_record

logger = logging.getLogger(__name__)


async def track_start(
    *,
    user_id: int,
    type: str,
    run_id: str,
    input_snapshot: dict,
    display_title: Optional[str] = None,
    parent_record_id: Optional[int] = None,
    creation_id: Optional[int] = None,
    candidate_id: Optional[int] = None,
    resume_context: Optional[dict] = None,
) -> int:
    """在 API 入口处调用，创建一条 pending 记录，返回 record_id。"""
    async with AsyncSessionLocal() as db:
        record = await create_record(
            db,
            user_id=user_id,
            type=type,
            run_id=run_id,
            input_snapshot=input_snapshot,
            display_title=display_title,
            parent_record_id=parent_record_id,
            creation_id=creation_id,
            candidate_id=candidate_id,
            resume_context=resume_context,
        )
        return record.id


async def track_complete(
    run_id: str,
    output_snapshot: dict,
    display_title: Optional[str] = None,
) -> None:
    """在后台任务成功后调用，回填结果。"""
    try:
        async with AsyncSessionLocal() as db:
            await complete_record(
                db, run_id=run_id,
                output_snapshot=output_snapshot,
                display_title=display_title,
            )
    except Exception:
        logger.exception(f"track_complete failed for run_id={run_id}")


async def track_fail(run_id: str, error_msg: str) -> None:
    """在后台任务失败后调用。"""
    try:
        async with AsyncSessionLocal() as db:
            await fail_record(db, run_id=run_id, error_msg=error_msg)
    except Exception:
        logger.exception(f"track_fail failed for run_id={run_id}")
