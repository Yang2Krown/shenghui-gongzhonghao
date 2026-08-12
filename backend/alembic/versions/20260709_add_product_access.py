"""add product access entitlements

Revision ID: 20260709_product_access
Revises: 20260708_course
Create Date: 2026-07-09
"""

from typing import Sequence, Union

from alembic import context, op
import sqlalchemy as sa
from sqlalchemy import inspect
from sqlalchemy.dialects import postgresql


revision: str = "20260709_product_access"
down_revision: Union[str, None] = "20260708_course"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    if context.is_offline_mode():
        inspector = None
        columns = set()
        tables = {"users"}
    else:
        inspector = inspect(op.get_bind())
        if not inspector.has_table("users"):
            return
        columns = {col["name"] for col in inspector.get_columns("users")}
        tables = set(inspector.get_table_names())
    if "product_access" not in columns:
        op.add_column(
            "users",
            sa.Column(
                "product_access",
                postgresql.JSONB(astext_type=sa.Text()),
                nullable=False,
                server_default=sa.text("'[]'::jsonb"),
                comment="已开通产品权益",
            ),
        )

    # 历史已缴会员先迁移为「创作工具」权益，后续权益按产品单独叠加。
    op.execute(
        """
        UPDATE users
        SET product_access = CASE
            WHEN product_access ? 'creation_tool' THEN product_access
            ELSE product_access || '["creation_tool"]'::jsonb
        END
        WHERE COALESCE(is_member, false) = true
        """
    )

    # 手机号是唯一身份；旧的默认邮箱管理员和无手机号账号不再保留。
    target_users = "SELECT id FROM users WHERE email = 'admin@example.com' OR phone IS NULL OR phone = ''"
    def _has_column(table_name: str, column_name: str) -> bool:
        if context.is_offline_mode():
            return False
        return table_name in tables and column_name in {
            col["name"] for col in inspector.get_columns(table_name)
        }

    def _delete_user_rows(table_name: str) -> None:
        if _has_column(table_name, "user_id"):
            op.execute(f"DELETE FROM {table_name} WHERE user_id IN ({target_users})")

    def _null_user_rows(table_name: str) -> None:
        if _has_column(table_name, "user_id"):
            op.execute(f"UPDATE {table_name} SET user_id = NULL WHERE user_id IN ({target_users})")

    for table_name in ("tasks", "topic_candidates"):
        _null_user_rows(table_name)

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

    op.execute("DELETE FROM users WHERE email = 'admin@example.com' OR phone IS NULL OR phone = ''")

    # 最高管理员固定为配置手机号。只有该手机号保留 is_superuser。
    op.execute(
        """
        UPDATE users
        SET role = 'admin', is_superuser = true
        WHERE phone = '18021751281'
        """
    )
    op.execute(
        """
        UPDATE users
        SET is_superuser = false
        WHERE phone IS DISTINCT FROM '18021751281'
        """
    )

    op.alter_column("users", "product_access", server_default=None)


def downgrade() -> None:
    if context.is_offline_mode():
        op.drop_column("users", "product_access")
        return
    inspector = inspect(op.get_bind())
    if inspector.has_table("users"):
        columns = {col["name"] for col in inspector.get_columns("users")}
        if "product_access" in columns:
            op.drop_column("users", "product_access")
