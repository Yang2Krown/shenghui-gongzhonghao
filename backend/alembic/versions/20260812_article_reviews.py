"""add team article review workspace.

Revision ID: 20260812_article_reviews
Revises: 20260811_phase1c
Create Date: 2026-08-12
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260812_article_reviews"
down_revision: Union[str, None] = "20260811_phase1c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "article_reviews",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("before_filename", sa.String(length=500), nullable=False),
        sa.Column("after_filename", sa.String(length=500), nullable=False),
        sa.Column("before_text", sa.Text(), nullable=False),
        sa.Column("after_text", sa.Text(), nullable=False),
        sa.Column("before_char_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("after_char_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("before_truncated", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("after_truncated", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("change_groups", sa.JSON(), nullable=False),
        sa.Column("ai_analysis", sa.JSON(), nullable=True),
        sa.Column(
            "status",
            sa.String(length=20),
            server_default="analyzing",
            nullable=False,
        ),
        sa.Column("analysis_task_id", sa.String(length=100), nullable=True),
        sa.Column("analysis_error", sa.Text(), nullable=True),
        sa.Column("promoted_card_ids", sa.JSON(), nullable=False),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["users.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_article_reviews_created_by",
        "article_reviews",
        ["created_by"],
    )
    op.create_index(
        "ix_article_reviews_status_created_at",
        "article_reviews",
        ["status", "created_at"],
    )
    op.create_index(
        "ix_article_reviews_created_by_created_at",
        "article_reviews",
        ["created_by", "created_at"],
    )

    op.create_table(
        "article_review_comments",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("review_id", sa.Integer(), nullable=False),
        sa.Column("change_group_id", sa.String(length=80), nullable=True),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("author_id", sa.Integer(), nullable=True),
        sa.Column("resolved", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(
            ["review_id"],
            ["article_reviews.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["author_id"],
            ["users.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_article_review_comments_review_id",
        "article_review_comments",
        ["review_id"],
    )
    op.create_index(
        "ix_article_review_comments_author_id",
        "article_review_comments",
        ["author_id"],
    )
    op.create_index(
        "ix_article_review_comments_review_created_at",
        "article_review_comments",
        ["review_id", "created_at"],
    )
    op.create_index(
        "ix_article_review_comments_group",
        "article_review_comments",
        ["review_id", "change_group_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_article_review_comments_group", table_name="article_review_comments")
    op.drop_index(
        "ix_article_review_comments_review_created_at",
        table_name="article_review_comments",
    )
    op.drop_index("ix_article_review_comments_author_id", table_name="article_review_comments")
    op.drop_index("ix_article_review_comments_review_id", table_name="article_review_comments")
    op.drop_table("article_review_comments")
    op.drop_index("ix_article_reviews_created_by_created_at", table_name="article_reviews")
    op.drop_index("ix_article_reviews_status_created_at", table_name="article_reviews")
    op.drop_index("ix_article_reviews_created_by", table_name="article_reviews")
    op.drop_table("article_reviews")
