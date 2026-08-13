"""初稿诊断记录模型。

初稿诊断和双版本文章复盘是两条不同的工作流：前者只有一份待优化的
初稿，运行时引用已经确认的经验卡片，并把诊断结果保存下来供后续回看。
"""

from sqlalchemy import Boolean, Column, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import relationship

from app.db.base import BaseModel, JSONField


class DraftDiagnosis(BaseModel):
    """一次初稿诊断及其可追溯的经验引用。"""

    __tablename__ = "draft_diagnoses"
    __table_args__ = (
        Index("ix_draft_diagnoses_created_by_created_at", "created_by", "created_at"),
        Index("ix_draft_diagnoses_status_created_at", "status", "created_at"),
    )

    title = Column(String(200), nullable=False)
    source_type = Column(
        String(20),
        nullable=False,
        comment="file / pasted",
    )
    source_filename = Column(String(500), nullable=True)
    content_text = Column(Text, nullable=False)
    content_char_count = Column(Integer, nullable=False, default=0)
    content_truncated = Column(Boolean, nullable=False, default=False)
    goal = Column(Text, nullable=True)
    audience = Column(String(500), nullable=True)
    channel = Column(String(100), nullable=True)
    # 结构化商单 brief 快照：保留本次诊断实际使用的上下文，便于历史回看。
    brief_context = Column(JSONField, nullable=True)
    status = Column(
        String(20),
        nullable=False,
        default="completed",
        comment="processing / completed / failed",
        index=True,
    )
    analysis = Column(JSONField, nullable=True)
    matched_experience_ids = Column(JSONField, nullable=False, default=list)
    matched_experiences = Column(JSONField, nullable=False, default=list)
    analysis_error = Column(Text, nullable=True)
    created_by = Column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    creator = relationship("User", foreign_keys=[created_by])
