"""add_wechat_accounts_table

Revision ID: b5d9cb8d0320
Revises: f9e702eae192
Create Date: 2026-06-11 17:28:04.349171

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'b5d9cb8d0320'
down_revision: Union[str, None] = 'f9e702eae192'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'wechat_accounts',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('account_name', sa.String(100), nullable=False, comment='账号别名'),
        sa.Column('appid', sa.String(64), nullable=False, comment='公众号 AppID'),
        sa.Column('app_secret', sa.String(128), nullable=False, comment='公众号 AppSecret'),
        sa.Column('author', sa.String(32), nullable=True, comment='默认作者名'),
        sa.Column('is_default', sa.Boolean(), server_default='false', nullable=False, comment='是否默认账号'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'account_name', name='uq_wechat_account_user_name'),
    )
    op.create_index('ix_wechat_accounts_id', 'wechat_accounts', ['id'], unique=False)
    op.create_index('ix_wechat_accounts_user_id', 'wechat_accounts', ['user_id'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_wechat_accounts_user_id', table_name='wechat_accounts')
    op.drop_index('ix_wechat_accounts_id', table_name='wechat_accounts')
    op.drop_table('wechat_accounts')
