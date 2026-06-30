"""add_payment_orders

Revision ID: 20260630_payment_orders
Revises: a1f3c9d27e44
Create Date: 2026-06-30 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260630_payment_orders"
down_revision: Union[str, None] = "a1f3c9d27e44"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "payment_orders",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("out_trade_no", sa.String(length=32), nullable=False, comment="商户订单号"),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("package_name", sa.String(length=50), nullable=False, comment="积分套餐名称"),
        sa.Column("amount_fen", sa.Integer(), nullable=False, comment="支付金额（分）"),
        sa.Column("credits", sa.Integer(), nullable=False, comment="到账积分"),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="PENDING", comment="PENDING/PAID/CLOSED"),
        sa.Column("payment_method", sa.String(length=30), nullable=False, server_default="wechat"),
        sa.Column("transaction_id", sa.String(length=100), nullable=True, comment="微信支付订单号"),
        sa.Column("code_url", sa.Text(), nullable=True, comment="Native 支付二维码链接"),
        sa.Column("paid_at", sa.DateTime(), nullable=True),
        sa.Column("notify_raw", sa.Text(), nullable=True, comment="最近一次支付回调原文"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("out_trade_no"),
    )
    op.create_index(op.f("ix_payment_orders_id"), "payment_orders", ["id"], unique=False)
    op.create_index(op.f("ix_payment_orders_out_trade_no"), "payment_orders", ["out_trade_no"], unique=False)
    op.create_index(op.f("ix_payment_orders_status"), "payment_orders", ["status"], unique=False)
    op.create_index(op.f("ix_payment_orders_user_id"), "payment_orders", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_payment_orders_user_id"), table_name="payment_orders")
    op.drop_index(op.f("ix_payment_orders_status"), table_name="payment_orders")
    op.drop_index(op.f("ix_payment_orders_out_trade_no"), table_name="payment_orders")
    op.drop_index(op.f("ix_payment_orders_id"), table_name="payment_orders")
    op.drop_table("payment_orders")
