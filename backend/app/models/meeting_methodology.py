"""跨会议方法论语义归并的持久化投影。"""

from sqlalchemy import (
    Boolean,
    Column,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from app.db.base import BaseModel, JSONField


class MeetingMethodologyCluster(BaseModel):
    """同一条可复用方法论的主记录；会议原文仍保存在各自 synthesis 中。"""

    __tablename__ = "meeting_methodology_clusters"
    __table_args__ = (
        Index(
            "ix_meeting_methodology_clusters_scope",
            "section",
            "category",
            "status",
        ),
        Index(
            "ix_meeting_methodology_clusters_fingerprint",
            "section",
            "category",
            "canonical_fingerprint",
        ),
    )

    section = Column(
        String(20),
        nullable=False,
        comment="methodology / checklist，两个语义空间不直接合并",
    )
    category = Column(String(50), nullable=False, index=True)
    title = Column(String(200), nullable=False)
    rule = Column(Text, nullable=False)
    rationale = Column(Text, nullable=True)
    example = Column(Text, nullable=True)
    evidence = Column(Text, nullable=True)
    normalized_text = Column(Text, nullable=False)
    canonical_fingerprint = Column(String(64), nullable=False)
    # 当前规模较小，复用现有 embedding 服务后以 JSON 保存向量，
    # 相似度在应用层计算，不新增向量库或新的中间件。
    embedding = Column(JSONField, nullable=True)
    source_count = Column(Integer, nullable=False, default=0)
    status = Column(String(20), nullable=False, default="active", index=True)
    is_manually_edited = Column(Boolean, nullable=False, default=False)

    sources = relationship(
        "MeetingMethodologySource",
        back_populates="cluster",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="MeetingMethodologySource.id",
    )


class MeetingMethodologySource(BaseModel):
    """主方法论簇对应的单次会议来源，保留原始条目和归并依据。"""

    __tablename__ = "meeting_methodology_sources"
    __table_args__ = (
        UniqueConstraint(
            "meeting_id",
            "section",
            "source_fingerprint",
            name="uq_meeting_methodology_source_item",
        ),
        Index(
            "ix_meeting_methodology_sources_cluster",
            "cluster_id",
            "meeting_id",
        ),
        Index(
            "ix_meeting_methodology_sources_meeting",
            "meeting_id",
            "section",
        ),
    )

    cluster_id = Column(
        ForeignKey("meeting_methodology_clusters.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    meeting_id = Column(
        ForeignKey("meetings.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    section = Column(String(20), nullable=False)
    source_fingerprint = Column(String(64), nullable=False)
    item = Column(JSONField, nullable=False, default=dict)
    similarity = Column(Float, nullable=True)
    match_kind = Column(
        String(30),
        nullable=False,
        default="new",
        comment="new / exact / embedding / llm / lexical",
    )
    is_primary = Column(Boolean, nullable=False, default=False)

    cluster = relationship(
        "MeetingMethodologyCluster",
        back_populates="sources",
    )
    meeting = relationship(
        "Meeting",
        back_populates="methodology_sources",
    )
