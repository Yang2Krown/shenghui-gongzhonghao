"""团队协作文章复盘模型。

文章复盘和 ContentVersion 是两条不同的产品链路：前者比较两份上传稿件，
后者保存某篇创作的显式快照。复盘完成后再把确认过的方法论沉淀为 ExperienceCard。
"""

from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint
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
    runs = relationship(
        "ArticleReviewRun",
        back_populates="review",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="ArticleReviewRun.run_no",
    )
    semantic_blocks = relationship(
        "ArticleReviewSemanticBlock",
        back_populates="review",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="ArticleReviewSemanticBlock.side, ArticleReviewSemanticBlock.ordinal",
    )
    changes = relationship(
        "ArticleReviewChange",
        back_populates="review",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="ArticleReviewChange.ordinal",
    )
    reorder_events = relationship(
        "ArticleReviewReorderEvent",
        back_populates="review",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="ArticleReviewReorderEvent.ordinal",
    )
    methodology_candidates = relationship(
        "ArticleReviewMethodologyCandidate",
        back_populates="review",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="ArticleReviewMethodologyCandidate.created_at",
    )
    experience_sources = relationship(
        "ArticleReviewExperienceSource",
        back_populates="review",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="ArticleReviewExperienceSource.created_at",
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
    change_id = Column(
        ForeignKey("article_review_changes.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    semantic_block_id = Column(
        ForeignKey("article_review_semantic_blocks.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    body = Column(Text, nullable=False)
    author_id = Column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    resolved = Column(Boolean, nullable=False, default=False)
    edit_status = Column(String(20), nullable=False, default="active")
    processing_status = Column(String(20), nullable=False, default="open")
    edited_at = Column(DateTime, nullable=True)

    review = relationship("ArticleReview", back_populates="comments")
    author = relationship("User", foreign_keys=[author_id])
    change = relationship(
        "ArticleReviewChange",
        foreign_keys=[change_id],
        overlaps="comments",
    )
    semantic_block = relationship(
        "ArticleReviewSemanticBlock",
        foreign_keys=[semantic_block_id],
    )


class ArticleReviewRun(BaseModel):
    """一次可恢复的文章复盘运行。"""

    __tablename__ = "article_review_runs"
    __table_args__ = (
        UniqueConstraint("review_id", "run_no", name="uq_article_review_runs_review_no"),
        Index("ix_article_review_runs_review_created_at", "review_id", "created_at"),
        Index("ix_article_review_runs_run_id", "run_id"),
    )

    review_id = Column(
        ForeignKey("article_reviews.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    run_id = Column(String(100), nullable=False, unique=True)
    run_no = Column(Integer, nullable=False, default=1)
    status = Column(String(20), nullable=False, default="queued")
    current_stage = Column(String(40), nullable=True)
    requested_stage = Column(String(40), nullable=True)
    task_id = Column(String(100), nullable=True)
    error = Column(Text, nullable=True)
    started_at = Column(DateTime, nullable=True)
    finished_at = Column(DateTime, nullable=True)
    created_by = Column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)

    review = relationship("ArticleReview", back_populates="runs")
    stages = relationship(
        "ArticleReviewStage",
        back_populates="run",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="ArticleReviewStage.stage_order",
    )
    creator = relationship("User", foreign_keys=[created_by])


class ArticleReviewStage(BaseModel):
    """运行中的单个阶段，支持阶段级重试和幂等收口。"""

    __tablename__ = "article_review_stages"
    __table_args__ = (
        UniqueConstraint("review_run_id", "stage_key", name="uq_article_review_stages_run_stage"),
        Index("ix_article_review_stages_status", "status"),
    )

    review_run_id = Column(
        ForeignKey("article_review_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    stage_key = Column(String(40), nullable=False)
    stage_order = Column(Integer, nullable=False, default=1)
    status = Column(String(30), nullable=False, default="queued")
    progress = Column(Integer, nullable=False, default=0)
    message = Column(String(500), nullable=True)
    task_id = Column(String(100), nullable=True)
    attempt = Column(Integer, nullable=False, default=0)
    input_hash = Column(String(128), nullable=True)
    output = Column(JSONField, nullable=True)
    error = Column(Text, nullable=True)
    started_at = Column(DateTime, nullable=True)
    finished_at = Column(DateTime, nullable=True)

    run = relationship("ArticleReviewRun", back_populates="stages")


class ArticleReviewSemanticBlock(BaseModel):
    """改前/改后文本中的稳定语义块。"""

    __tablename__ = "article_review_semantic_blocks"
    __table_args__ = (
        UniqueConstraint("review_run_id", "stable_id", name="uq_article_review_blocks_run_stable"),
        Index("ix_article_review_blocks_review_side_ordinal", "review_id", "side", "ordinal"),
    )

    review_id = Column(
        ForeignKey("article_reviews.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    review_run_id = Column(
        ForeignKey("article_review_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    stable_id = Column(String(120), nullable=False)
    side = Column(String(10), nullable=False, comment="before / after")
    ordinal = Column(Integer, nullable=False)
    text = Column(Text, nullable=False)
    normalized_text = Column(Text, nullable=False)
    start_offset = Column(Integer, nullable=False, default=0)
    end_offset = Column(Integer, nullable=False, default=0)
    source_line_start = Column(Integer, nullable=True)
    source_line_end = Column(Integer, nullable=True)
    raw_block_count = Column(Integer, nullable=False, default=1)
    user_edited = Column(Boolean, nullable=False, default=False)
    locked = Column(Boolean, nullable=False, default=False)
    block_metadata = Column("metadata", JSONField, nullable=True)

    review = relationship("ArticleReview", back_populates="semantic_blocks")
    run = relationship("ArticleReviewRun")


class ArticleReviewChange(BaseModel):
    """语义块对齐后的变化；旧 change_groups JSON 由它兼容投影而来。"""

    __tablename__ = "article_review_changes"
    __table_args__ = (
        UniqueConstraint("review_run_id", "stable_id", name="uq_article_review_changes_run_stable"),
        Index("ix_article_review_changes_review_ordinal", "review_id", "ordinal"),
        Index("ix_article_review_changes_type_impact", "change_type", "impact"),
    )

    review_id = Column(
        ForeignKey("article_reviews.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    review_run_id = Column(
        ForeignKey("article_review_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    stable_id = Column(String(120), nullable=False)
    ordinal = Column(Integer, nullable=False)
    change_type = Column(
        String(30),
        nullable=False,
        comment="unchanged / minor_edit / rewrite / structural_change / addition / deletion / reorder / uncertain",
    )
    impact = Column(String(20), nullable=False, default="low")
    is_major = Column(Boolean, nullable=False, default=False)
    confidence = Column(Float, nullable=False, default=0.0)
    change_ratio = Column(Float, nullable=False, default=0.0)
    significance_reason = Column(Text, nullable=True)
    effect = Column(Text, nullable=True)
    before_block_ids = Column(JSONField, nullable=False, default=list)
    after_block_ids = Column(JSONField, nullable=False, default=list)
    before_text = Column(Text, nullable=True)
    after_text = Column(Text, nullable=True)
    position_delta = Column(Integer, nullable=True)
    human_label = Column(String(30), nullable=True, comment="important / unimportant / false_positive / needs_review")
    human_note = Column(Text, nullable=True)
    ai_analysis = Column(JSONField, nullable=True)

    review = relationship("ArticleReview", back_populates="changes")
    run = relationship("ArticleReviewRun")
    comments = relationship(
        "ArticleReviewComment",
        foreign_keys="ArticleReviewComment.change_id",
        overlaps="change",
    )


class ArticleReviewReorderEvent(BaseModel):
    """内容基本不变但顺序变化的独立事件。"""

    __tablename__ = "article_review_reorder_events"
    __table_args__ = (
        UniqueConstraint("review_run_id", "stable_id", name="uq_article_review_reorder_run_stable"),
        Index("ix_article_review_reorder_review_ordinal", "review_id", "ordinal"),
    )

    review_id = Column(ForeignKey("article_reviews.id", ondelete="CASCADE"), nullable=False, index=True)
    review_run_id = Column(ForeignKey("article_review_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    stable_id = Column(String(120), nullable=False)
    ordinal = Column(Integer, nullable=False)
    before_block_ids = Column(JSONField, nullable=False, default=list)
    after_block_ids = Column(JSONField, nullable=False, default=list)
    summary = Column(Text, nullable=True)
    confidence = Column(Float, nullable=False, default=0.0)
    human_label = Column(String(30), nullable=True)

    review = relationship("ArticleReview", back_populates="reorder_events")
    run = relationship("ArticleReviewRun")


class ArticleReviewMethodologyCandidate(BaseModel):
    """AI 生成、等待人工确认的方法论候选。"""

    __tablename__ = "article_review_methodology_candidates"
    __table_args__ = (
        Index("ix_article_review_methodology_review_status", "review_id", "status"),
    )

    review_id = Column(ForeignKey("article_reviews.id", ondelete="CASCADE"), nullable=False, index=True)
    review_run_id = Column(ForeignKey("article_review_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    title = Column(String(200), nullable=False)
    rule = Column(Text, nullable=False)
    rationale = Column(Text, nullable=True)
    example = Column(Text, nullable=True)
    evidence_change_ids = Column(JSONField, nullable=False, default=list)
    status = Column(String(20), nullable=False, default="candidate", comment="candidate / confirmed / rejected / promoted")
    confirmed_by = Column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    confirmed_at = Column(DateTime, nullable=True)
    experience_card_id = Column(ForeignKey("experience_cards.id", ondelete="SET NULL"), nullable=True, index=True)

    review = relationship("ArticleReview", back_populates="methodology_candidates")
    run = relationship("ArticleReviewRun")
    confirmer = relationship("User", foreign_keys=[confirmed_by])


class ArticleReviewExperienceSource(BaseModel):
    """经验卡片的复盘来源和人工确认证据。"""

    __tablename__ = "article_review_experience_sources"
    __table_args__ = (
        Index("ix_article_review_experience_sources_card", "experience_card_id"),
        Index("ix_article_review_experience_sources_review", "review_id"),
    )

    experience_card_id = Column(ForeignKey("experience_cards.id", ondelete="CASCADE"), nullable=False, index=True)
    review_id = Column(ForeignKey("article_reviews.id", ondelete="CASCADE"), nullable=False, index=True)
    review_run_id = Column(ForeignKey("article_review_runs.id", ondelete="SET NULL"), nullable=True, index=True)
    change_id = Column(ForeignKey("article_review_changes.id", ondelete="SET NULL"), nullable=True, index=True)
    comment_ids = Column(JSONField, nullable=False, default=list)
    confirmed_conclusion = Column(Text, nullable=True)
    confirmed_by = Column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    confirmed_at = Column(DateTime, nullable=True)

    review = relationship("ArticleReview", back_populates="experience_sources")
    run = relationship("ArticleReviewRun")
    change = relationship("ArticleReviewChange")
    confirmer = relationship("User", foreign_keys=[confirmed_by])
