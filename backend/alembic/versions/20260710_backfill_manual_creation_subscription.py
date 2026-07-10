"""backfill manually granted creation-tool subscriptions

Revision ID: 20260710_manual_creation_sub
Revises: 20260710_announcements
Create Date: 2026-07-10
"""

from typing import Sequence, Union

from alembic import op
from sqlalchemy import inspect


revision: str = "20260710_manual_creation_sub"
down_revision: Union[str, None] = "20260710_announcements"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Give legacy manual creation-tool grants their first subscription month and 6000 credits."""
    bind = op.get_bind()
    inspector = inspect(bind)
    required_tables = {"users", "user_credits", "credit_transactions"}
    if not required_tables.issubset(set(inspector.get_table_names())):
        return

    # Product access is JSONB in the entitlement migration. Admins already have permanent access
    # and are intentionally excluded from subscription/credit expiry bookkeeping.
    op.execute(
        """
        WITH granted AS (
            INSERT INTO user_credits (
                user_id, balance, total_purchased, total_consumed, total_gifted,
                subscription_expires_at, gift_credits_at, created_at, updated_at
            )
            SELECT u.id, 6000, 0, 0, 6000,
                   NOW() + INTERVAL '1 month', NOW(), NOW(), NOW()
            FROM users u
            WHERE u.product_access ? 'creation_tool'
              AND COALESCE(u.is_superuser, false) = false
              AND COALESCE(LOWER(u.role), 'user') <> 'admin'
            ON CONFLICT (user_id) DO UPDATE
            SET balance = user_credits.balance + 6000,
                total_gifted = user_credits.total_gifted + 6000,
                subscription_expires_at = NOW() + INTERVAL '1 month',
                gift_credits_at = NOW(),
                updated_at = NOW()
            WHERE user_credits.subscription_expires_at IS NULL
            RETURNING id, user_id, balance
        )
        INSERT INTO credit_transactions (
            user_id, credit_account_id, type, amount, balance_after, description, created_at
        )
        SELECT user_id, id, 'gift', 6000, balance, '历史管理员开通创作工具赠送积分', NOW()
        FROM granted
        """
    )


def downgrade() -> None:
    # Do not remove granted credits in downgrade: they are a legitimate recorded entitlement.
    pass
