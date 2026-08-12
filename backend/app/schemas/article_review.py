"""文章复盘接口 schema。"""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, validator


class ArticleReviewCommentCreate(BaseModel):
    change_group_id: Optional[str] = Field(None, max_length=80)
    body: str = Field(..., min_length=1, max_length=5_000)

    @validator("change_group_id", "body")
    def strip_text(cls, value: Optional[str]) -> Optional[str]:
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
