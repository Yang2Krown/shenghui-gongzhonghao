"""创作外部发布记录。

创作本身的 status 表示本地内容生命周期，外部平台的上传/发布结果单独落表，
这样“已进入公众号草稿箱”和“已正式发布”不会再被混成一个状态。
"""

from sqlalchemy import Column, DateTime, ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.orm import relationship

from app.db.base import BaseModel


class CreationPublication(BaseModel):
    """一次创作在某个平台上的发布/上传状态。"""

    __tablename__ = "creation_publications"
    __table_args__ = (
        UniqueConstraint(
            "creation_id",
            "platform",
            "operation",
            "request_key",
            name="uq_creation_publications_idempotency_key",
        ),
        Index("ix_creation_publications_creation_id", "creation_id"),
        Index("ix_creation_publications_status", "status"),
    )

    creation_id = Column(
        ForeignKey("content_creations.id", ondelete="CASCADE"),
        nullable=False,
    )
    initiated_by = Column(ForeignKey("users.id"), nullable=False)
    platform = Column(String(50), nullable=False, comment="wechat_draft / wechat / other")
    operation = Column(String(30), nullable=False, comment="draft_upload / publish")
    status = Column(String(20), nullable=False, default="pending", comment="pending/succeeded/failed")
    external_id = Column(String(200), nullable=True)
    external_url = Column(String(1000), nullable=True)
    request_key = Column(String(100), nullable=True)
    error_message = Column(Text, nullable=True)
    started_at = Column(DateTime, nullable=True)
    finished_at = Column(DateTime, nullable=True)

    creation = relationship("ContentCreation", foreign_keys=[creation_id])

    def __repr__(self) -> str:
        return (
            f"<CreationPublication(creation_id={self.creation_id}, platform='{self.platform}', "
            f"operation='{self.operation}', status='{self.status}')>"
        )
