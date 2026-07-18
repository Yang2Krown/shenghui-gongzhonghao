"""add xhs keyword material collection

Revision ID: 20260716_xhs_materials
Revises: 20260715_remove_adhoc_topics
"""
from typing import Sequence, Union
from datetime import datetime
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect
from sqlalchemy.dialects.postgresql import insert

revision: str = "20260716_xhs_materials"
down_revision: Union[str, None] = "20260715_remove_adhoc_topics"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

BASE_KEYWORDS = [
    "大模型","AI Agent","Coding Agent","Claude","ChatGPT","DeepSeek","Cursor","AI 编程","vibe coding","Sora","AI 视频",
    "Midjourney","提示词","MCP","智能体","多模态","开源模型","具身智能","generative AI","LLM","Claude AI","GPT-5",
    "open source LLM","RAG","AI coding","agentic AI","fine-tuning","multimodal","prompt engineering","MCP protocol","AI startup",
    "LLM inference","AI research",
]


def _timestamps():
    return [sa.Column("id", sa.Integer(), primary_key=True), sa.Column("created_at", sa.DateTime(), nullable=False), sa.Column("updated_at", sa.DateTime(), nullable=False)]


def _seed_base_keywords() -> None:
    normalized_keywords = [" ".join(k.lower().split()) for k in BASE_KEYWORDS]
    if len(BASE_KEYWORDS) != 33 or len(set(normalized_keywords)) != 33:
        raise RuntimeError("小红书基础关键词必须正好 33 个且标准化后唯一")
    table = sa.table(
        "xhs_keywords",
        sa.column("keyword"), sa.column("normalized_keyword"), sa.column("keyword_type"),
        sa.column("schedule_group"), sa.column("enabled"), sa.column("derived_evidence", sa.JSON()),
        sa.column("created_at"), sa.column("updated_at"),
    )
    now = datetime.now()
    rows = [
        {"keyword": keyword, "normalized_keyword": normalized_keywords[i], "keyword_type": "base", "schedule_group": i // 11 + 1, "enabled": True, "derived_evidence": {}, "created_at": now, "updated_at": now}
        for i, keyword in enumerate(BASE_KEYWORDS)
    ]
    op.get_bind().execute(insert(table).values(rows).on_conflict_do_nothing(index_elements=["normalized_keyword"]))


def upgrade() -> None:
    expected_tables = {
        "xhs_keywords", "xhs_keyword_runs", "xhs_notes", "xhs_note_discoveries",
        "xhs_provider_calls", "xhs_engagement_snapshots", "xhs_daily_quotas", "xhs_image_failure_reports",
    }
    existing_tables = expected_tables.intersection(inspect(op.get_bind()).get_table_names())
    if existing_tables:
        if existing_tables != expected_tables:
            missing = ", ".join(sorted(expected_tables - existing_tables))
            raise RuntimeError(f"小红书素材表仅部分存在，拒绝自动跳过迁移；缺少: {missing}")
        _seed_base_keywords()
        return
    op.create_table("xhs_keywords", *_timestamps(), sa.Column("keyword", sa.String(120), nullable=False), sa.Column("normalized_keyword", sa.String(120), nullable=False, unique=True), sa.Column("keyword_type", sa.String(20), nullable=False, server_default="base"), sa.Column("schedule_group", sa.Integer()), sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()), sa.Column("derived_evidence", sa.JSON(), nullable=False, server_default="{}"), sa.Column("cooldown_until", sa.Date()), sa.Column("last_run_at", sa.DateTime()), sa.Column("next_run_at", sa.DateTime()))
    op.create_table("xhs_keyword_runs", *_timestamps(), sa.Column("keyword_id", sa.Integer(), sa.ForeignKey("xhs_keywords.id", ondelete="CASCADE"), nullable=False), sa.Column("run_date", sa.Date(), nullable=False), sa.Column("status", sa.String(30), nullable=False, server_default="pending"), sa.Column("tikhub_status", sa.String(30), nullable=False, server_default="pending"), sa.Column("cli_status", sa.String(30), nullable=False, server_default="pending"), sa.Column("tikhub_raw_count", sa.Integer(), nullable=False, server_default="0"), sa.Column("cli_raw_count", sa.Integer(), nullable=False, server_default="0"), sa.Column("merged_count", sa.Integer(), nullable=False, server_default="0"), sa.Column("within_week_count", sa.Integer(), nullable=False, server_default="0"), sa.Column("eligible_like_count", sa.Integer(), nullable=False, server_default="0"), sa.Column("filtered_count", sa.Integer(), nullable=False, server_default="0"), sa.Column("final_count", sa.Integer(), nullable=False, server_default="0"), sa.Column("displayable_count", sa.Integer(), nullable=False, server_default="0"), sa.Column("paid_call_count", sa.Integer(), nullable=False, server_default="0"), sa.Column("rejection_counts", sa.JSON(), nullable=False, server_default="{}"), sa.Column("error_message", sa.Text()), sa.Column("started_at", sa.DateTime()), sa.Column("finished_at", sa.DateTime()), sa.UniqueConstraint("keyword_id", "run_date", name="uq_xhs_keyword_run_day"))
    op.create_table("xhs_notes", *_timestamps(), sa.Column("note_id", sa.String(100), nullable=False, unique=True), sa.Column("title", sa.String(500)), sa.Column("content", sa.Text()), sa.Column("published_at", sa.DateTime()), sa.Column("note_type", sa.String(20)), sa.Column("author_id", sa.String(100)), sa.Column("author_nickname", sa.String(200)), sa.Column("author_bio", sa.Text()), sa.Column("avatar_url", sa.String(2000)), sa.Column("cover_url", sa.String(2000)), sa.Column("native_tags", sa.JSON(), nullable=False, server_default="[]"), sa.Column("ai_summary", sa.Text()), sa.Column("ai_topics", sa.JSON(), nullable=False, server_default="[]"), sa.Column("like_count", sa.Integer()), sa.Column("collect_count", sa.Integer()), sa.Column("comment_count", sa.Integer()), sa.Column("share_count", sa.Integer()), sa.Column("view_count", sa.Integer()), sa.Column("stable_url", sa.String(1000), nullable=False), sa.Column("latest_xsec_url", sa.String(2000)), sa.Column("first_discovered_at", sa.DateTime(), nullable=False), sa.Column("last_discovered_at", sa.DateTime(), nullable=False), sa.Column("detail_status", sa.String(30), nullable=False, server_default="discovered"), sa.Column("media_status", sa.String(30), nullable=False, server_default="remote_ok"), sa.Column("quality_status", sa.String(30), nullable=False, server_default="pending"), sa.Column("comprehensive_score", sa.Float(), nullable=False, server_default="0"), sa.Column("raw_info_id", sa.Integer(), sa.ForeignKey("raw_infos.id", ondelete="SET NULL")), sa.Column("source_payload", sa.JSON(), nullable=False, server_default="{}"))
    op.create_table("xhs_note_discoveries", *_timestamps(), sa.Column("note_id", sa.Integer(), sa.ForeignKey("xhs_notes.id", ondelete="CASCADE"), nullable=False), sa.Column("keyword_id", sa.Integer(), sa.ForeignKey("xhs_keywords.id", ondelete="CASCADE"), nullable=False), sa.Column("run_id", sa.Integer(), sa.ForeignKey("xhs_keyword_runs.id", ondelete="CASCADE"), nullable=False), sa.Column("provider", sa.String(30), nullable=False), sa.Column("provider_rank", sa.Integer()), sa.Column("discovered_at", sa.DateTime(), nullable=False), sa.UniqueConstraint("run_id", "note_id", "provider", name="uq_xhs_discovery_run_note_src"))
    op.create_table("xhs_provider_calls", *_timestamps(), sa.Column("provider", sa.String(30), nullable=False), sa.Column("operation", sa.String(30), nullable=False), sa.Column("run_id", sa.Integer(), sa.ForeignKey("xhs_keyword_runs.id", ondelete="SET NULL")), sa.Column("note_identity", sa.String(100)), sa.Column("status", sa.String(30), nullable=False), sa.Column("is_paid", sa.Boolean(), nullable=False, server_default=sa.false()), sa.Column("request_count", sa.Integer(), nullable=False, server_default="1"), sa.Column("latency_ms", sa.Integer()), sa.Column("estimated_cost", sa.Float(), nullable=False, server_default="0"), sa.Column("error_code", sa.String(80)), sa.Column("error_message", sa.Text()), sa.Column("metadata_json", sa.JSON(), nullable=False, server_default="{}"))
    op.create_table("xhs_engagement_snapshots", *_timestamps(), sa.Column("note_id", sa.Integer(), sa.ForeignKey("xhs_notes.id", ondelete="CASCADE"), nullable=False), sa.Column("snapshot_date", sa.Date(), nullable=False), sa.Column("like_count", sa.Integer()), sa.Column("collect_count", sa.Integer()), sa.Column("comment_count", sa.Integer()), sa.Column("share_count", sa.Integer()), sa.Column("view_count", sa.Integer()), sa.UniqueConstraint("note_id", "snapshot_date", name="uq_xhs_note_snapshot_day"))
    op.create_table("xhs_daily_quotas", *_timestamps(), sa.Column("quota_date", sa.Date(), nullable=False, unique=True), sa.Column("limit_count", sa.Integer(), nullable=False, server_default="100"), sa.Column("used_count", sa.Integer(), nullable=False, server_default="0"), sa.Column("reserved_search_count", sa.Integer(), nullable=False, server_default="0"))
    op.create_table("xhs_image_failure_reports", *_timestamps(), sa.Column("note_id", sa.Integer(), sa.ForeignKey("xhs_notes.id", ondelete="CASCADE"), nullable=False), sa.Column("image_kind", sa.String(20), nullable=False, server_default="cover"), sa.Column("failed_url", sa.String(2000), nullable=False), sa.Column("reporter_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")), sa.Column("failure_count", sa.Integer(), nullable=False, server_default="1"), sa.Column("last_failed_at", sa.DateTime(), nullable=False), sa.Column("status", sa.String(20), nullable=False, server_default="open"), sa.UniqueConstraint("note_id", "image_kind", "failed_url", name="uq_xhs_image_failure"))
    indexes = {"xhs_keywords":["normalized_keyword","keyword_type","schedule_group","enabled","cooldown_until"],"xhs_keyword_runs":["keyword_id","run_date","status"],"xhs_notes":["note_id","published_at","note_type","author_id","like_count","last_discovered_at","detail_status","media_status","quality_status","comprehensive_score","raw_info_id"],"xhs_note_discoveries":["note_id","keyword_id","run_id","provider"],"xhs_provider_calls":["provider","operation","run_id","note_identity","status"],"xhs_engagement_snapshots":["note_id","snapshot_date"],"xhs_daily_quotas":["quota_date"],"xhs_image_failure_reports":["note_id","reporter_user_id","status"]}
    for table, columns in indexes.items():
        for column in columns: op.create_index(f"ix_{table}_{column}", table, [column])
    op.create_index("ix_xhs_notes_public", "xhs_notes", ["quality_status", "published_at", "like_count"])
    _seed_base_keywords()


def downgrade() -> None:
    for table in ["xhs_image_failure_reports","xhs_engagement_snapshots","xhs_note_discoveries","xhs_provider_calls","xhs_daily_quotas","xhs_notes","xhs_keyword_runs","xhs_keywords"]:
        op.drop_table(table)
