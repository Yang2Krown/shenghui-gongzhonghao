"""add monitoring alert handling fields

Revision ID: 20260704_alert_handling
Revises: 20260704_monitoring_alerts
Create Date: 2026-07-04
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260704_alert_handling"
down_revision: Union[str, None] = "20260704_monitoring_alerts"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("monitoring_alerts", sa.Column("handled_by_user_id", sa.Integer(), nullable=True))
    op.add_column("monitoring_alerts", sa.Column("handled_at", sa.DateTime(), nullable=True))
    op.add_column("monitoring_alerts", sa.Column("note", sa.Text(), nullable=True))
    op.create_index(
        op.f("ix_monitoring_alerts_handled_by_user_id"),
        "monitoring_alerts",
        ["handled_by_user_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_monitoring_alerts_handled_by_user_id"), table_name="monitoring_alerts")
    op.drop_column("monitoring_alerts", "note")
    op.drop_column("monitoring_alerts", "handled_at")
    op.drop_column("monitoring_alerts", "handled_by_user_id")
