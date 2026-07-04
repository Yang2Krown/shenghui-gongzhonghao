"""add monitoring snapshots

Revision ID: 20260704_monitoring_snapshots
Revises: 20260703_commercial_brand_cat
Create Date: 2026-07-04
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "20260704_monitoring_snapshots"
down_revision: Union[str, None] = "20260703_commercial_brand_cat"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    json_type = postgresql.JSONB(astext_type=sa.Text()) if bind.dialect.name == "postgresql" else sa.JSON()
    op.create_table(
        "monitoring_snapshots",
        sa.Column("level", sa.String(length=20), nullable=False),
        sa.Column("message", sa.String(length=200), nullable=True),
        sa.Column("generated_at", sa.DateTime(), nullable=False),
        sa.Column("raw_infos_2h", sa.Integer(), nullable=False),
        sa.Column("clusters_24h", sa.Integer(), nullable=False),
        sa.Column("pending_raw_infos", sa.Integer(), nullable=False),
        sa.Column("failed_tasks_24h", sa.Integer(), nullable=False),
        sa.Column("active_users_24h", sa.Integer(), nullable=False),
        sa.Column("low_credit_users", sa.Integer(), nullable=False),
        sa.Column("payload", json_type, nullable=False),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_monitoring_snapshots_id"), "monitoring_snapshots", ["id"], unique=False)
    op.create_index(op.f("ix_monitoring_snapshots_level"), "monitoring_snapshots", ["level"], unique=False)
    op.create_index(
        op.f("ix_monitoring_snapshots_generated_at"),
        "monitoring_snapshots",
        ["generated_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_monitoring_snapshots_generated_at"), table_name="monitoring_snapshots")
    op.drop_index(op.f("ix_monitoring_snapshots_level"), table_name="monitoring_snapshots")
    op.drop_index(op.f("ix_monitoring_snapshots_id"), table_name="monitoring_snapshots")
    op.drop_table("monitoring_snapshots")
