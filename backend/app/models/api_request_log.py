"""API 请求监测日志。"""

from sqlalchemy import Column, DateTime, Float, Integer, String

from app.core.timezone import utcnow
from app.db.base import BaseModel


class ApiRequestLog(BaseModel):
    """后台接口健康监测的轻量请求日志。"""

    __tablename__ = "api_request_logs"

    method = Column(String(10), nullable=False, index=True)
    path = Column(String(500), nullable=False, index=True)
    status_code = Column(Integer, nullable=False, index=True)
    duration_ms = Column(Float, nullable=False, default=0)
    user_id = Column(Integer, nullable=True, index=True)
    created_at = Column(DateTime, default=utcnow, nullable=False, index=True)
