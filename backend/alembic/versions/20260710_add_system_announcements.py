"""add system announcements

Revision ID: 20260710_announcements
Revises: 20260710_sub_expiry
Create Date: 2026-07-10
"""
from typing import Sequence, Union
from alembic import context, op
import sqlalchemy as sa
from sqlalchemy import inspect

revision: str = "20260710_announcements"
down_revision: Union[str, None] = "20260710_sub_expiry"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    if context.is_offline_mode():
        tables = set()
    else:
        inspector = inspect(op.get_bind())
        tables = set(inspector.get_table_names())
    if "system_announcements" not in tables:
        op.create_table("system_announcements", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("created_at", sa.DateTime(), nullable=False), sa.Column("updated_at", sa.DateTime(), nullable=False), sa.Column("title", sa.String(length=120), nullable=False), sa.Column("content", sa.Text(), nullable=False), sa.Column("is_published", sa.Boolean(), nullable=False, server_default=sa.true()), sa.Column("expires_at", sa.DateTime(), nullable=False), sa.Column("published_at", sa.DateTime(), nullable=False), sa.Column("created_by_user_id", sa.Integer(), nullable=True))
        op.create_index("ix_system_announcements_is_published", "system_announcements", ["is_published"])
        op.create_index("ix_system_announcements_expires_at", "system_announcements", ["expires_at"])
        op.create_index("ix_system_announcements_published_at", "system_announcements", ["published_at"])
    if "system_announcement_dismissals" not in tables:
        op.create_table("system_announcement_dismissals", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("created_at", sa.DateTime(), nullable=False), sa.Column("updated_at", sa.DateTime(), nullable=False), sa.Column("announcement_id", sa.Integer(), nullable=False), sa.Column("user_id", sa.Integer(), nullable=False), sa.Column("dismissed_at", sa.DateTime(), nullable=False), sa.UniqueConstraint("announcement_id", "user_id", name="uq_announcement_dismissal_user"))
        op.create_index("ix_system_announcement_dismissals_announcement_id", "system_announcement_dismissals", ["announcement_id"])
        op.create_index("ix_system_announcement_dismissals_user_id", "system_announcement_dismissals", ["user_id"])

def downgrade() -> None:
    op.drop_table("system_announcement_dismissals")
    op.drop_table("system_announcements")
