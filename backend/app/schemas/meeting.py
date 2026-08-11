"""会议方法论沉淀与兼容行动项 API schema。"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, validator


MEETING_STATUSES = {"extracting", "ready", "failed"}
SUGGESTION_STATUSES = {
    "proposed",
    "adopted",
    "in_progress",
    "done",
    "rejected",
}
SUGGESTION_PRIORITIES = {"P0", "P1", "P2"}


class MeetingCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    meeting_at: datetime
    raw_text: str = Field(..., min_length=1, max_length=200000)
    source_kind: str = Field("pasted_text", max_length=20)

    @validator("title", "raw_text")
    def validate_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("内容不能为空")
        return value

    @validator("source_kind")
    def validate_source_kind(cls, value: str) -> str:
        value = value.strip().lower()
        if value != "pasted_text":
            raise ValueError("当前阶段只支持 pasted_text")
        return value


class MeetingSuggestionUpdate(BaseModel):
    content: Optional[str] = Field(None, min_length=1)
    proposer: Optional[str] = Field(None, max_length=50)
    category: Optional[str] = Field(None, min_length=1, max_length=50)
    priority: Optional[str] = None
    acceptance_criteria: Optional[str] = None
    status: Optional[str] = None
    owner_id: Optional[int] = Field(None, ge=1)
    resolution_note: Optional[str] = None

    @validator("content", "category")
    def require_action_text(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        value = value.strip()
        if not value:
            raise ValueError("建议内容和类别不能为空")
        return value

    @validator("proposer", "acceptance_criteria", "resolution_note")
    def strip_optional_text(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        value = value.strip()
        return value or None

    @validator("priority")
    def validate_priority(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        value = value.strip().upper()
        if value not in SUGGESTION_PRIORITIES:
            raise ValueError("优先级仅支持 P0 / P1 / P2")
        return value

    @validator("status")
    def validate_status(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        value = value.strip().lower()
        if value not in SUGGESTION_STATUSES:
            raise ValueError("建议状态不合法")
        return value


class MeetingSuggestionLinkRequest(BaseModel):
    creation_id: int = Field(..., ge=1)


class MeetingSynthesisUpdate(BaseModel):
    """人工修订会议沉淀；列表项保持 JSON 对象，便于后续增量扩展字段。"""

    summary: Optional[str] = Field(None, max_length=4000)
    methodology: Optional[list[dict]] = None
    checklist: Optional[list[dict]] = None
    decisions: Optional[list[dict]] = None
    disagreements: Optional[list[dict]] = None
    open_questions: Optional[list[dict]] = None
    follow_ups: Optional[list[dict]] = None

    @validator("summary")
    def strip_summary(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        value = value.strip()
        return value or None


class MeetingOut(BaseModel):
    id: int
    title: str
    meeting_at: datetime
    raw_text: str
    source_kind: str
    status: str
    created_by: int
    extract_task_id: Optional[str] = None
    extract_run_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class MeetingListResponse(BaseModel):
    items: list[dict]
    total: int
    page: int
    page_size: int
    total_pages: int
