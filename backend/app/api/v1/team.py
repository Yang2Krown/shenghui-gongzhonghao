"""团队协作 API（P0）：成员角色赋予、员工档案、文章共享。"""
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import delete, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.product_access import is_admin_user, is_employee_user
from app.core.security import get_current_user
from app.db.session import get_db
from app.models.admin_audit import AdminAuditLog
from app.models.article_member import ArticleMember
from app.models.creation import ContentCreation
from app.models.employee_profile import EmployeeProfile
from app.models.user import User
from app.schemas.team import (
    CreationMemberOut,
    RoleUpdateRequest,
    ShareCreationRequest,
    TeamMemberOut,
    TeamMemberUpdateRequest,
)
from app.services.team_service import (
    get_or_create_employee_profile,
)

router = APIRouter()


def _mask_phone(phone: Optional[str]) -> Optional[str]:
    if not phone or len(phone) < 7:
        return phone
    return f"{phone[:3]}****{phone[-4:]}"


def _member_payload(user: User, profile: Optional[EmployeeProfile]) -> dict:
    return TeamMemberOut(
        user_id=user.id,
        username=user.username,
        phone_masked=_mask_phone(user.phone),
        full_name=user.full_name,
        avatar_url=user.avatar_url,
        role=user.role,
        is_superuser=user.is_superuser,
        is_active=user.is_active,
        department=profile.department if profile else None,
        position=profile.position if profile else None,
        employee_no=profile.employee_no if profile else None,
        joined_at=profile.joined_at if profile else None,
        employee_status=profile.status if profile else None,
        created_at=user.created_at,
    ).dict()


def _require_team_admin(user: User) -> None:
    if not is_admin_user(user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="仅管理员可执行此操作")


def _require_team_member(user: User) -> None:
    if not (is_admin_user(user) or is_employee_user(user)):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="仅团队成员可访问")


def _audit(
    db: AsyncSession,
    *,
    actor_user_id: int,
    action: str,
    target_type: str,
    target_id: str,
    summary: str,
    metadata_json: Optional[dict] = None,
) -> None:
    db.add(AdminAuditLog(
        actor_user_id=actor_user_id,
        action=action,
        target_type=target_type,
        target_id=target_id,
        summary=summary[:300],
        metadata_json=metadata_json or {},
    ))


async def _get_creation_or_404(db: AsyncSession, creation_id: int) -> ContentCreation:
    creation = (await db.execute(
        select(ContentCreation).where(ContentCreation.id == creation_id)
    )).scalars().first()
    if creation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="创作不存在")
    return creation


# ── 成员 ──────────────────────────────────────────────────

