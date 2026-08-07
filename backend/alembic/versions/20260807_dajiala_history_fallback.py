"""add Dajiala history fallback identity fields

Revision ID: 20260807_dajiala
Revises: 20260724_xhs_topic_boards
Create Date: 2026-08-07

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260807_dajiala"
down_revision: Union[str, None] = "20260724_xhs_topic_boards"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("source_accounts", sa.Column("wechat_ghid", sa.String(length=200), nullable=True))
    op.add_column("source_accounts", sa.Column("wechat_reference_url", sa.String(length=1000), nullable=True))
    op.create_index("ix_source_accounts_wechat_ghid", "source_accounts", ["wechat_ghid"], unique=False)

    # 现有账号没有 ghid，但已经入库过永久公众号文章。先回填一条文章链接，
    # 让新接口可以从链接反查公众号；接口成功后 adapter 会继续写回 ghid。
    op.execute(
        sa.text(
            """
            UPDATE source_accounts AS account
            SET wechat_reference_url = latest.url
            FROM (
                SELECT DISTINCT ON (raw.source_account_id)
                    raw.source_account_id,
                    raw.url
                FROM raw_infos AS raw
                JOIN source_registry AS source
                  ON source.id = raw.source_registry_id
                WHERE source.source_type = 'dajiala_wechat'
                  AND raw.source_account_id IS NOT NULL
                  AND raw.url ILIKE '%mp.weixin.qq.com%'
                ORDER BY raw.source_account_id,
                         COALESCE(raw.published_at, raw.scraped_at) DESC NULLS LAST,
                         raw.id DESC
            ) AS latest
            WHERE account.id = latest.source_account_id
              AND account.wechat_reference_url IS NULL
            """
        )
    )


def downgrade() -> None:
    op.drop_index("ix_source_accounts_wechat_ghid", table_name="source_accounts")
    op.drop_column("source_accounts", "wechat_reference_url")
    op.drop_column("source_accounts", "wechat_ghid")
