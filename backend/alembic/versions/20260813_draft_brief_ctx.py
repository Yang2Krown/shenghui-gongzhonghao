"""save structured brief context on draft diagnoses.

Revision ID: 20260813_draft_brief_ctx
Revises: 20260813_draft_diagnosis
Create Date: 2026-08-13
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260813_draft_brief_ctx"
down_revision: Union[str, None] = "20260813_draft_diagnosis"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "draft_diagnoses",
        sa.Column("brief_context", sa.JSON(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("draft_diagnoses", "brief_context")
