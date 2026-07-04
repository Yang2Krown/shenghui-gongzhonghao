"""add monitoring alerts

Revision ID: 20260704_monitoring_alerts
Revises: 20260704_monitoring_snapshots
Create Date: 2026-07-04
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "20260704_monitoring_alerts"
down_revision: Union[str, None] = "20260704_monitoring_snapshots"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    json_type = postgresql.JSONB(astext_type=sa.Text()) if bind.dialect.name == "postgresql" else sa.JSON()
    op.create_table(
        "monitoring_alerts",
        sa.Column("key", sa.String(length=80), nullable=False),
        sa.Column("level", sa.String(length=20), nullable=False),
        sa.Column("title", sa.String(length=120), nullable=False),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("value", sa.Integer(), nullable=True),
        sa.Column("threshold", sa.Integer(), nullable=True),
        sa.Column("last_triggered_at", sa.DateTime(), nullable=False),
        sa.Column("resolved_at", sa.DateTime(), nullable=True),
        sa.Column("payload", json_type, nullable=False),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("key"),
    )
    op.create_index(op.f("ix_monitoring_alerts_id"), "monitoring_alerts", ["id"], unique=False)
    op.create_index(op.f("ix_monitoring_alerts_key"), "monitoring_alerts", ["key"], unique=True)
    op.create_index(op.f("ix_monitoring_alerts_level"), "monitoring_alerts", ["level"], unique=False)
    op.create_index(op.f("ix_monitoring_alerts_status"), "monitoring_alerts", ["status"], unique=False)
    op.create_index(
        op.f("ix_monitoring_alerts_last_triggered_at"),
        "monitoring_alerts",
        ["last_triggered_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_monitoring_alerts_last_triggered_at"), table_name="monitoring_alerts")
    op.drop_index(op.f("ix_monitoring_alerts_status"), table_name="monitoring_alerts")
    op.drop_index(op.f("ix_monitoring_alerts_level"), table_name="monitoring_alerts")
    op.drop_index(op.f("ix_monitoring_alerts_key"), table_name="monitoring_alerts")
    op.drop_index(op.f("ix_monitoring_alerts_id"), table_name="monitoring_alerts")
    op.drop_table("monitoring_alerts")
