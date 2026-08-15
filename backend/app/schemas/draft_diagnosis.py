"""初稿诊断接口 schema。"""

from typing import Any, Optional

from pydantic import BaseModel, Field, validator


MAX_DRAFT_DIAGNOSIS_CHARS = 150_000


class DraftDiagnosisCreate(BaseModel):
    """粘贴文字的初稿诊断请求。"""

    title: Optional[str] = Field(None, max_length=200)
    content: str = Field(..., min_length=1, max_length=MAX_DRAFT_DIAGNOSIS_CHARS)
    goal: Optional[str] = Field(None, max_length=5000)
    audience: Optional[str] = Field(None, max_length=500)
    channel: Optional[str] = Field(None, max_length=100)
    brief_context: Optional[dict[str, Any]] = Field(None, description="结构化商单 brief 上下文")

    @validator("title", "content", "goal", "audience", "channel")
    def strip_text(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        value = value.strip()
        return value or None


class DraftDiagnosisTitleUpdate(BaseModel):
    """更新初稿诊断标题。"""

    title: str = Field(..., min_length=1, max_length=200)

    @validator("title")
    def strip_title(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("标题不能为空")
        return value


class DraftDiagnosisExperienceDraftCreate(BaseModel):
    """把某条诊断发现送入待确认经验，不直接进入正式经验库。"""

    finding_index: int = Field(..., ge=0, le=50)
    title: Optional[str] = Field(None, max_length=200)
    content: Optional[str] = Field(None, max_length=50_000)
    category: Optional[str] = Field(None, max_length=50)

    @validator("title", "content", "category")
    def strip_optional_text(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        value = value.strip()
        return value or None
