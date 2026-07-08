"""add membership system

Revision ID: 20260707_membership
Revises: 20260707_merge_security_heads
Create Date: 2026-07-07
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision: str = "20260707_membership"
down_revision: Union[str, None] = "20260707_merge_security_heads"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    tables = set(inspector.get_table_names())

    # 1. users 表加 is_member / member_since
    if inspector.has_table("users"):
        columns = {col["name"] for col in inspector.get_columns("users")}
        if "is_member" not in columns:
            op.add_column("users", sa.Column(
                "is_member", sa.Boolean(), nullable=False, server_default=sa.text("false")
            ))
        if "member_since" not in columns:
            op.add_column("users", sa.Column(
                "member_since", sa.DateTime(), nullable=True
            ))

    # 2. payment_orders 表加 order_type
    if inspector.has_table("payment_orders"):
        columns = {col["name"] for col in inspector.get_columns("payment_orders")}
        if "order_type" not in columns:
            op.add_column("payment_orders", sa.Column(
                "order_type", sa.String(20), nullable=False, server_default="credits"
            ))

    if "users" not in tables:
        return

    # 3. 清理无手机号用户（按产品规则：后续只允许手机号登录/自动注册）
    _no_phone = "SELECT id FROM users WHERE phone IS NULL OR phone = ''"

    def _has_column(table_name: str, column_name: str) -> bool:
        return table_name in tables and column_name in {
            col["name"] for col in inspector.get_columns(table_name)
        }

    def _delete_user_rows(table_name: str) -> None:
        if _has_column(table_name, "user_id"):
            op.execute(f"DELETE FROM {table_name} WHERE user_id IN ({_no_phone})")

    def _null_user_rows(table_name: str) -> None:
        if _has_column(table_name, "user_id"):
            op.execute(f"UPDATE {table_name} SET user_id = NULL WHERE user_id IN ({_no_phone})")

    # nullable=True 的 FK：置 NULL 即可，保留公共素材/任务记录
    for table_name in ("tasks", "topic_candidates"):
        _null_user_rows(table_name)

    # nullable=False 的 FK：删除关联行（先删更底层的子表）
    for table_name in (
        "credit_transactions",
        "user_credits",
        "payment_orders",
        "user_profiles",
        "generation_records",
        "content_creations",
        "topics",
        "topic_collections",
        "style_profiles",
        "style_sources",
        "articles_for_analysis",
        "wechat_accounts",
        "feishu_auths",
    ):
        _delete_user_rows(table_name)

    op.execute("DELETE FROM users WHERE phone IS NULL OR phone = ''")

    # 4. 历史保留用户默认设为会员；后续手机号新用户默认非会员
    op.execute("UPDATE users SET is_member = true, member_since = NOW() WHERE is_member = false")


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)

    if inspector.has_table("payment_orders"):
        columns = {col["name"] for col in inspector.get_columns("payment_orders")}
        if "order_type" in columns:
            op.drop_column("payment_orders", "order_type")

    if inspector.has_table("users"):
        columns = {col["name"] for col in inspector.get_columns("users")}
        if "member_since" in columns:
            op.drop_column("users", "member_since")
        if "is_member" in columns:
            op.drop_column("users", "is_member")
