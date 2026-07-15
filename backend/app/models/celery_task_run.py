"""Celery 任务运行记录。

该表只记录任务元数据和生命周期，不保存完整模型输出，避免监控表无限膨胀。
"""

from sqlalchemy import Boolean, Column, Integer, String, Text

from app.db.base import BaseModel, JSONField


class CeleryTaskRun(BaseModel):
    __tablename__ = "celery_task_runs"

    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(String(100), nullable=False, unique=True, index=True)
    task_name = Column(String(255), nullable=False, index=True)
    category = Column(String(30), nullable=False, index=True)
    queue = Column(String(50), nullable=False, default="default", index=True)
    status = Column(String(30), nullable=False, default="waiting", index=True)
    retry_count = Column(Integer, nullable=False, default=0)
    worker = Column(String(255), nullable=True)
    args_json = Column(JSONField, nullable=True)
    kwargs_json = Column(JSONField, nullable=True)
    result_json = Column(JSONField, nullable=True)
    error_message = Column(Text, nullable=True)
    started_at = Column(String(40), nullable=True)
    finished_at = Column(String(40), nullable=True)
    last_seen_at = Column(String(40), nullable=True)
    is_dead_letter = Column(Boolean, nullable=False, default=False, index=True)
    retried_from_id = Column(Integer, nullable=True, index=True)

