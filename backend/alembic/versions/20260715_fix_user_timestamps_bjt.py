"""fix user timestamps to Beijing time

Revision ID: 20260715_user_timestamps_bjt
Revises: 20260710_manual_creation_sub
Create Date: 2026-07-15
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260715_user_timestamps_bjt"
down_revision: Union[str, None] = "20260710_manual_creation_sub"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """将旧版按数据库 UTC 写入的用户时间修正为北京时间。"""
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        expression = "{column} + INTERVAL '8 hours'"
    elif bind.dialect.name == "sqlite":
        expression = "datetime({column}, '+8 hours')"
    else:
        raise RuntimeError(f"Unsupported database dialect: {bind.dialect.name}")

    for column in ("created_at", "updated_at", "last_login"):
        op.execute(
            sa.text(
                f"UPDATE users SET {column} = {expression.format(column=column)} "
                f"WHERE {column} IS NOT NULL"
            )
        )


def downgrade() -> None:
    """回滚一次性校正，恢复旧版 UTC 数值。"""
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        expression = "{column} - INTERVAL '8 hours'"
    elif bind.dialect.name == "sqlite":
        expression = "datetime({column}, '-8 hours')"
    else:
        raise RuntimeError(f"Unsupported database dialect: {bind.dialect.name}")

    for column in ("created_at", "updated_at", "last_login"):
        op.execute(
            sa.text(
                f"UPDATE users SET {column} = {expression.format(column=column)} "
                f"WHERE {column} IS NOT NULL"
            )
        )
