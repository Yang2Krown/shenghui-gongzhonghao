from __future__ import annotations

from typing import Optional, List, Tuple

from sqlalchemy import select, desc, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.generation_record import GenerationRecord


async def create_record(
    db: AsyncSession,
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
) -> GenerationRecord:
    record = GenerationRecord(
        user_id=user_id,
        type=type,
        run_id=run_id,
        input_snapshot=input_snapshot,
        display_title=display_title,
        parent_record_id=parent_record_id,
        creation_id=creation_id,
        candidate_id=candidate_id,
        resume_context=resume_context or {},
        status="pending",
    )
    db.add(record)
    await db.commit()
    await db.refresh(record)
    return record


async def complete_record(
    db: AsyncSession,
    *,
    run_id: str,
    output_snapshot: dict,
    display_title: Optional[str] = None,
) -> None:
    stmt = (
        update(GenerationRecord)
        .where(GenerationRecord.run_id == run_id)
        .values(status="completed", output_snapshot=output_snapshot)
    )
    if display_title is not None:
        stmt = stmt.values(display_title=display_title)
    await db.execute(stmt)
    await db.commit()


async def fail_record(db: AsyncSession, *, run_id: str, error_msg: str) -> None:
    await db.execute(
        update(GenerationRecord)
        .where(GenerationRecord.run_id == run_id)
        .values(status="failed", output_snapshot={"error": error_msg})
    )
    await db.commit()


async def list_records(
    db: AsyncSession,
    *,
    user_id: int,
    type_filter: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
) -> Tuple[List[GenerationRecord], int]:
    q = select(GenerationRecord).where(GenerationRecord.user_id == user_id)
    if type_filter:
        q = q.where(GenerationRecord.type == type_filter)

    count_q = select(GenerationRecord.id).where(GenerationRecord.user_id == user_id)
    if type_filter:
        count_q = count_q.where(GenerationRecord.type == type_filter)
    total = len((await db.execute(count_q)).all())

    q = q.order_by(desc(GenerationRecord.created_at))
    q = q.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(q)
    return list(result.scalars().all()), total


async def get_record(db: AsyncSession, *, record_id: int) -> Optional[GenerationRecord]:
    result = await db.execute(
        select(GenerationRecord).where(GenerationRecord.id == record_id)
    )
    return result.scalar_one_or_none()


async def get_record_by_run_id(db: AsyncSession, *, run_id: str) -> Optional[GenerationRecord]:
    result = await db.execute(
        select(GenerationRecord).where(GenerationRecord.run_id == run_id)
    )
    return result.scalar_one_or_none()
