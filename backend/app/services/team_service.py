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
    if creation is None or not await is_active_team_user(db, user):
        return False

    if creation.user_id == user.id:
        return True
    if is_admin_user(user):
        return True
    role = (await db.execute(
        select(ArticleMember.role).where(
            ArticleMember.creation_id == creation.id,
            ArticleMember.user_id == user.id,
        )
    )).scalar_one_or_none()
    return role in {"editor", "viewer"}


async def is_active_team_user(db: AsyncSession, user: User) -> bool:
    """员工生命周期的统一守门：离职员工不再拥有团队资源权限。"""
    if not user.is_active:
        return False
    if user.role != "employee":
        return True
    profile_status = (await db.execute(
        select(EmployeeProfile.status).where(EmployeeProfile.user_id == user.id)
    )).scalar_one_or_none()
    return profile_status != "left"


async def can_edit_creation(
    db: AsyncSession,
    user: User,
    creation: Optional[ContentCreation],
) -> bool:
    """判断用户是否可以编辑文章正文/元数据。

    作者和管理员拥有编辑权；共享成员只有 editor 角色可以编辑，viewer 只能读。
    """
    if creation is None or not await can_access_creation(db, user, creation):
        return False
    if creation.user_id == user.id or is_admin_user(user):
        return True
    role = (await db.execute(
        select(ArticleMember.role).where(
            ArticleMember.creation_id == creation.id,
            ArticleMember.user_id == user.id,
        )
    )).scalar_one_or_none()
    return role == "editor"


async def can_publish_creation(
    db: AsyncSession,
    user: User,
    creation: Optional[ContentCreation],
) -> bool:
    """判断用户是否可以改变文章的外部发布状态。

    发布属于高风险状态变更，当前只开放给作者和管理员；editor 仍可编辑内容，
    但不能代替作者完成发布。
    """
    if creation is None or not await can_access_creation(db, user, creation):
        return False
    return creation.user_id == user.id or is_admin_user(user)


async def can_delete_creation(
    db: AsyncSession,
    user: User,
    creation: Optional[ContentCreation],
) -> bool:
    """判断用户是否可以删除文章。删除仍只允许作者和管理员。"""
    if creation is None or not await can_access_creation(db, user, creation):
        return False
    return creation.user_id == user.id or is_admin_user(user)


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
