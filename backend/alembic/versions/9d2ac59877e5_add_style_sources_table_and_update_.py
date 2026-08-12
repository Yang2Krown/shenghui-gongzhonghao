"""add_style_sources_table_and_update_style_profile

Revision ID: 9d2ac59877e5
Revises: 22ab956b7d3b
Create Date: 2026-05-23 09:53:57.854436

"""
from typing import Sequence, Union

from alembic import context, op
import sqlalchemy as sa
from sqlalchemy import inspect

# revision identifiers, used by Alembic.
revision: str = '9d2ac59877e5'
down_revision: Union[str, None] = '22ab956b7d3b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def column_exists(
    table_name: str,
    column_name: str,
    *,
    offline_default: bool = False,
) -> bool:
    """用 Inspector 检查列；离线生成时使用调用方提供的基线假设。

    旧实现直接调用 ``op.get_bind().execute``。在 ``alembic upgrade --sql``
    中不存在可执行的 bind，导致 ``NoneType has no attribute scalar``，使
    所有后续迁移都无法生成 SQL。在线迁移仍然保持幂等检查；离线模式按
    干净基线生成标准的新增/删除语句。
    """

    if context.is_offline_mode():
        return offline_default
    bind = op.get_bind()
    inspector = inspect(bind)
    if table_name not in inspector.get_table_names():
        return False
    return column_name in {
        column["name"] for column in inspector.get_columns(table_name)
    }


def table_exists(table_name: str, *, offline_default: bool = False) -> bool:
    """用 Inspector 检查表；离线模式不访问数据库。"""

    if context.is_offline_mode():
        return offline_default
    return table_name in inspect(op.get_bind()).get_table_names()


def upgrade() -> None:
    # 添加 style_profiles 新字段（检查是否已存在）
    columns_to_add = [
        ('version', sa.Integer()),
        ('signature', sa.Text()),
        ('radar', sa.JSON()),
        ('traits', sa.JSON()),
        ('source_count', sa.Integer()),
        ('total_words', sa.Integer()),
        ('trained_at', sa.DateTime()),
    ]

    for col_name, col_type in columns_to_add:
        if not column_exists('style_profiles', col_name):
            op.add_column('style_profiles', sa.Column(col_name, col_type, nullable=True))

    # 检查 style_sources 表是否已存在
    if not table_exists("style_sources"):
        op.create_table(
            'style_sources',
            sa.Column('id', sa.Integer(), primary_key=True, index=True),
            sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
            sa.Column('profile_id', sa.Integer(), sa.ForeignKey('style_profiles.id'), nullable=True),
            sa.Column('title', sa.String(500), nullable=True),
            sa.Column('content_type', sa.String(50), server_default='text'),
            sa.Column('url', sa.String(1000), nullable=True),
            sa.Column('raw_text', sa.Text(), nullable=True),
            sa.Column('preview', sa.Text(), nullable=True),
            sa.Column('word_count', sa.Integer(), server_default='0'),
            sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        )


def downgrade() -> None:
    if table_exists("style_sources", offline_default=True):
        op.drop_table('style_sources')

    columns_to_drop = ['trained_at', 'total_words', 'source_count', 'traits', 'radar', 'signature', 'version']
    for col_name in columns_to_drop:
        if column_exists('style_profiles', col_name, offline_default=True):
            op.drop_column('style_profiles', col_name)
