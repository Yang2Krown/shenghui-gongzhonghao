"""团队协作服务（P0）：员工档案、文章共享访问控制。"""
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.product_access import is_admin_user
from app.models.article_member import ArticleMember
from app.models.creation import ContentCreation
from app.models.employee_profile import EmployeeProfile
from app.models.user import User


async def can_access_creation(
    db: AsyncSession,
    user: User,
    creation: Optional[ContentCreation],
) -> bool:
    """文章访问控制：
    - 作者本人；
    - 管理员/超管；
    - 被作者显式共享的成员（article_members）。
    员工默认不自动获得他人文章访问权，需要作者分享。
    """
    if creation is None:
        return False
    if creation.user_id == user.id:
        return True
    if is_admin_user(user):
        return True
    row = (await db.execute(
        select(ArticleMember.id).where(
            ArticleMember.creation_id == creation.id,
            ArticleMember.user_id == user.id,
        )
    )).scalars().first()
    return row is not None


async def get_or_create_employee_profile(
    db: AsyncSession,
    user_id: int,
    *,
    department: Optional[str] = None,
    position: Optional[str] = None,
) -> EmployeeProfile:
    profile = (await db.execute(
        select(EmployeeProfile).where(EmployeeProfile.user_id == user_id)
    )).scalars().first()
    if profile is None:
        profile = EmployeeProfile(user_id=user_id, department=department, position=position)
        db.add(profile)
        await db.flush()
    return profile
