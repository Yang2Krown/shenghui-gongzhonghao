"""文章共享模型（P0 团队协作底座）。"""
from sqlalchemy import Column, Integer, String, ForeignKey, UniqueConstraint

from app.db.base import BaseModel


class ArticleMember(BaseModel):
    """文章成员：把创作共享给团队成员，支撑后续评论/版本跨人访问。"""

    __tablename__ = "article_members"
    __table_args__ = (
        UniqueConstraint("creation_id", "user_id", name="uq_article_members_creation_user"),
    )

    creation_id = Column(Integer, ForeignKey("content_creations.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    role = Column(String(20), default="viewer", nullable=False, comment="owner / editor / viewer")
    granted_by = Column(Integer, ForeignKey("users.id"), nullable=True, comment="授权人 user_id")

    def __repr__(self) -> str:
        return f"<ArticleMember(creation_id={self.creation_id}, user_id={self.user_id}, role='{self.role}')>"
