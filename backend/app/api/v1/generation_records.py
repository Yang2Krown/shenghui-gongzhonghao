from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, get_current_user
from app.models.user import User
from app.models.generation_record import GenerationRecord
from app.crud.generation_record import list_records, get_record, create_record
from app.schemas.generation_record import GenerationRecordOut, GenerationRecordListOut

router = APIRouter()


class GenerationRecordCreateRequest(BaseModel):
    """创建生成记录请求"""
    type: str
    input_snapshot: dict = {}
    display_title: Optional[str] = None
    output_snapshot: Optional[dict] = None
    resume_context: dict = {}


@router.post("", response_model=dict)
async def create_generation_record(
    req: GenerationRecordCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """创建生成记录"""
    import uuid
    run_id = f"manual_{uuid.uuid4().hex[:16]}"

    record = await create_record(
        db,
        user_id=current_user.id,
        type=req.type,
        run_id=run_id,
        input_snapshot=req.input_snapshot,
        display_title=req.display_title,
        output_snapshot=req.output_snapshot,
        resume_context=req.resume_context,
    )

    # 如果有 output_snapshot，直接标记为完成
    if req.output_snapshot:
        from app.crud.generation_record import complete_record
        await complete_record(db, run_id=run_id, output_snapshot=req.output_snapshot)

    return {
        "code": 200,
        "data": GenerationRecordOut.model_validate(record).model_dump(),
    }


@router.get("", response_model=dict)
async def get_generation_records(
    page: int = 1,
    page_size: int = 20,
    type: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    records, total = await list_records(
        db,
        user_id=current_user.id,
        type_filter=type,
        page=page,
        page_size=page_size,
    )
    return {
        "code": 200,
        "data": {
            "items": [GenerationRecordListOut.model_validate(r).model_dump() for r in records],
            "total": total,
            "page": page,
            "page_size": page_size,
        },
    }


@router.get("/by-candidate/{candidate_id}", response_model=dict)
async def get_records_by_candidate(
    candidate_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取某个选题下所有生成记录（按时间倒序），用于恢复创作状态。

    只返回 completed 状态的记录，每种 type 只返回最新一条。
    """
    result = await db.execute(
        select(GenerationRecord)
        .where(
            GenerationRecord.user_id == current_user.id,
            GenerationRecord.candidate_id == candidate_id,
            GenerationRecord.status == "completed",
        )
        .order_by(desc(GenerationRecord.created_at))
    )
    all_records = result.scalars().all()

    # 每种 type 只保留最新一条
    seen_types = set()
    latest = []
    for r in all_records:
        if r.type not in seen_types:
            seen_types.add(r.type)
            latest.append(r)

    return {
        "code": 200,
        "data": [GenerationRecordOut.model_validate(r).model_dump() for r in latest],
    }


@router.get("/{record_id}", response_model=dict)
async def get_generation_record(
    record_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    record = await get_record(db, record_id=record_id)
    if not record or record.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="记录不存在")
    return {
        "code": 200,
        "data": GenerationRecordOut.model_validate(record).model_dump(),
    }
