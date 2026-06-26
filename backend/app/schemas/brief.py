"""商单 brief 相关 schema。"""

from typing import List, Optional
from pydantic import BaseModel, Field


class StructuredBrief(BaseModel):
    """结构化商单 brief。product/brief/banned/tone 可直接喂 practical 流程。"""
    product: str = Field("", description="被推广的产品/工具名")
    brief: str = Field("", description="提炼后的写作要求正文")
    core_message: Optional[str] = Field(None, description="核心主张/slogan")
    must_cover: List[str] = Field(default_factory=list, description="必须覆盖的要点")
    tone: Optional[str] = Field(None, description="调性要求")
    banned: List[str] = Field(default_factory=list, description="红线/禁忌")
    cta: Optional[str] = Field(None, description="引导动作")
    audience: Optional[str] = Field(None, description="目标读者")
    publish: Optional[str] = Field(None, description="发布档期")
    review_notes: Optional[str] = Field(None, description="审核/交付要求")
    notes: Optional[str] = Field(None, description="其他约束")


# ── 飞书授权 ──────────────────────────────────────────────

class FeishuAuthStartResponse(BaseModel):
    verification_url: str = Field(..., description="让用户打开完成授权的链接")
    expires_in: Optional[int] = Field(None, description="链接有效期(秒)")
    status: str = "pending"


class FeishuAuthStatusResponse(BaseModel):
    status: str = Field(..., description="none | pending | valid | expired")
    feishu_user_name: Optional[str] = None
    feishu_open_id: Optional[str] = None
    last_error: Optional[str] = None
    authorized_at: Optional[str] = None


# ── 读取 / 总结 ───────────────────────────────────────────

class BriefReadRequest(BaseModel):
    source_type: str = Field(..., description="feishu_link | text")
    value: str = Field(..., min_length=1, description="飞书文档链接 或 粘贴的文本")


class BriefReadResponse(BaseModel):
    title: str = ""
    raw_text: str = ""


class BriefSummarizeRequest(BaseModel):
    raw_text: str = Field(..., min_length=1, description="brief 原文")
    title: str = Field("", description="文档标题(选填)")
