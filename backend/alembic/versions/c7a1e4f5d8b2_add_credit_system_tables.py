"""add_credit_system_tables

Revision ID: c7a1e4f5d8b2
Revises: b5d9cb8d0320
Create Date: 2026-06-11 20:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'c7a1e4f5d8b2'
down_revision: Union[str, None] = 'b5d9cb8d0320'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 用户积分账户表
    op.create_table(
        'user_credits',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('balance', sa.Integer(), nullable=False, server_default='0', comment='当前余额'),
        sa.Column('total_purchased', sa.Integer(), nullable=False, server_default='0', comment='累计购买'),
        sa.Column('total_consumed', sa.Integer(), nullable=False, server_default='0', comment='累计消耗'),
        sa.Column('total_gifted', sa.Integer(), nullable=False, server_default='0', comment='累计赠送'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id'),
    )
    op.create_index('ix_user_credits_user_id', 'user_credits', ['user_id'])

    # 积分交易记录表
    op.create_table(
        'credit_transactions',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('credit_account_id', sa.Integer(), sa.ForeignKey('user_credits.id'), nullable=False),
        sa.Column('type', sa.String(20), nullable=False, comment='交易类型: purchase/consume/gift/refund'),
        sa.Column('amount', sa.Integer(), nullable=False, comment='正数=入账，负数=消耗'),
        sa.Column('balance_after', sa.Integer(), nullable=True, comment='操作后余额'),
        sa.Column('operation', sa.String(50), nullable=True, comment='操作类型'),
        sa.Column('operation_id', sa.String(100), nullable=True, comment='关联的任务ID'),
        sa.Column('token_usage', sa.JSON(), nullable=True, comment='token使用详情'),
        sa.Column('cost_yuan', sa.Numeric(10, 4), nullable=True, comment='实际LLM成本（人民币）'),
        sa.Column('payment_amount_yuan', sa.Numeric(10, 2), nullable=True, comment='支付金额（人民币）'),
        sa.Column('payment_method', sa.String(30), nullable=True, comment='支付方式'),
        sa.Column('payment_order_id', sa.String(100), nullable=True, comment='支付订单号'),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_credit_transactions_user_id', 'credit_transactions', ['user_id'])
    op.create_index('ix_credit_transactions_credit_account_id', 'credit_transactions', ['credit_account_id'])
    op.create_index('ix_credit_transactions_type', 'credit_transactions', ['type'])
    op.create_index('ix_credit_transactions_operation', 'credit_transactions', ['operation'])

    # 积分套餐表（预置数据）
    op.create_table(
        'credit_packages',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('name', sa.String(50), nullable=False, comment='套餐名称'),
        sa.Column('credits', sa.Integer(), nullable=False, comment='积分数量'),
        sa.Column('price_yuan', sa.Numeric(10, 2), nullable=False, comment='价格（人民币）'),
        sa.Column('original_price_yuan', sa.Numeric(10, 2), nullable=True, comment='原价'),
        sa.Column('description', sa.String(200), nullable=True, comment='套餐描述'),
        sa.Column('badge', sa.String(50), nullable=True, comment='角标'),
        sa.Column('is_active', sa.Boolean(), server_default='true', nullable=False),
        sa.Column('sort_order', sa.Integer(), server_default='0', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )

    # 插入默认套餐数据
    op.execute("""
        INSERT INTO credit_packages (name, credits, price_yuan, original_price_yuan, description, badge, sort_order)
        VALUES 
            ('体验包', 100, 9.9, NULL, '适合轻度使用，可创作约 5 篇完整文章', NULL, 1),
            ('标准包', 500, 39, 49.5, '最受欢迎，可创作约 27 篇完整文章', '推荐', 2),
            ('专业包', 1200, 79, 118.8, '专业运营首选，可创作约 66 篇完整文章', '超值', 3),
            ('团队包', 3000, 169, 297, '团队批量采购，可创作约 166 篇完整文章', NULL, 4)
    """)


def downgrade() -> None:
    op.drop_table('credit_packages')
    op.drop_index('ix_credit_transactions_operation', table_name='credit_transactions')
    op.drop_index('ix_credit_transactions_type', table_name='credit_transactions')
    op.drop_index('ix_credit_transactions_credit_account_id', table_name='credit_transactions')
    op.drop_index('ix_credit_transactions_user_id', table_name='credit_transactions')
    op.drop_table('credit_transactions')
    op.drop_index('ix_user_credits_user_id', table_name='user_credits')
    op.drop_table('user_credits')