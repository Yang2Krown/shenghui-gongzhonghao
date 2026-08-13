"""add reusable draft diagnosis records.

Revision ID: 20260813_draft_diagnosis
Revises: 20260813_experience_flow
Create Date: 2026-08-13
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260813_draft_diagnosis"
down_revision: Union[str, None] = "20260813_experience_flow"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "draft_diagnoses",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("source_type", sa.String(length=20), nullable=False),
        sa.Column("source_filename", sa.String(length=500), nullable=True),
        sa.Column("content_text", sa.Text(), nullable=False),
        sa.Column("content_char_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("content_truncated", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("goal", sa.Text(), nullable=True),
        sa.Column("audience", sa.String(length=500), nullable=True),
        sa.Column("channel", sa.String(length=100), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="completed"),
        sa.Column("analysis", sa.JSON(), nullable=True),
        sa.Column("matched_experience_ids", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("matched_experiences", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("analysis_error", sa.Text(), nullable=True),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_draft_diagnoses_created_by",
        "draft_diagnoses",
        ["created_by"],
    )
    op.create_index(
        "ix_draft_diagnoses_status",
        "draft_diagnoses",
        ["status"],
    )
    op.create_index(
        "ix_draft_diagnoses_created_by_created_at",
        "draft_diagnoses",
        ["created_by", "created_at"],
    )
    op.create_index(
        "ix_draft_diagnoses_status_created_at",
        "draft_diagnoses",
        ["status", "created_at"],
    )
    op.alter_column("draft_diagnoses", "content_char_count", server_default=None)
    op.alter_column("draft_diagnoses", "content_truncated", server_default=None)
    op.alter_column("draft_diagnoses", "status", server_default=None)
    op.alter_column("draft_diagnoses", "matched_experience_ids", server_default=None)
    op.alter_column("draft_diagnoses", "matched_experiences", server_default=None)


def downgrade() -> None:
    op.drop_index("ix_draft_diagnoses_status_created_at", table_name="draft_diagnoses")
    op.drop_index("ix_draft_diagnoses_created_by_created_at", table_name="draft_diagnoses")
    op.drop_index("ix_draft_diagnoses_status", table_name="draft_diagnoses")
    op.drop_index("ix_draft_diagnoses_created_by", table_name="draft_diagnoses")
    op.drop_table("draft_diagnoses")
