"""add llm monitoring

Revision ID: 20260704_llm_monitoring
Revises: 20260704_api_request_logs
Create Date: 2026-07-04
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect
from datetime import datetime, timezone, timedelta


revision: str = "20260704_llm_monitoring"
down_revision: Union[str, None] = "20260704_api_request_logs"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    now = datetime.now(timezone(timedelta(hours=8))).replace(tzinfo=None)

    if not inspector.has_table("llm_model_pricing"):
        op.create_table(
            "llm_model_pricing",
            sa.Column("provider", sa.String(length=50), nullable=False),
            sa.Column("model", sa.String(length=120), nullable=False),
            sa.Column("display_name", sa.String(length=160), nullable=True),
            sa.Column("input_price_per_million", sa.Numeric(12, 6), nullable=False),
            sa.Column("output_price_per_million", sa.Numeric(12, 6), nullable=False),
            sa.Column("currency", sa.String(length=10), nullable=False),
            sa.Column("enabled", sa.Boolean(), nullable=False),
            sa.Column("note", sa.Text(), nullable=True),
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("provider", "model", name="uq_llm_model_pricing_provider_model"),
        )

    if not inspector.has_table("llm_call_logs"):
        op.create_table(
            "llm_call_logs",
            sa.Column("provider", sa.String(length=50), nullable=False),
            sa.Column("model", sa.String(length=120), nullable=False),
            sa.Column("operation", sa.String(length=80), nullable=True),
            sa.Column("operation_id", sa.String(length=120), nullable=True),
            sa.Column("user_id", sa.Integer(), nullable=True),
            sa.Column("status", sa.String(length=20), nullable=False),
            sa.Column("prompt_tokens", sa.Integer(), nullable=False),
            sa.Column("completion_tokens", sa.Integer(), nullable=False),
            sa.Column("total_tokens", sa.Integer(), nullable=False),
            sa.Column("cost_yuan", sa.Numeric(12, 6), nullable=False),
            sa.Column("duration_ms", sa.Float(), nullable=False),
            sa.Column("finish_reason", sa.String(length=80), nullable=True),
            sa.Column("error_message", sa.Text(), nullable=True),
            sa.Column("pricing_snapshot", sa.JSON(), nullable=True),
            sa.Column("metadata_json", sa.JSON(), nullable=True),
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )

    for table, columns in {
        "llm_model_pricing": ["id", "provider", "model", "enabled"],
        "llm_call_logs": ["id", "provider", "model", "operation", "operation_id", "user_id", "status", "created_at"],
    }.items():
        for column in columns:
            op.execute(f"CREATE INDEX IF NOT EXISTS ix_{table}_{column} ON {table} ({column})")

    pricing = sa.table(
        "llm_model_pricing",
        sa.column("provider", sa.String),
        sa.column("model", sa.String),
        sa.column("display_name", sa.String),
        sa.column("input_price_per_million", sa.Numeric),
        sa.column("output_price_per_million", sa.Numeric),
        sa.column("currency", sa.String),
        sa.column("enabled", sa.Boolean),
        sa.column("note", sa.Text),
        sa.column("created_at", sa.DateTime),
        sa.column("updated_at", sa.DateTime),
    )
    op.bulk_insert(pricing, [
        {"provider": "deepseek", "model": "deepseek-v4-flash", "display_name": "DeepSeek V4 Flash", "input_price_per_million": 2, "output_price_per_million": 8, "currency": "CNY", "enabled": True, "note": "默认估算价，可在后台调整", "created_at": now, "updated_at": now},
        {"provider": "moonshot", "model": "moonshot-v1-32k", "display_name": "Moonshot v1 32k", "input_price_per_million": 12, "output_price_per_million": 12, "currency": "CNY", "enabled": True, "note": "默认估算价，可在后台调整", "created_at": now, "updated_at": now},
        {"provider": "anthropic", "model": "claude-sonnet-4-6", "display_name": "Claude Sonnet 4.6", "input_price_per_million": 21, "output_price_per_million": 105, "currency": "CNY", "enabled": True, "note": "默认估算价，可在后台调整", "created_at": now, "updated_at": now},
        {"provider": "aigocode", "model": "claude-opus-4-8-r", "display_name": "AIGoCode Claude Opus", "input_price_per_million": 105, "output_price_per_million": 525, "currency": "CNY", "enabled": True, "note": "默认估算价，可在后台调整", "created_at": now, "updated_at": now},
    ])


def downgrade() -> None:
    op.drop_table("llm_call_logs")
    op.drop_table("llm_model_pricing")
