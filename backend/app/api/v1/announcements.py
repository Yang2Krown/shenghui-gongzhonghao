"""面向已登录用户的系统公告接口。"""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_active_user
from app.core.timezone import utcnow
from app.db.session import get_db
from app.models.system_announcement import SystemAnnouncement, SystemAnnouncementDismissal
from app.models.user import User

router = APIRouter()


class AnnouncementDismissRequest(BaseModel):
    announcement_id: int


def _announcement_payload(row: SystemAnnouncement) -> dict:
    return {"id": row.id, "title": row.title, "content": row.content, "published_at": row.published_at.isoformat() if row.published_at else None, "expires_at": row.expires_at.isoformat() if row.expires_at else None}


@router.get("/active", response_model=dict)
async def list_active_announcements(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)) -> dict:
    """读取当前用户尚未选择“不再提示”的有效公告。"""
    now = utcnow()
    dismissed = select(SystemAnnouncementDismissal.announcement_id).where(SystemAnnouncementDismissal.user_id == current_user.id)
    rows = (await db.execute(select(SystemAnnouncement).where(
        SystemAnnouncement.is_published.is_(True), SystemAnnouncement.published_at <= now,
        SystemAnnouncement.expires_at > now, SystemAnnouncement.id.not_in(dismissed),
    ).order_by(SystemAnnouncement.published_at.asc(), SystemAnnouncement.id.asc()))).scalars().all()
    return {"code": 200, "message": "获取系统公告成功", "data": {"items": [_announcement_payload(row) for row in rows]}}


@router.post("/dismiss", response_model=dict)
async def dismiss_announcement(req: AnnouncementDismissRequest, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)) -> dict:
    """记录用户对公告的“不再提示”；确认收到不调用此接口。"""
    announcement = await db.get(SystemAnnouncement, req.announcement_id)
    now = utcnow()
    if not announcement or not announcement.is_published or announcement.published_at > now or announcement.expires_at <= now:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="公告不存在或已过期")
    exists = (await db.execute(select(SystemAnnouncementDismissal).where(SystemAnnouncementDismissal.announcement_id == announcement.id, SystemAnnouncementDismissal.user_id == current_user.id))).scalar_one_or_none()
    if not exists:
        db.add(SystemAnnouncementDismissal(announcement_id=announcement.id, user_id=current_user.id, dismissed_at=now))
        await db.commit()
    return {"code": 200, "message": "已设置为不再提示", "data": {"announcement_id": announcement.id}}
