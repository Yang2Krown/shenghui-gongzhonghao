"""phase 0.5 engineering baseline: publication records.

Revision ID: 20260808_phase05
Revises: 20260808_team_collab
Create Date: 2026-08-08

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260808_phase05"
down_revision: Union[str, None] = "20260808_team_collab"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "creation_publications",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("creation_id", sa.Integer(), nullable=False),
        sa.Column("initiated_by", sa.Integer(), nullable=False),
        sa.Column("platform", sa.String(length=50), nullable=False),
        sa.Column("operation", sa.String(length=30), nullable=False),
        sa.Column("status", sa.String(length=20), server_default="pending", nullable=False),
        sa.Column("external_id", sa.String(length=200), nullable=True),
        sa.Column("external_url", sa.String(length=1000), nullable=True),
        sa.Column("request_key", sa.String(length=100), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["creation_id"], ["content_creations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["initiated_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "creation_id",
            "platform",
            "operation",
            "request_key",
            name="uq_creation_publications_idempotency_key",
        ),
    )
    op.create_index(
        "ix_creation_publications_creation_id",
        "creation_publications",
        ["creation_id"],
    )
    op.create_index(
        "ix_creation_publications_status",
        "creation_publications",
        ["status"],
    )


def downgrade() -> None:
    op.drop_index("ix_creation_publications_status", table_name="creation_publications")
    op.drop_index("ix_creation_publications_creation_id", table_name="creation_publications")
    op.drop_table("creation_publications")
