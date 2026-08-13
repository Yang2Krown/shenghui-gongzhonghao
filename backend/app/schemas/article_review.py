"""文章复盘接口 schema。"""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, validator


class ArticleReviewCommentCreate(BaseModel):
    change_group_id: Optional[str] = Field(None, max_length=80)
    change_id: Optional[int] = Field(None, ge=1)
    semantic_block_id: Optional[int] = Field(None, ge=1)
    body: str = Field(..., min_length=1, max_length=5_000)

    @validator("change_group_id", "body")
    def strip_text(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        value = value.strip()
        return value or None


class ArticleReviewTitleUpdate(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)

    @validator("title")
    def strip_title(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("标题不能为空")
        return value


class ArticleReviewCommentUpdate(BaseModel):
    body: Optional[str] = Field(None, min_length=1, max_length=5_000)
    resolved: Optional[bool] = None
    edit_status: Optional[str] = Field(None, pattern=r"^(active|edited|deleted)$")
    processing_status: Optional[str] = Field(None, pattern=r"^(open|in_review|accepted|rejected|closed)$")

    @validator("body")
    def strip_body(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        value = value.strip()
        return value or None


class ArticleReviewAnalysisUpdate(BaseModel):
    summary: Optional[str] = Field(None, max_length=4_000)
    key_changes: Optional[List[Dict[str, Any]]] = None
    methodology_candidates: Optional[List[Dict[str, Any]]] = None
    open_questions: Optional[List[str]] = None

    @validator("summary")
    def strip_summary(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        value = value.strip()
        return value or None


class ArticleReviewPromote(BaseModel):
    methodology_candidate_id: Optional[int] = Field(None, ge=1)
    title: Optional[str] = Field(None, max_length=200)
    content: Optional[str] = Field(None, max_length=50_000)
    category: Optional[str] = Field(None, max_length=50)
    change_group_ids: List[str] = Field(default_factory=list, max_length=30)

    @validator("title", "content", "category")
    def strip_optional_text(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        value = value.strip()
        return value or None

    @validator("change_group_ids")
    def strip_group_ids(cls, value: List[str]) -> List[str]:
        return [item.strip() for item in value if item and item.strip()]


class ArticleReviewSemanticBlockInput(BaseModel):
    side: str = Field(..., pattern=r"^(before|after)$")
    stable_id: Optional[str] = Field(None, max_length=120)
    ordinal: int = Field(..., ge=1, le=10_000)
    text: str = Field(..., min_length=1, max_length=50_000)
    start_offset: int = Field(0, ge=0)
    end_offset: int = Field(0, ge=0)
    user_edited: bool = True

    @validator("stable_id", "text")
    def strip_block_text(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        value = value.strip()
        return value or None


class ArticleReviewSemanticBlocksUpdate(BaseModel):
    blocks: List[ArticleReviewSemanticBlockInput] = Field(..., min_length=1, max_length=10_000)
    lock: bool = True


class ArticleReviewChangeReviewUpdate(BaseModel):
    human_label: str = Field(..., pattern=r"^(important|unimportant|false_positive|needs_review)$")
    human_note: Optional[str] = Field(None, max_length=5_000)

    @validator("human_note")
    def strip_human_note(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        value = value.strip()
        return value or None


class ArticleReviewMethodologyConfirm(BaseModel):
    status: str = Field(..., pattern=r"^(confirmed|rejected)$")
    conclusion: Optional[str] = Field(None, max_length=10_000)

    @validator("conclusion")
    def strip_conclusion(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        value = value.strip()
        return value or None
