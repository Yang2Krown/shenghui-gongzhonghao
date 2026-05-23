"""merge heads

Revision ID: 22ab956b7d3b
Revises: 20260522_add_phone_to_users, e55bc58b6a7b
Create Date: 2026-05-22 18:52:49.806061

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '22ab956b7d3b'
down_revision: Union[str, None] = ('20260522_add_phone_to_users', 'e55bc58b6a7b')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
