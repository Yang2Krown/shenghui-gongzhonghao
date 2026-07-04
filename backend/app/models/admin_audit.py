"""管理员操作审计日志。"""

from sqlalchemy import Column, DateTime, Integer, String, Text

from app.core.timezone import utcnow
from app.db.base import BaseModel, JSONField


class AdminAuditLog(BaseModel):
    """后台管理员关键操作记录。"""

    __tablename__ = "admin_audit_logs"

    actor_user_id = Column(Integer, nullable=True, index=True)
    action = Column(String(80), nullable=False, index=True)
    target_type = Column(String(50), nullable=True, index=True)
    target_id = Column(String(100), nullable=True, index=True)
    summary = Column(String(300), nullable=True)
    detail = Column(Text, nullable=True)
    metadata_json = Column(JSONField, default=dict, nullable=False)
    occurred_at = Column(DateTime, default=utcnow, nullable=False, index=True)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "actor_user_id": self.actor_user_id,
            "action": self.action,
            "target_type": self.target_type,
            "target_id": self.target_id,
            "summary": self.summary,
            "detail": self.detail,
            "metadata": self.metadata_json,
            "occurred_at": self.occurred_at.isoformat() if self.occurred_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
