"""后台监测模型。"""

from sqlalchemy import Column, DateTime, Integer, String, Text

from app.core.timezone import utcnow
from app.db.base import BaseModel, JSONField


class MonitoringSnapshot(BaseModel):
    """一次后台监测采样结果。"""

    __tablename__ = "monitoring_snapshots"

    level = Column(String(20), nullable=False, index=True)
    message = Column(String(200), nullable=True)
    generated_at = Column(DateTime, default=utcnow, nullable=False, index=True)

    raw_infos_2h = Column(Integer, default=0, nullable=False)
    clusters_24h = Column(Integer, default=0, nullable=False)
    pending_raw_infos = Column(Integer, default=0, nullable=False)
    failed_tasks_24h = Column(Integer, default=0, nullable=False)
    active_users_24h = Column(Integer, default=0, nullable=False)
    low_credit_users = Column(Integer, default=0, nullable=False)

    payload = Column(JSONField, default=dict, nullable=False)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "level": self.level,
            "message": self.message,
            "generated_at": self.generated_at.isoformat() if self.generated_at else None,
            "raw_infos_2h": self.raw_infos_2h,
            "clusters_24h": self.clusters_24h,
            "pending_raw_infos": self.pending_raw_infos,
            "failed_tasks_24h": self.failed_tasks_24h,
            "active_users_24h": self.active_users_24h,
            "low_credit_users": self.low_credit_users,
            "payload": self.payload,
        }


class MonitoringAlert(BaseModel):
    """后台监测告警。"""

    __tablename__ = "monitoring_alerts"

    key = Column(String(80), nullable=False, unique=True, index=True)
    level = Column(String(20), nullable=False, index=True)  # warn / critical
    title = Column(String(120), nullable=False)
    message = Column(Text, nullable=True)
    status = Column(String(20), default="open", nullable=False, index=True)  # open / resolved
    value = Column(Integer, nullable=True)
    threshold = Column(Integer, nullable=True)
    last_triggered_at = Column(DateTime, default=utcnow, nullable=False, index=True)
    resolved_at = Column(DateTime, nullable=True)
    handled_by_user_id = Column(Integer, nullable=True, index=True)
    handled_at = Column(DateTime, nullable=True)
    note = Column(Text, nullable=True)
    payload = Column(JSONField, default=dict, nullable=False)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "key": self.key,
            "level": self.level,
            "title": self.title,
            "message": self.message,
            "status": self.status,
            "value": self.value,
            "threshold": self.threshold,
            "last_triggered_at": self.last_triggered_at.isoformat() if self.last_triggered_at else None,
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
            "handled_by_user_id": self.handled_by_user_id,
            "handled_at": self.handled_at.isoformat() if self.handled_at else None,
            "note": self.note,
            "payload": self.payload,
        }
