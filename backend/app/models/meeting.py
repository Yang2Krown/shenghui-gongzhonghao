"""会议纪要、方法论沉淀与兼容行动项模型（Phase 1b）。"""

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import relationship

from app.db.base import BaseModel, JSONField


class Meeting(BaseModel):
    """一次内部会议及其异步提取状态。"""

    __tablename__ = "meetings"
    __table_args__ = (
        Index("ix_meetings_status_meeting_at", "status", "meeting_at"),
        Index("ix_meetings_created_by_meeting_at", "created_by", "meeting_at"),
    )

    title = Column(String(200), nullable=False)
    meeting_at = Column(DateTime, nullable=False, index=True)
    raw_text = Column(Text, nullable=False)
    source_kind = Column(
        String(20),
        nullable=False,
        default="pasted_text",
        comment="pasted_text / file / feishu_notes（后续预留）",
    )
    status = Column(
        String(20),
        nullable=False,
        default="extracting",
        index=True,
        comment="extracting / ready / failed",
    )
    created_by = Column(ForeignKey("users.id"), nullable=False, index=True)

    # 任务与进度 ID 是幂等保护所需的运行态投影，不改变会议业务状态含义。
    extract_task_id = Column(String(100), nullable=True)
    extract_run_id = Column(String(100), nullable=True)

    creator = relationship(
        "User",
        foreign_keys=[created_by],
        back_populates="meetings_created",
    )
    suggestions = relationship(
        "MeetingSuggestion",
        back_populates="meeting",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="MeetingSuggestion.id",
    )
    synthesis = relationship(
        "MeetingSynthesis",
        back_populates="meeting",
        uselist=False,
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    methodology_sources = relationship(
        "MeetingMethodologySource",
        back_populates="meeting",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class MeetingSynthesis(BaseModel):
    """一次会议的结构化方法论沉淀，而不是任务 KPI。"""

    __tablename__ = "meeting_syntheses"
    __table_args__ = (
        Index("ix_meeting_syntheses_parse_status", "parse_status"),
        Index("ix_meeting_syntheses_updated_at", "updated_at"),
    )

    meeting_id = Column(
        ForeignKey("meetings.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    summary = Column(Text, nullable=True)
    methodology = Column(JSONField, nullable=False, default=list)
    checklist = Column(JSONField, nullable=False, default=list)
    decisions = Column(JSONField, nullable=False, default=list)
    disagreements = Column(JSONField, nullable=False, default=list)
    open_questions = Column(JSONField, nullable=False, default=list)
    follow_ups = Column(JSONField, nullable=False, default=list)
    raw_json = Column(JSONField, nullable=True)
    parse_status = Column(
        String(20),
        nullable=False,
        default="parsed",
        comment="parsed / repaired",
    )
    is_manually_edited = Column(Boolean, nullable=False, default=False)

    meeting = relationship("Meeting", back_populates="synthesis")


class MeetingSuggestion(BaseModel):
    """从会议纪要提取出的可执行建议。"""

    __tablename__ = "meeting_suggestions"
    __table_args__ = (
        Index("ix_meeting_suggestions_meeting_status", "meeting_id", "status"),
        Index("ix_meeting_suggestions_owner_status", "owner_id", "status"),
        Index("ix_meeting_suggestions_category", "category"),
        Index("ix_meeting_suggestions_creation", "related_creation_id"),
    )

    meeting_id = Column(
        ForeignKey("meetings.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    content = Column(Text, nullable=False)
    proposer = Column(String(50), nullable=True)
    category = Column(String(50), nullable=False, default="其他")
    priority = Column(String(20), nullable=False, default="P1", index=True)
    acceptance_criteria = Column(Text, nullable=True)
    status = Column(
        String(20),
        nullable=False,
        default="proposed",
        index=True,
    )
    owner_id = Column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    resolution_note = Column(Text, nullable=True)
    related_creation_id = Column(
        ForeignKey("content_creations.id", ondelete="SET NULL"),
        nullable=True,
    )
    # Phase 1c 尚未实现。保留字段，但不建立不存在的外键。
    related_version_id = Column(Integer, nullable=True, index=True)
    closed_at = Column(DateTime, nullable=True)
    raw_json = Column(JSONField, nullable=True)
    is_manually_edited = Column(Boolean, nullable=False, default=False)

    meeting = relationship("Meeting", back_populates="suggestions")
    owner = relationship(
        "User",
        foreign_keys=[owner_id],
        back_populates="meeting_suggestions_owned",
    )
    creation = relationship(
        "ContentCreation",
        foreign_keys=[related_creation_id],
        back_populates="meeting_suggestions",
    )
