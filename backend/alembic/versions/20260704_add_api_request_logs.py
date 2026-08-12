"""add api request logs

Revision ID: 20260704_api_request_logs
Revises: 20260704_admin_audit_logs
Create Date: 2026-07-04
"""

from typing import Sequence, Union

from alembic import context, op
import sqlalchemy as sa
from sqlalchemy import inspect


revision: str = "20260704_api_request_logs"
down_revision: Union[str, None] = "20260704_admin_audit_logs"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    table_exists = (
        False
        if context.is_offline_mode()
        else inspect(op.get_bind()).has_table("api_request_logs")
    )
    if not table_exists:
        op.create_table(
            "api_request_logs",
            sa.Column("method", sa.String(length=10), nullable=False),
            sa.Column("path", sa.String(length=500), nullable=False),
            sa.Column("status_code", sa.Integer(), nullable=False),
            sa.Column("duration_ms", sa.Float(), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=True),
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )
    op.execute("CREATE INDEX IF NOT EXISTS ix_api_request_logs_id ON api_request_logs (id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_api_request_logs_method ON api_request_logs (method)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_api_request_logs_path ON api_request_logs (path)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_api_request_logs_status_code ON api_request_logs (status_code)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_api_request_logs_user_id ON api_request_logs (user_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_api_request_logs_created_at ON api_request_logs (created_at)")


def downgrade() -> None:
    op.drop_index(op.f("ix_api_request_logs_created_at"), table_name="api_request_logs")
    op.drop_index(op.f("ix_api_request_logs_user_id"), table_name="api_request_logs")
    op.drop_index(op.f("ix_api_request_logs_status_code"), table_name="api_request_logs")
    op.drop_index(op.f("ix_api_request_logs_path"), table_name="api_request_logs")
    op.drop_index(op.f("ix_api_request_logs_method"), table_name="api_request_logs")
    op.drop_index(op.f("ix_api_request_logs_id"), table_name="api_request_logs")
    op.drop_table("api_request_logs")
