"""add_updated_at_to_credit_transactions

补 c7a1e4f5d8b2 漏建的列：credit_transactions.updated_at。
模型 CreditTransaction 继承 BaseModel，含 updated_at，但建表迁移遗漏，
导致购买/写入交易记录时 INSERT 报 UndefinedColumnError。

Revision ID: d8b2e5a1c7f4
Revises: c7a1e4f5d8b2
Create Date: 2026-06-13 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'd8b2e5a1c7f4'
down_revision: Union[str, None] = 'c7a1e4f5d8b2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'credit_transactions',
        sa.Column(
            'updated_at',
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column('credit_transactions', 'updated_at')
