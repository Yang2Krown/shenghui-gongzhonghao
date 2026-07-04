"""add admin audit logs

Revision ID: 20260704_admin_audit_logs
Revises: 20260704_alert_handling
Create Date: 2026-07-04
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "20260704_admin_audit_logs"
down_revision: Union[str, None] = "20260704_alert_handling"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    json_type = postgresql.JSONB(astext_type=sa.Text()) if bind.dialect.name == "postgresql" else sa.JSON()
    op.create_table(
        "admin_audit_logs",
        sa.Column("actor_user_id", sa.Integer(), nullable=True),
        sa.Column("action", sa.String(length=80), nullable=False),
        sa.Column("target_type", sa.String(length=50), nullable=True),
        sa.Column("target_id", sa.String(length=100), nullable=True),
        sa.Column("summary", sa.String(length=300), nullable=True),
        sa.Column("detail", sa.Text(), nullable=True),
        sa.Column("metadata_json", json_type, nullable=False),
        sa.Column("occurred_at", sa.DateTime(), nullable=False),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_admin_audit_logs_id"), "admin_audit_logs", ["id"], unique=False)
    op.create_index(op.f("ix_admin_audit_logs_actor_user_id"), "admin_audit_logs", ["actor_user_id"], unique=False)
    op.create_index(op.f("ix_admin_audit_logs_action"), "admin_audit_logs", ["action"], unique=False)
    op.create_index(op.f("ix_admin_audit_logs_target_type"), "admin_audit_logs", ["target_type"], unique=False)
    op.create_index(op.f("ix_admin_audit_logs_target_id"), "admin_audit_logs", ["target_id"], unique=False)
    op.create_index(op.f("ix_admin_audit_logs_occurred_at"), "admin_audit_logs", ["occurred_at"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_admin_audit_logs_occurred_at"), table_name="admin_audit_logs")
    op.drop_index(op.f("ix_admin_audit_logs_target_id"), table_name="admin_audit_logs")
    op.drop_index(op.f("ix_admin_audit_logs_target_type"), table_name="admin_audit_logs")
    op.drop_index(op.f("ix_admin_audit_logs_action"), table_name="admin_audit_logs")
    op.drop_index(op.f("ix_admin_audit_logs_actor_user_id"), table_name="admin_audit_logs")
    op.drop_index(op.f("ix_admin_audit_logs_id"), table_name="admin_audit_logs")
    op.drop_table("admin_audit_logs")
