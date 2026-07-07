"""merge security task owner head

Revision ID: 20260707_merge_security_heads
Revises: 20260704_llm_monitoring, 20260707_tasks_user_id
Create Date: 2026-07-07
"""

from typing import Sequence, Union


revision: str = "20260707_merge_security_heads"
down_revision: Union[str, tuple[str, str], None] = ("20260704_llm_monitoring", "20260707_tasks_user_id")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
