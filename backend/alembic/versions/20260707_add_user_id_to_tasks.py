"""add user_id to tasks

Revision ID: 20260707_tasks_user_id
Revises: 20260704_api_request_logs
Create Date: 2026-07-07
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision: str = "20260707_tasks_user_id"
down_revision: Union[str, None] = "20260704_api_request_logs"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    columns = {col["name"] for col in inspector.get_columns("tasks")} if inspector.has_table("tasks") else set()
    if "user_id" not in columns:
        op.add_column("tasks", sa.Column("user_id", sa.Integer(), nullable=True))
    op.execute("CREATE INDEX IF NOT EXISTS ix_tasks_user_id ON tasks (user_id)")


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    if inspector.has_table("tasks"):
        op.execute("DROP INDEX IF EXISTS ix_tasks_user_id")
        columns = {col["name"] for col in inspector.get_columns("tasks")}
        if "user_id" in columns:
            op.drop_column("tasks", "user_id")