@router.get("/users/search", response_model=dict)
async def search_team_candidates(
    keyword: str = Query(..., min_length=1, max_length=50, description="用户名/姓名/手机号关键词"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    """管理员按关键词搜索用户，用于直接赋予员工角色。"""
    _require_team_admin(current_user)
    like = f"%{keyword.strip()}%"
    rows = (await db.execute(
        select(User)
        .where(
            User.is_active.is_(True),
            or_(User.username.ilike(like), User.full_name.ilike(like), User.phone.ilike(like)),
        )
        .order_by(User.id.asc())
        .limit(20)
    )).scalars().all()
    items = [
        {
            "user_id": u.id,
            "username": u.username,
            "full_name": u.full_name,
            "phone_masked": _mask_phone(u.phone),
            "role": u.role,
            "is_superuser": u.is_superuser,
        }
        for u in rows
    ]
    return {"code": 200, "message": "用户搜索成功", "data": {"items": items}}


@router.put("/members/{user_id}/role", response_model=dict)
async def update_member_role(
    user_id: int,
    req: RoleUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    """管理员直接赋予/取消员工角色（employee / user）。"""
    _require_team_admin(current_user)
    target = (await db.execute(select(User).where(User.id == user_id))).scalars().first()
    if target is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用户不存在")
    if target.phone == settings.SUPER_ADMIN_PHONE:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="不能修改最高管理员角色")
    if target.is_superuser:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="不能修改最高管理员角色")
    before = target.role
    if req.role == "employee":
        profile = await get_or_create_employee_profile(db, target.id)
        profile.status = "active"
    target.role = req.role
    if req.role == "user":
        # 角色撤销必须同时清理文章共享关系，避免用户降级后仍凭旧 member
        # 记录访问团队内容。
        await db.execute(delete(ArticleMember).where(ArticleMember.user_id == target.id))
    _audit(
        db,
        actor_user_id=current_user.id,
        action="team.member.role.update",
        target_type="user",
        target_id=str(target.id),
        summary=f"角色变更 {before or 'user'} → {req.role}：{target.full_name or target.username}",
        metadata_json={"before": before, "after": req.role},
    )
    await db.commit()
    await db.refresh(target)
    return {
        "code": 200,
        "message": "角色已更新",
        "data": {"user_id": target.id, "role": target.role},
    }

@router.get("/members", response_model=dict)
async def list_team_members(
    keyword: Optional[str] = Query(None, max_length=50),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    """团队成员列表（管理员/员工可看）。"""
    _require_team_member(current_user)
    stmt = (
        select(User, EmployeeProfile)
        .outerjoin(EmployeeProfile, EmployeeProfile.user_id == User.id)
        .where(or_(User.role.in_(["admin", "employee"]), User.is_superuser.is_(True)))
        .order_by(User.is_superuser.desc(), User.role.asc(), User.id.asc())
    )
    if keyword:
        like = f"%{keyword}%"
        stmt = stmt.where(or_(User.username.ilike(like), User.full_name.ilike(like), User.phone.ilike(like)))
    rows = (await db.execute(stmt)).all()
    items = [_member_payload(user, profile) for user, profile in rows]
    return {
        "code": 200,
        "message": "团队成员获取成功",
        "data": {"items": items, "total": len(items)},
    }


@router.put("/members/{user_id}", response_model=dict)
async def update_team_member(
    user_id: int,
    req: TeamMemberUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    """管理员更新员工档案（部门/岗位/工号/状态等）。"""
    _require_team_admin(current_user)
    target = (await db.execute(select(User).where(User.id == user_id))).scalars().first()
    if target is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用户不存在")
    profile = await get_or_create_employee_profile(db, target.id)
    fields = {
        "department": req.department,
        "position": req.position,
        "employee_no": req.employee_no,
        "joined_at": req.joined_at,
        "status": req.status,
    }
    changed = {}
    for field, value in fields.items():
        if value is not None and getattr(profile, field) != value:
            setattr(profile, field, value)
            changed[field] = value

    if req.status == "left" and target.role == "employee":
        target.role = "user"
        changed["role"] = "user"
        await db.execute(delete(ArticleMember).where(ArticleMember.user_id == target.id))
    _audit(
        db,
        actor_user_id=current_user.id,
        action="team.member.update",
        target_type="user",
        target_id=str(target.id),
        summary=f"更新员工档案 {target.full_name or target.username}",
        metadata_json={"changed": changed},
    )
    await db.commit()
    return {
        "code": 200,
        "message": "员工档案已更新",
        "data": _member_payload(target, profile),
    }


# ── 文章共享 ──────────────────────────────────────────────

async def _ensure_share_permission(
    db: AsyncSession,
    current_user: User,
    creation: ContentCreation,
) -> None:
    if creation.user_id != current_user.id and not is_admin_user(current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="仅作者或管理员可管理共享")


@router.post("/creations/{creation_id}/share", response_model=dict)
async def share_creation(
    creation_id: int,
    req: ShareCreationRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    """把创作共享给团队成员（editor/viewer）。"""
    creation = await _get_creation_or_404(db, creation_id)
    await _ensure_share_permission(db, current_user, creation)
    if req.user_id == creation.user_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="作者无需共享给自己")
    target = (await db.execute(select(User).where(User.id == req.user_id))).scalars().first()
    if target is None or not target.is_active:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="目标用户不存在或已禁用")
    if not (is_admin_user(target) or is_employee_user(target)):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="仅可共享给团队成员")
    if target.role == "employee":
        target_profile_status = (await db.execute(
            select(EmployeeProfile.status).where(EmployeeProfile.user_id == target.id)
        )).scalar_one_or_none()
        if target_profile_status == "left":
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="不能共享给已离职员工")
    member = (await db.execute(
        select(ArticleMember).where(
            ArticleMember.creation_id == creation.id,
            ArticleMember.user_id == req.user_id,
        )
    )).scalars().first()
    if member is None:
        member = ArticleMember(
            creation_id=creation.id,
            user_id=req.user_id,
            role=req.role,
            granted_by=current_user.id,
        )
        db.add(member)
    else:
        member.role = req.role
    await db.commit()
    await db.refresh(member)
    return {
        "code": 200,
        "message": "共享已更新",
        "data": {
            "creation_id": creation.id,
            "user_id": member.user_id,
            "role": member.role,
        },
    }


@router.delete("/creations/{creation_id}/share/{user_id}", response_model=dict)
async def unshare_creation(
    creation_id: int,
    user_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    """取消共享。"""
    creation = await _get_creation_or_404(db, creation_id)
    await _ensure_share_permission(db, current_user, creation)
    member = (await db.execute(
        select(ArticleMember).where(
            ArticleMember.creation_id == creation.id,
            ArticleMember.user_id == user_id,
        )
    )).scalars().first()
    if member is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="该成员未被共享")
    await db.delete(member)
    await db.commit()
    return {"code": 200, "message": "已取消共享"}


@router.get("/creations/{creation_id}/members", response_model=dict)
async def list_creation_members(
    creation_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    """查看创作的共享成员。"""
    creation = await _get_creation_or_404(db, creation_id)
    await _ensure_share_permission(db, current_user, creation)
    rows = (
        await db.execute(
            select(ArticleMember, User)
            .join(User, User.id == ArticleMember.user_id)
            .where(ArticleMember.creation_id == creation.id)
            .order_by(ArticleMember.created_at.asc())
        )
    ).all()
    items = [
        CreationMemberOut(
            user_id=member.user_id,
            username=user.username,
            full_name=user.full_name,
            avatar_url=user.avatar_url,
            role=member.role,
            granted_by=member.granted_by,
            created_at=member.created_at,
        ).dict()
        for member, user in rows
    ]
    return {"code": 200, "message": "共享成员获取成功", "data": {"items": items}}
