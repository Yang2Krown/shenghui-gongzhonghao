"""add celery task monitoring records"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision: str = "20260715_celery_task_runs"
down_revision: Union[str, None] = "20260715_user_timestamps_bjt"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Older application startups could create this model through metadata before
    # Alembic reached this revision. Treat that schema as already provisioned.
    if "celery_task_runs" in inspect(op.get_bind()).get_table_names():
        return
    op.create_table(
        "celery_task_runs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("task_id", sa.String(length=100), nullable=False),
        sa.Column("task_name", sa.String(length=255), nullable=False),
        sa.Column("category", sa.String(length=30), nullable=False),
        sa.Column("queue", sa.String(length=50), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("worker", sa.String(length=255), nullable=True),
        sa.Column("args_json", sa.JSON(), nullable=True),
        sa.Column("kwargs_json", sa.JSON(), nullable=True),
        sa.Column("result_json", sa.JSON(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.String(length=40), nullable=True),
        sa.Column("finished_at", sa.String(length=40), nullable=True),
        sa.Column("last_seen_at", sa.String(length=40), nullable=True),
        sa.Column("is_dead_letter", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("retried_from_id", sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("task_id"),
    )
    for name, column in (
        ("ix_celery_task_runs_task_id", "task_id"),
        ("ix_celery_task_runs_task_name", "task_name"),
        ("ix_celery_task_runs_category", "category"),
        ("ix_celery_task_runs_queue", "queue"),
        ("ix_celery_task_runs_status", "status"),
        ("ix_celery_task_runs_is_dead_letter", "is_dead_letter"),
        ("ix_celery_task_runs_retried_from_id", "retried_from_id"),
    ):
        op.create_index(name, "celery_task_runs", [column], unique=False)


def downgrade() -> None:
    op.drop_table("celery_task_runs")
