"""add resumable article review stages and semantic alignment tables.

Revision ID: 20260812_review_stages
Revises: 20260812_review_async
Create Date: 2026-08-12
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260812_review_stages"
down_revision: Union[str, None] = "20260812_review_async"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _timestamps() -> tuple[sa.Column, sa.Column]:
    return (
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )


def upgrade() -> None:
    op.create_table(
        "article_review_runs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("review_id", sa.Integer(), nullable=False),
        sa.Column("run_id", sa.String(length=100), nullable=False),
        sa.Column("run_no", sa.Integer(), server_default="1", nullable=False),
        sa.Column("status", sa.String(length=20), server_default="queued", nullable=False),
        sa.Column("current_stage", sa.String(length=40), nullable=True),
        sa.Column("requested_stage", sa.String(length=40), nullable=True),
        sa.Column("task_id", sa.String(length=100), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.Column("created_by", sa.Integer(), nullable=True),
        *_timestamps(),
        sa.ForeignKeyConstraint(["review_id"], ["article_reviews.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("run_id", name="uq_article_review_runs_run_id"),
        sa.UniqueConstraint("review_id", "run_no", name="uq_article_review_runs_review_no"),
    )
    op.create_index("ix_article_review_runs_review_id", "article_review_runs", ["review_id"])
    op.create_index("ix_article_review_runs_created_by", "article_review_runs", ["created_by"])
    op.create_index("ix_article_review_runs_review_created_at", "article_review_runs", ["review_id", "created_at"])
    op.create_index("ix_article_review_runs_run_id", "article_review_runs", ["run_id"])

    op.create_table(
        "article_review_stages",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("review_run_id", sa.Integer(), nullable=False),
        sa.Column("stage_key", sa.String(length=40), nullable=False),
        sa.Column("stage_order", sa.Integer(), server_default="1", nullable=False),
        sa.Column("status", sa.String(length=30), server_default="queued", nullable=False),
        sa.Column("progress", sa.Integer(), server_default="0", nullable=False),
        sa.Column("message", sa.String(length=500), nullable=True),
        sa.Column("task_id", sa.String(length=100), nullable=True),
        sa.Column("attempt", sa.Integer(), server_default="0", nullable=False),
        sa.Column("input_hash", sa.String(length=128), nullable=True),
        sa.Column("output", sa.JSON(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        *_timestamps(),
        sa.ForeignKeyConstraint(["review_run_id"], ["article_review_runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("review_run_id", "stage_key", name="uq_article_review_stages_run_stage"),
    )
    op.create_index("ix_article_review_stages_review_run_id", "article_review_stages", ["review_run_id"])
    op.create_index("ix_article_review_stages_status", "article_review_stages", ["status"])

    op.create_table(
        "article_review_semantic_blocks",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("review_id", sa.Integer(), nullable=False),
        sa.Column("review_run_id", sa.Integer(), nullable=False),
        sa.Column("stable_id", sa.String(length=120), nullable=False),
        sa.Column("side", sa.String(length=10), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("normalized_text", sa.Text(), nullable=False),
        sa.Column("start_offset", sa.Integer(), server_default="0", nullable=False),
        sa.Column("end_offset", sa.Integer(), server_default="0", nullable=False),
        sa.Column("source_line_start", sa.Integer(), nullable=True),
        sa.Column("source_line_end", sa.Integer(), nullable=True),
        sa.Column("raw_block_count", sa.Integer(), server_default="1", nullable=False),
        sa.Column("user_edited", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("locked", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=True),
        *_timestamps(),
        sa.ForeignKeyConstraint(["review_id"], ["article_reviews.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["review_run_id"], ["article_review_runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("review_run_id", "stable_id", name="uq_article_review_blocks_run_stable"),
    )
    op.create_index("ix_article_review_semantic_blocks_review_id", "article_review_semantic_blocks", ["review_id"])
    op.create_index("ix_article_review_semantic_blocks_review_run_id", "article_review_semantic_blocks", ["review_run_id"])
    op.create_index("ix_article_review_blocks_review_side_ordinal", "article_review_semantic_blocks", ["review_id", "side", "ordinal"])

    op.create_table(
        "article_review_changes",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("review_id", sa.Integer(), nullable=False),
        sa.Column("review_run_id", sa.Integer(), nullable=False),
        sa.Column("stable_id", sa.String(length=120), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("change_type", sa.String(length=30), nullable=False),
        sa.Column("impact", sa.String(length=20), server_default="low", nullable=False),
        sa.Column("is_major", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("confidence", sa.Float(), server_default="0", nullable=False),
        sa.Column("change_ratio", sa.Float(), server_default="0", nullable=False),
        sa.Column("significance_reason", sa.Text(), nullable=True),
        sa.Column("effect", sa.Text(), nullable=True),
        sa.Column("before_block_ids", sa.JSON(), nullable=False),
        sa.Column("after_block_ids", sa.JSON(), nullable=False),
        sa.Column("before_text", sa.Text(), nullable=True),
        sa.Column("after_text", sa.Text(), nullable=True),
        sa.Column("position_delta", sa.Integer(), nullable=True),
        sa.Column("human_label", sa.String(length=30), nullable=True),
        sa.Column("human_note", sa.Text(), nullable=True),
        sa.Column("ai_analysis", sa.JSON(), nullable=True),
        *_timestamps(),
        sa.ForeignKeyConstraint(["review_id"], ["article_reviews.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["review_run_id"], ["article_review_runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("review_run_id", "stable_id", name="uq_article_review_changes_run_stable"),
    )
    op.create_index("ix_article_review_changes_review_id", "article_review_changes", ["review_id"])
    op.create_index("ix_article_review_changes_review_run_id", "article_review_changes", ["review_run_id"])
    op.create_index("ix_article_review_changes_review_ordinal", "article_review_changes", ["review_id", "ordinal"])
    op.create_index("ix_article_review_changes_type_impact", "article_review_changes", ["change_type", "impact"])

    op.create_table(
        "article_review_reorder_events",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("review_id", sa.Integer(), nullable=False),
        sa.Column("review_run_id", sa.Integer(), nullable=False),
        sa.Column("stable_id", sa.String(length=120), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("before_block_ids", sa.JSON(), nullable=False),
        sa.Column("after_block_ids", sa.JSON(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("confidence", sa.Float(), server_default="0", nullable=False),
        sa.Column("human_label", sa.String(length=30), nullable=True),
        *_timestamps(),
        sa.ForeignKeyConstraint(["review_id"], ["article_reviews.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["review_run_id"], ["article_review_runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("review_run_id", "stable_id", name="uq_article_review_reorder_run_stable"),
    )
    op.create_index("ix_article_review_reorder_events_review_id", "article_review_reorder_events", ["review_id"])
    op.create_index("ix_article_review_reorder_events_review_run_id", "article_review_reorder_events", ["review_run_id"])
    op.create_index("ix_article_review_reorder_review_ordinal", "article_review_reorder_events", ["review_id", "ordinal"])

    op.create_table(
        "article_review_methodology_candidates",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("review_id", sa.Integer(), nullable=False),
        sa.Column("review_run_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("rule", sa.Text(), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=True),
        sa.Column("example", sa.Text(), nullable=True),
        sa.Column("evidence_change_ids", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=20), server_default="candidate", nullable=False),
        sa.Column("confirmed_by", sa.Integer(), nullable=True),
        sa.Column("confirmed_at", sa.DateTime(), nullable=True),
        sa.Column("experience_card_id", sa.Integer(), nullable=True),
        *_timestamps(),
        sa.ForeignKeyConstraint(["review_id"], ["article_reviews.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["review_run_id"], ["article_review_runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["confirmed_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["experience_card_id"], ["experience_cards.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_article_review_methodology_candidates_review_id", "article_review_methodology_candidates", ["review_id"])
    op.create_index("ix_article_review_methodology_candidates_review_run_id", "article_review_methodology_candidates", ["review_run_id"])
    op.create_index("ix_article_review_methodology_review_status", "article_review_methodology_candidates", ["review_id", "status"])
    op.create_index("ix_article_review_methodology_candidates_confirmed_by", "article_review_methodology_candidates", ["confirmed_by"])
    op.create_index("ix_article_review_methodology_candidates_experience_card_id", "article_review_methodology_candidates", ["experience_card_id"])

    op.create_table(
        "article_review_experience_sources",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("experience_card_id", sa.Integer(), nullable=False),
        sa.Column("review_id", sa.Integer(), nullable=False),
        sa.Column("review_run_id", sa.Integer(), nullable=True),
        sa.Column("change_id", sa.Integer(), nullable=True),
        sa.Column("comment_ids", sa.JSON(), nullable=False),
        sa.Column("confirmed_conclusion", sa.Text(), nullable=True),
        sa.Column("confirmed_by", sa.Integer(), nullable=True),
        sa.Column("confirmed_at", sa.DateTime(), nullable=True),
        *_timestamps(),
        sa.ForeignKeyConstraint(["experience_card_id"], ["experience_cards.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["review_id"], ["article_reviews.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["review_run_id"], ["article_review_runs.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["change_id"], ["article_review_changes.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["confirmed_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_article_review_experience_sources_experience_card_id", "article_review_experience_sources", ["experience_card_id"])
    op.create_index("ix_article_review_experience_sources_review_id", "article_review_experience_sources", ["review_id"])
    op.create_index("ix_article_review_experience_sources_review_run_id", "article_review_experience_sources", ["review_run_id"])
    op.create_index("ix_article_review_experience_sources_change_id", "article_review_experience_sources", ["change_id"])
    op.create_index("ix_article_review_experience_sources_confirmed_by", "article_review_experience_sources", ["confirmed_by"])

    op.add_column(
        "article_review_comments",
        sa.Column("change_id", sa.Integer(), nullable=True),
    )
    op.add_column(
        "article_review_comments",
        sa.Column("semantic_block_id", sa.Integer(), nullable=True),
    )
    op.add_column(
        "article_review_comments",
        sa.Column("edit_status", sa.String(length=20), server_default="active", nullable=False),
    )
    op.add_column(
        "article_review_comments",
        sa.Column("processing_status", sa.String(length=20), server_default="open", nullable=False),
    )
    op.add_column("article_review_comments", sa.Column("edited_at", sa.DateTime(), nullable=True))
    op.create_foreign_key(
        "fk_article_review_comments_change_id",
        "article_review_comments",
        "article_review_changes",
        ["change_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_article_review_comments_semantic_block_id",
        "article_review_comments",
        "article_review_semantic_blocks",
        ["semantic_block_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_article_review_comments_change_id", "article_review_comments", ["change_id"])
    op.create_index("ix_article_review_comments_semantic_block_id", "article_review_comments", ["semantic_block_id"])

    # 为迁移前已经存在的文章复盘建立一个 legacy run，使旧记录可以进入新的工作流视图。
    op.execute(
        sa.text(
            """
            INSERT INTO article_review_runs
                (review_id, run_id, run_no, status, current_stage, created_by, created_at, updated_at)
            SELECT
                ar.id,
                COALESCE(ar.progress_run_id, 'legacy-review-' || CAST(ar.id AS VARCHAR(80))),
                1,
                CASE WHEN ar.status = 'failed' THEN 'failed'
                     WHEN ar.status = 'reviewing' THEN 'succeeded'
                     ELSE 'queued' END,
                CASE WHEN ar.status = 'failed' THEN 'ai_review'
                     WHEN ar.status = 'reviewing' THEN 'ai_review'
                     WHEN ar.before_text <> '' AND ar.after_text <> '' THEN 'semantic_alignment'
                     ELSE 'parse' END,
                ar.created_by,
                ar.created_at,
                ar.updated_at
            FROM article_reviews ar
            WHERE NOT EXISTS (
                SELECT 1 FROM article_review_runs rr WHERE rr.review_id = ar.id
            )
            """
        )
    )
    # 旧记录没有规范化语义块，但仍补齐阶段状态，确保详情页可以说明
    # 哪些结果来自旧版、哪些阶段可以从当前记录继续重跑。
    op.execute(
        sa.text(
            """
            INSERT INTO article_review_stages
                (review_run_id, stage_key, stage_order, status, progress, message, created_at, updated_at)
            SELECT rr.id, 'parse', 1,
                CASE WHEN ar.before_text <> '' AND ar.after_text <> '' THEN 'succeeded' ELSE 'queued' END,
                CASE WHEN ar.before_text <> '' AND ar.after_text <> '' THEN 100 ELSE 0 END,
                '迁移自旧版文章复盘', ar.created_at, ar.updated_at
            FROM article_review_runs rr
            JOIN article_reviews ar ON ar.id = rr.review_id
            WHERE NOT EXISTS (
                SELECT 1 FROM article_review_stages st
                WHERE st.review_run_id = rr.id AND st.stage_key = 'parse'
            );

            INSERT INTO article_review_stages
                (review_run_id, stage_key, stage_order, status, progress, message, created_at, updated_at)
            SELECT rr.id, 'semantic_segmentation', 2,
                CASE WHEN ar.before_text <> '' AND ar.after_text <> '' THEN 'succeeded' ELSE 'blocked' END,
                CASE WHEN ar.before_text <> '' AND ar.after_text <> '' THEN 100 ELSE 0 END,
                '旧版分段结果仅保留兼容投影，确认后可重新生成语义块', ar.created_at, ar.updated_at
            FROM article_review_runs rr
            JOIN article_reviews ar ON ar.id = rr.review_id
            WHERE NOT EXISTS (
                SELECT 1 FROM article_review_stages st
                WHERE st.review_run_id = rr.id AND st.stage_key = 'semantic_segmentation'
            );

            INSERT INTO article_review_stages
                (review_run_id, stage_key, stage_order, status, progress, message, created_at, updated_at)
            SELECT rr.id, 'semantic_alignment', 3,
                CASE WHEN COALESCE(ar.change_groups::text, '[]') <> '[]' THEN 'succeeded' ELSE 'blocked' END,
                CASE WHEN COALESCE(ar.change_groups::text, '[]') <> '[]' THEN 100 ELSE 0 END,
                '旧版差异保留在兼容字段中', ar.created_at, ar.updated_at
            FROM article_review_runs rr
            JOIN article_reviews ar ON ar.id = rr.review_id
            WHERE NOT EXISTS (
                SELECT 1 FROM article_review_stages st
                WHERE st.review_run_id = rr.id AND st.stage_key = 'semantic_alignment'
            );

            INSERT INTO article_review_stages
                (review_run_id, stage_key, stage_order, status, progress, message, created_at, updated_at)
            SELECT rr.id, 'ai_review', 4,
                CASE WHEN ar.status = 'reviewing' THEN 'succeeded'
                     WHEN ar.status = 'failed' THEN 'failed'
                     ELSE 'blocked' END,
                CASE WHEN ar.status IN ('reviewing', 'failed') THEN 100 ELSE 0 END,
                '旧版 AI 复盘结果保留在兼容字段中', ar.created_at, ar.updated_at
            FROM article_review_runs rr
            JOIN article_reviews ar ON ar.id = rr.review_id
            WHERE NOT EXISTS (
                SELECT 1 FROM article_review_stages st
                WHERE st.review_run_id = rr.id AND st.stage_key = 'ai_review'
            );

            INSERT INTO article_review_stages
                (review_run_id, stage_key, stage_order, status, progress, message, created_at, updated_at)
            SELECT rr.id, 'methodology', 5,
                CASE WHEN ar.status = 'reviewing' THEN 'succeeded' ELSE 'blocked' END,
                CASE WHEN ar.status = 'reviewing' THEN 100 ELSE 0 END,
                '旧版方法论保留在 AI 结果中', ar.created_at, ar.updated_at
            FROM article_review_runs rr
            JOIN article_reviews ar ON ar.id = rr.review_id
            WHERE NOT EXISTS (
                SELECT 1 FROM article_review_stages st
                WHERE st.review_run_id = rr.id AND st.stage_key = 'methodology'
            )
            """
        )
    )


def downgrade() -> None:
    op.drop_index("ix_article_review_comments_semantic_block_id", table_name="article_review_comments")
    op.drop_index("ix_article_review_comments_change_id", table_name="article_review_comments")
    op.drop_constraint("fk_article_review_comments_semantic_block_id", "article_review_comments", type_="foreignkey")
    op.drop_constraint("fk_article_review_comments_change_id", "article_review_comments", type_="foreignkey")
    op.drop_column("article_review_comments", "edited_at")
    op.drop_column("article_review_comments", "processing_status")
    op.drop_column("article_review_comments", "edit_status")
    op.drop_column("article_review_comments", "semantic_block_id")
    op.drop_column("article_review_comments", "change_id")

    op.drop_index("ix_article_review_experience_sources_confirmed_by", table_name="article_review_experience_sources")
    op.drop_index("ix_article_review_experience_sources_change_id", table_name="article_review_experience_sources")
    op.drop_index("ix_article_review_experience_sources_review_run_id", table_name="article_review_experience_sources")
    op.drop_index("ix_article_review_experience_sources_review_id", table_name="article_review_experience_sources")
    op.drop_index("ix_article_review_experience_sources_experience_card_id", table_name="article_review_experience_sources")
    op.drop_table("article_review_experience_sources")

    op.drop_index("ix_article_review_methodology_candidates_experience_card_id", table_name="article_review_methodology_candidates")
    op.drop_index("ix_article_review_methodology_candidates_confirmed_by", table_name="article_review_methodology_candidates")
    op.drop_index("ix_article_review_methodology_review_status", table_name="article_review_methodology_candidates")
    op.drop_index("ix_article_review_methodology_candidates_review_run_id", table_name="article_review_methodology_candidates")
    op.drop_index("ix_article_review_methodology_candidates_review_id", table_name="article_review_methodology_candidates")
    op.drop_table("article_review_methodology_candidates")

    op.drop_index("ix_article_review_reorder_review_ordinal", table_name="article_review_reorder_events")
    op.drop_index("ix_article_review_reorder_events_review_run_id", table_name="article_review_reorder_events")
    op.drop_index("ix_article_review_reorder_events_review_id", table_name="article_review_reorder_events")
    op.drop_table("article_review_reorder_events")

    op.drop_index("ix_article_review_changes_type_impact", table_name="article_review_changes")
    op.drop_index("ix_article_review_changes_review_ordinal", table_name="article_review_changes")
    op.drop_index("ix_article_review_changes_review_run_id", table_name="article_review_changes")
    op.drop_index("ix_article_review_changes_review_id", table_name="article_review_changes")
    op.drop_table("article_review_changes")

    op.drop_index("ix_article_review_blocks_review_side_ordinal", table_name="article_review_semantic_blocks")
    op.drop_index("ix_article_review_semantic_blocks_review_run_id", table_name="article_review_semantic_blocks")
    op.drop_index("ix_article_review_semantic_blocks_review_id", table_name="article_review_semantic_blocks")
    op.drop_table("article_review_semantic_blocks")

    op.drop_index("ix_article_review_stages_status", table_name="article_review_stages")
    op.drop_index("ix_article_review_stages_review_run_id", table_name="article_review_stages")
    op.drop_table("article_review_stages")

    op.drop_index("ix_article_review_runs_run_id", table_name="article_review_runs")
    op.drop_index("ix_article_review_runs_review_created_at", table_name="article_review_runs")
    op.drop_index("ix_article_review_runs_created_by", table_name="article_review_runs")
    op.drop_index("ix_article_review_runs_review_id", table_name="article_review_runs")
    op.drop_table("article_review_runs")
