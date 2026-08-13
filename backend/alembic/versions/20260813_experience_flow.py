"""add experience review status and source metadata.

Revision ID: 20260813_experience_flow
Revises: 20260812_review_stages
Create Date: 2026-08-13
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260813_experience_flow"
down_revision: Union[str, None] = "20260812_review_stages"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "experience_cards",
        sa.Column("status", sa.String(length=20), server_default="confirmed", nullable=False),
    )
    op.add_column("experience_cards", sa.Column("source_meta", sa.JSON(), nullable=True))
    op.create_index("ix_experience_cards_status", "experience_cards", ["status"])
    op.create_index(
        "ix_experience_cards_status_created_at",
        "experience_cards",
        ["status", "created_at"],
    )
    op.alter_column("experience_cards", "status", server_default=None)


def downgrade() -> None:
    op.drop_index("ix_experience_cards_status_created_at", table_name="experience_cards")
    op.drop_index("ix_experience_cards_status", table_name="experience_cards")
    op.drop_column("experience_cards", "source_meta")
    op.drop_column("experience_cards", "status")
