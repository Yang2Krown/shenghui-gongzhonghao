"""系统公告及用户不再提示记录。"""

from sqlalchemy import Boolean, Column, DateTime, Integer, String, Text, UniqueConstraint

from app.core.timezone import utcnow
from app.db.base import BaseModel


class SystemAnnouncement(BaseModel):
    """由最高管理员发布、向已登录用户展示的系统公告。"""

    __tablename__ = "system_announcements"

    title = Column(String(120), nullable=False)
    content = Column(Text, nullable=False)
    is_published = Column(Boolean, default=True, nullable=False, index=True)
    expires_at = Column(DateTime, nullable=False, index=True)
    published_at = Column(DateTime, default=utcnow, nullable=False, index=True)
    created_by_user_id = Column(Integer, nullable=True, index=True)


class SystemAnnouncementDismissal(BaseModel):
    """用户针对单条公告选择“不再提示”的永久记录。"""

    __tablename__ = "system_announcement_dismissals"
    __table_args__ = (UniqueConstraint("announcement_id", "user_id", name="uq_announcement_dismissal_user"),)

    announcement_id = Column(Integer, nullable=False, index=True)
    user_id = Column(Integer, nullable=False, index=True)
    dismissed_at = Column(DateTime, default=utcnow, nullable=False)
