"""add feishu_auths

飞书商单 brief 接入：每用户一条飞书授权绑定（设备码 OAuth）。

Revision ID: a1f3c9d27e44
Revises: d2b8e4f1a902
Create Date: 2026-06-26

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1f3c9d27e44'
down_revision: Union[str, None] = 'd2b8e4f1a902'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'feishu_auths',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('feishu_user_name', sa.String(length=128), nullable=True),
        sa.Column('feishu_open_id', sa.String(length=128), nullable=True),
        sa.Column('status', sa.String(length=16), nullable=False, server_default='none'),
        sa.Column('scopes', sa.String(length=512), nullable=True),
        sa.Column('access_token', sa.Text(), nullable=True),
        sa.Column('refresh_token', sa.Text(), nullable=True),
        sa.Column('token_expires_at', sa.DateTime(), nullable=True),
        sa.Column('refresh_expires_at', sa.DateTime(), nullable=True),
        sa.Column('device_code', sa.String(length=256), nullable=True),
        sa.Column('last_error', sa.String(length=512), nullable=True),
        sa.Column('authorized_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], name='fk_feishu_auths_user_id_users'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', name='uq_feishu_auth_user'),
    )
    op.create_index(op.f('ix_feishu_auths_id'), 'feishu_auths', ['id'], unique=False)
    op.create_index(op.f('ix_feishu_auths_user_id'), 'feishu_auths', ['user_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_feishu_auths_user_id'), table_name='feishu_auths')
    op.drop_index(op.f('ix_feishu_auths_id'), table_name='feishu_auths')
    op.drop_table('feishu_auths')
