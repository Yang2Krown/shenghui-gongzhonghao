"""团队协作模块 schema（P0：角色赋予 / 成员 / 文章共享）。"""
from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, Field, validator


# ── 成员 ──────────────────────────────────────────────────

class RoleUpdateRequest(BaseModel):
    role: str = Field(..., description="目标角色：employee / user")

    @validator("role")
    def validate_role(cls, v: str) -> str:
        role = v.strip().lower()
        if role not in {"employee", "user"}:
            raise ValueError("仅支持 employee / user 角色")
        return role


class TeamMemberUpdateRequest(BaseModel):
    department: Optional[str] = Field(None, max_length=50)
    position: Optional[str] = Field(None, max_length=50)
    employee_no: Optional[str] = Field(None, max_length=32)
    joined_at: Optional[date] = None
    status: Optional[str] = Field(None, description="active / left")


class TeamMemberOut(BaseModel):
    user_id: int
    username: str
    phone_masked: Optional[str] = None
    full_name: Optional[str] = None
    avatar_url: Optional[str] = None
    role: str
    is_superuser: bool = False
    is_active: bool = True
    department: Optional[str] = None
    position: Optional[str] = None
    employee_no: Optional[str] = None
    joined_at: Optional[date] = None
    employee_status: Optional[str] = None
    created_at: Optional[datetime] = None


# ── 文章共享 ──────────────────────────────────────────────

class ShareCreationRequest(BaseModel):
    user_id: int = Field(..., description="被共享成员 user_id")
    role: str = Field("viewer", description="editor / viewer")

    @validator("role")
    def validate_role(cls, v: str) -> str:
        role = v.strip().lower()
        if role not in {"editor", "viewer"}:
            raise ValueError("共享角色仅支持 editor / viewer")
        return role


class CreationMemberOut(BaseModel):
    user_id: int
    username: str
    full_name: Optional[str] = None
    avatar_url: Optional[str] = None
    role: str
    granted_by: Optional[int] = None
    created_at: Optional[datetime] = None
