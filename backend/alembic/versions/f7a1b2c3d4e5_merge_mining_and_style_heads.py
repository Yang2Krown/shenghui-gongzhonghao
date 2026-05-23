"""merge ai_relevant and style_sources heads

Revision ID: f7a1b2c3d4e5
Revises: 20260523_add_is_ai_relevant, 9d2ac59877e5
Create Date: 2026-05-23

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f7a1b2c3d4e5'
down_revision: Union[str, None] = ('20260523_add_is_ai_relevant', '9d2ac59877e5')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
