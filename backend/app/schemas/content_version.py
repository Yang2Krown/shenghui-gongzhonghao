"""文章版本和经验库接口 schema。"""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, validator


VERSION_TYPES = {
    "before_meeting",
    "after_meeting",
    "before_review",
    "final",
    "manual",
}
EXPERIENCE_SOURCE_TYPES = {
    "meeting_methodology",
    "meeting_diff",
    "review_feedback",
    "uploaded",
    "manual",
}
EXPERIENCE_STATUSES = {"pending", "confirmed", "rejected", "merged"}


class ContentVersionCreate(BaseModel):
    version_type: str = Field("manual", max_length=20)
    note: Optional[str] = Field(None, max_length=5000)
    suggestion_id: Optional[int] = Field(None, ge=1)
    save_as_experience: bool = False
    experience_title: Optional[str] = Field(None, max_length=200)
    experience_category: Optional[str] = Field(None, max_length=50)

    @validator("version_type")
    def validate_version_type(cls, value: str) -> str:
        value = value.strip().lower()
        if value not in VERSION_TYPES:
            raise ValueError("版本类型不合法")
        return value

    @validator("note", "experience_title", "experience_category")
    def strip_optional_text(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        value = value.strip()
        return value or None


class ExperienceCardCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    content: str = Field(..., min_length=1, max_length=50000)
    category: Optional[str] = Field(None, max_length=50)
    source_type: str = Field("manual", max_length=20)
    creation_id: Optional[int] = Field(None, ge=1)
    version_pair: Optional[Dict[str, Any]] = None
    source_meta: Optional[Dict[str, Any]] = None
    suggestion_id: Optional[int] = Field(None, ge=1)

    @validator("title", "content", "category")
    def strip_text(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        value = value.strip()
        return value or None

    @validator("source_type")
    def validate_source_type(cls, value: str) -> str:
        value = value.strip().lower()
        if value not in EXPERIENCE_SOURCE_TYPES:
            raise ValueError("经验来源类型不合法")
        return value


class ExperienceCardDraftCreate(BaseModel):
    """待确认经验只允许由受控的上传/会议入口创建。"""

    title: str = Field(..., min_length=1, max_length=200)
    content: str = Field(..., min_length=1, max_length=50000)
    category: Optional[str] = Field(None, max_length=50)
    source_type: str = Field(..., max_length=20)
    source_meta: Optional[Dict[str, Any]] = None

    @validator("title", "content", "category")
    def strip_text(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        value = value.strip()
        return value or None

    @validator("source_type")
    def validate_draft_source_type(cls, value: str) -> str:
        value = value.strip().lower()
        if value not in {"meeting_methodology", "review_feedback", "uploaded", "manual"}:
            raise ValueError("待确认经验来源类型不合法")
        return value


class ExperienceCardUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=200)
    content: Optional[str] = Field(None, min_length=1, max_length=50000)
    category: Optional[str] = Field(None, max_length=50)

    @validator("title", "content", "category")
    def strip_update_text(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        value = value.strip()
        return value or None


class ExperienceCardListResponse(BaseModel):
    items: List[dict]
    total: int
    page: int
    page_size: int
    total_pages: int
    search_mode: str
    embedding_available: bool


class ExperienceMergePreviewRequest(BaseModel):
    """请求 LLM 生成多条经验的智能合并草稿。"""

    source_ids: List[int] = Field(..., min_length=2, max_length=10)

    @validator("source_ids")
    def dedupe_source_ids(cls, value: List[int]) -> List[int]:
        return list(dict.fromkeys(int(item) for item in value))


class ExperienceMergeConfirmRequest(BaseModel):
    """确认合并：保留一条正式经验，其余标记为已合并。"""

    source_ids: List[int] = Field(..., min_length=2, max_length=10)
    surviving_id: Optional[int] = Field(None, ge=1)
    title: str = Field(..., min_length=1, max_length=200)
    content: str = Field(..., min_length=1, max_length=50000)
    category: Optional[str] = Field(None, max_length=50)

    @validator("source_ids")
    def dedupe_source_ids(cls, value: List[int]) -> List[int]:
        return list(dict.fromkeys(int(item) for item in value))

    @validator("title", "content", "category")
    def strip_text(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        value = value.strip()
        return value or None
