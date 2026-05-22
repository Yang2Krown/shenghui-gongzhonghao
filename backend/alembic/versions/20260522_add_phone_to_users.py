"""add phone to users and make email/password nullable

Revision ID: 20260522_add_phone_to_users
Revises: 20260522_add_outline_tables
Create Date: 2026-05-22 12:00:00.000000
"""

from alembic import op
import sqlalchemy as sa

revision = "20260522_add_phone_to_users"
down_revision = "20260522_add_outline_tables"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("phone", sa.String(20), nullable=True))
    op.create_index("ix_users_phone", "users", ["phone"], unique=True)
    # 允许 email 和 hashed_password 为空（手机注册用户无密码）
    op.alter_column("users", "email", nullable=True)
    op.alter_column("users", "hashed_password", nullable=True)


def downgrade() -> None:
    op.drop_index("ix_users_phone", table_name="users")
    op.drop_column("users", "phone")
    op.alter_column("users", "email", nullable=False)
    op.alter_column("users", "hashed_password", nullable=False)
