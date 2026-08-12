"""团队协作文章复盘模型。

文章复盘和 ContentVersion 是两条不同的产品链路：前者比较两份上传稿件，
后者保存某篇创作的显式快照。复盘完成后再把确认过的方法论沉淀为 ExperienceCard。
"""

from sqlalchemy import Boolean, Column, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import relationship

from app.db.base import BaseModel, JSONField


class ArticleReview(BaseModel):
    """改前/改后文章的团队复盘记录。"""

    __tablename__ = "article_reviews"
    __table_args__ = (
        Index("ix_article_reviews_status_created_at", "status", "created_at"),
        Index("ix_article_reviews_created_by_created_at", "created_by", "created_at"),
    )

    title = Column(String(200), nullable=False)
    before_filename = Column(String(500), nullable=False)
    after_filename = Column(String(500), nullable=False)
    # 原始文件只在后台解析期间暂存于共享 uploads volume；解析完成后清理。
    before_file_path = Column(String(1000), nullable=True)
    after_file_path = Column(String(1000), nullable=True)
    before_text = Column(Text, nullable=False)
    after_text = Column(Text, nullable=False)
    before_char_count = Column(Integer, nullable=False, default=0)
    after_char_count = Column(Integer, nullable=False, default=0)
    before_truncated = Column(Boolean, nullable=False, default=False)
    after_truncated = Column(Boolean, nullable=False, default=False)
    # 只保存有变化的块；每个块有稳定的 change_group_id，评论和经验卡片都引用它。
    change_groups = Column(JSONField, nullable=False, default=list)
    ai_analysis = Column(JSONField, nullable=True)
    status = Column(
        String(20),
        nullable=False,
        default="analyzing",
        comment="processing / analyzing / reviewing / failed",
    )
    analysis_task_id = Column(String(100), nullable=True)
    progress_run_id = Column(String(100), nullable=True, index=True)
    analysis_error = Column(Text, nullable=True)
    promoted_card_ids = Column(JSONField, nullable=False, default=list)
    created_by = Column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    creator = relationship("User", foreign_keys=[created_by])
    comments = relationship(
        "ArticleReviewComment",
        back_populates="review",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="ArticleReviewComment.created_at",
    )


class ArticleReviewComment(BaseModel):
    """复盘成员针对某个改动块的人工评论。"""

    __tablename__ = "article_review_comments"
    __table_args__ = (
        Index("ix_article_review_comments_review_created_at", "review_id", "created_at"),
        Index("ix_article_review_comments_group", "review_id", "change_group_id"),
    )

    review_id = Column(
        ForeignKey("article_reviews.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    change_group_id = Column(String(80), nullable=True)
    body = Column(Text, nullable=False)
    author_id = Column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    resolved = Column(Boolean, nullable=False, default=False)

    review = relationship("ArticleReview", back_populates="comments")
    author = relationship("User", foreign_keys=[author_id])
