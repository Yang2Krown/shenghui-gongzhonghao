"""add subscription expiry to user_credits

创作工具改为按月订阅：
- user_credits.subscription_expires_at：创作工具订阅到期时间（naive 北京时间）
- user_credits.gift_credits_at：本期赠送积分的时间（用于前端展示"本期赠送"来源）

到期后由 Celery Beat 任务移除 creation_tool 权益；账户积分余额永久保留。

Revision ID: 20260710_sub_expiry
Revises: 20260709_product_access
Create Date: 2026-07-10
"""

from typing import Sequence, Union

from alembic import context, op
import sqlalchemy as sa
from sqlalchemy import inspect


revision: str = "20260710_sub_expiry"
down_revision: Union[str, None] = "20260709_product_access"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    if context.is_offline_mode():
        columns = set()
    else:
        inspector = inspect(op.get_bind())
        if not inspector.has_table("user_credits"):
            return
        columns = {col["name"] for col in inspector.get_columns("user_credits")}
    if "subscription_expires_at" not in columns:
        op.add_column(
            "user_credits",
            sa.Column(
                "subscription_expires_at",
                sa.DateTime(),
                nullable=True,
                comment="创作工具订阅到期时间",
            ),
        )
    if "gift_credits_at" not in columns:
        op.add_column(
            "user_credits",
            sa.Column(
                "gift_credits_at",
                sa.DateTime(),
                nullable=True,
                comment="本期赠送积分时间",
            ),
        )


def downgrade() -> None:
    if context.is_offline_mode():
        op.drop_column("user_credits", "gift_credits_at")
        op.drop_column("user_credits", "subscription_expires_at")
        return
    inspector = inspect(op.get_bind())
    if not inspector.has_table("user_credits"):
        return
    columns = {col["name"] for col in inspector.get_columns("user_credits")}
    if "gift_credits_at" in columns:
        op.drop_column("user_credits", "gift_credits_at")
    if "subscription_expires_at" in columns:
        op.drop_column("user_credits", "subscription_expires_at")
