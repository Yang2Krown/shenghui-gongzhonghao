"""make article review ingestion asynchronous.

Revision ID: 20260812_review_async
Revises: 20260812_article_reviews
Create Date: 2026-08-12
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260812_review_async"
down_revision: Union[str, None] = "20260812_article_reviews"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("article_reviews", sa.Column("before_file_path", sa.String(length=1000), nullable=True))
    op.add_column("article_reviews", sa.Column("after_file_path", sa.String(length=1000), nullable=True))
    op.add_column("article_reviews", sa.Column("progress_run_id", sa.String(length=100), nullable=True))
    op.create_index("ix_article_reviews_progress_run_id", "article_reviews", ["progress_run_id"])


def downgrade() -> None:
    op.drop_index("ix_article_reviews_progress_run_id", table_name="article_reviews")
    op.drop_column("article_reviews", "progress_run_id")
    op.drop_column("article_reviews", "after_file_path")
    op.drop_column("article_reviews", "before_file_path")
