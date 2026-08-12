"""remove user-generated adhoc content from the public topic library

Revision ID: 20260715_remove_adhoc_topics
Revises: 20260715_celery_task_runs
Create Date: 2026-07-15
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260715_remove_adhoc_topics"
down_revision: Union[str, None] = "20260715_celery_task_runs"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Delete only user-input topic clusters; keep candidates and creations usable."""
    # 先保存受影响的簇 ID。只按 adhoc_input 来源识别，不碰定时抓取的数据。
    op.execute(sa.text(
        """
        CREATE TEMPORARY TABLE _user_adhoc_cluster_ids AS
        SELECT DISTINCT r.info_cluster_id AS id
        FROM raw_infos r
        JOIN source_registry s ON s.id = r.source_registry_id
        WHERE s.platform = 'adhoc_input'
          AND r.info_cluster_id IS NOT NULL
        """
    ))

    # 保留用户自己的候选、大纲、草稿，只解除它们对即将删除信息簇的引用。
    op.execute(sa.text(
        """
        UPDATE topic_candidates
        SET info_cluster_id = NULL
        WHERE info_cluster_id IN (SELECT id FROM _user_adhoc_cluster_ids)
        """
    ))
    op.execute(sa.text(
        """
        UPDATE content_creations
        SET cluster_id = NULL
        WHERE cluster_id IN (SELECT id FROM _user_adhoc_cluster_ids)
        """
    ))

    op.execute(sa.text(
        """
        DELETE FROM raw_infos
        WHERE source_registry_id IN (
            SELECT id FROM source_registry WHERE platform = 'adhoc_input'
        )
        """
    ))
    op.execute(sa.text(
        """
        DELETE FROM info_clusters
        WHERE id IN (SELECT id FROM _user_adhoc_cluster_ids)
        """
    ))
    op.execute(sa.text("DROP TABLE _user_adhoc_cluster_ids"))


def downgrade() -> None:
    # 历史用户输入数据是误入公共库的脏数据，不恢复。
    pass
