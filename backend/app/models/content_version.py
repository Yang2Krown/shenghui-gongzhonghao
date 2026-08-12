"""文章版本快照与经验卡片模型（Phase 1c）。"""

from sqlalchemy import Column, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import relationship

from app.db.base import BaseModel, JSONField


class ContentVersion(BaseModel):
    """文章的显式版本快照。

    版本只在用户明确点击“保存版本”时创建，不参与文章自动保存链路。
    ``content_json`` 保存编辑器当前实际使用的 JSON 结构，``content_text``
    是同一快照的统一纯文本投影，供 diff 和语义摘要使用。
    """

    __tablename__ = "content_versions"
    __table_args__ = (
        UniqueConstraint(
            "creation_id",
            "version_no",
            name="uq_content_versions_creation_version_no",
        ),
        Index("ix_content_versions_creation_version_no", "creation_id", "version_no"),
        Index("ix_content_versions_creation_created_at", "creation_id", "created_at"),
        Index("ix_content_versions_version_type", "version_type"),
    )

    creation_id = Column(
        ForeignKey("content_creations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    version_no = Column(Integer, nullable=False)
    version_type = Column(
        String(20),
        nullable=False,
        comment="before_meeting / after_meeting / before_review / final / manual",
    )
    title = Column(String(500), nullable=False)
    content_json = Column(JSONField, nullable=False)
    content_text = Column(Text, nullable=False)
    word_count = Column(Integer, nullable=False, default=0)
    note = Column(Text, nullable=True)
    created_by = Column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    suggestion_id = Column(
        ForeignKey("meeting_suggestions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    # 一个 after 版本可以和多个版本对比较，所以必须按 before/after key 保存，
    # 不能让新的语义摘要覆盖另一对版本的结果。
    diff_summary = Column(JSONField, nullable=True)

    creation = relationship(
        "ContentCreation",
        back_populates="versions",
        passive_deletes=True,
    )
    creator = relationship(
        "User",
        foreign_keys=[created_by],
        back_populates="content_versions_created",
    )
    suggestion = relationship(
        "MeetingSuggestion",
        foreign_keys=[suggestion_id],
        back_populates="content_versions",
    )
    related_suggestions = relationship(
        "MeetingSuggestion",
        foreign_keys="MeetingSuggestion.related_version_id",
        back_populates="related_version",
        passive_deletes=True,
    )


class ExperienceCard(BaseModel):
    """可检索的经验卡片，不承载知识图谱关系。"""

    __tablename__ = "experience_cards"
    __table_args__ = (
        Index("ix_experience_cards_source_type_created_at", "source_type", "created_at"),
        Index("ix_experience_cards_category_created_at", "category", "created_at"),
        Index("ix_experience_cards_creation", "creation_id"),
        Index("ix_experience_cards_suggestion", "suggestion_id"),
    )

    title = Column(String(200), nullable=False)
    content = Column(Text, nullable=False)
    source_type = Column(
        String(20),
        nullable=False,
        comment="meeting_diff / review_feedback / manual",
    )
    creation_id = Column(
        ForeignKey("content_creations.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    version_pair = Column(JSONField, nullable=True)
    suggestion_id = Column(
        ForeignKey("meeting_suggestions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    category = Column(String(50), nullable=True, index=True)
    # 当前项目的会议方法论语义归并使用 JSON 保存向量并在应用层计算相似度，
    # 这里沿用同一约定，仍复用 pgvector 对应的 embedding_service，不增加向量库。
    embedding = Column(JSONField, nullable=True)
    embedding_status = Column(
        String(20),
        nullable=False,
        default="pending",
        comment="pending / ready / failed",
    )
    embedding_error = Column(Text, nullable=True)
    embedding_task_id = Column(String(100), nullable=True)
    created_by = Column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    creation = relationship(
        "ContentCreation",
        back_populates="experience_cards",
        passive_deletes=True,
    )
    creator = relationship(
        "User",
        foreign_keys=[created_by],
        back_populates="experience_cards_created",
    )
    suggestion = relationship(
        "MeetingSuggestion",
        foreign_keys=[suggestion_id],
        back_populates="experience_cards",
    )
