from datetime import datetime
from typing import Optional, Any
from pydantic import BaseModel


class GenerationRecordCreate(BaseModel):
    type: str
    run_id: str
    input_snapshot: dict = {}
    display_title: Optional[str] = None
    parent_record_id: Optional[int] = None
    creation_id: Optional[int] = None
    candidate_id: Optional[int] = None
    resume_context: dict = {}


class GenerationRecordOut(BaseModel):
    id: int
    user_id: int
    type: str
    run_id: str
    status: str
    input_snapshot: dict
    output_snapshot: Optional[Any] = None
    display_title: Optional[str] = None
    parent_record_id: Optional[int] = None
    creation_id: Optional[int] = None
    candidate_id: Optional[int] = None
    resume_context: dict
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class GenerationRecordListOut(BaseModel):
    id: int
    type: str
    status: str
    display_title: Optional[str] = None
    candidate_id: Optional[int] = None
    creation_id: Optional[int] = None
    resume_context: dict
    created_at: datetime

    class Config:
        from_attributes = True
