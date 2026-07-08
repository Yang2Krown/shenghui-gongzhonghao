"""管理员后台 API。"""

from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_super_admin_user
from app.core.admin_permissions import ADMIN_ROLES, allowed_roles_text, require_admin_permission
from app.core.config import settings
from app.core.timezone import utcnow
from app.db.session import get_db
from app.models.admin_audit import AdminAuditLog
from app.models.credit import UserCredit
from app.models.llm_monitoring import LlmModelPricing
from app.models.monitoring import MonitoringAlert, MonitoringSnapshot
from app.models.task import Task, TaskStatus
from app.models.user import User
from app.services.monitoring.checks import build_alert_specs, collect_admin_monitoring
from app.services.monitoring.modules import collect_ai_costs, collect_api_health, collect_source_health, collect_user_stats
from app.services.monitoring.security_health import collect_security_health
from app.services.llm.cost_guard import collect_llm_guard_status

router = APIRouter()


class AdminGrantRequest(BaseModel):
    phone: str = Field(..., min_length=6, max_length=20, description="用户手机号")
    is_admin: bool = Field(True, description="true=设为管理员，false=取消管理员")
    role: Optional[str] = Field(
        None,
        description="细分后台角色：admin/ops/support/finance/auditor；为空时兼容 is_admin",
    )


class AlertUpdateRequest(BaseModel):
    note: Optional[str] = Field(None, max_length=1000, description="处理备注")
    resolve: bool = Field(False, description="是否手动标记已恢复")


class UserStatusUpdateRequest(BaseModel):
    is_active: bool = Field(..., description="true=启用用户，false=禁用用户")
    reason: Optional[str] = Field(None, max_length=1000, description="操作原因")


class UserMembershipUpdateRequest(BaseModel):
    is_member: bool = Field(..., description="true=设为会员，false=取消会员")
    reason: Optional[str] = Field(None, max_length=1000, description="操作原因")


class LlmPricingRequest(BaseModel):
    provider: str = Field(..., min_length=1, max_length=50)
    model: str = Field(..., min_length=1, max_length=120)
    display_name: Optional[str] = Field(None, max_length=160)
    input_price_per_million: float = Field(..., ge=0)
    output_price_per_million: float = Field(..., ge=0)
    currency: str = Field("CNY", min_length=1, max_length=10)
    enabled: bool = True
    note: Optional[str] = Field(None, max_length=1000)


class LlmPricingUpdateRequest(BaseModel):
    display_name: Optional[str] = Field(None, max_length=160)
    input_price_per_million: Optional[float] = Field(None, ge=0)
    output_price_per_million: Optional[float] = Field(None, ge=0)
    currency: Optional[str] = Field(None, min_length=1, max_length=10)
    enabled: Optional[bool] = None
    note: Optional[str] = Field(None, max_length=1000)


def _mask_phone(phone: Optional[str]) -> Optional[str]:
    if not phone or len(phone) < 7:
        return phone
    return f"{phone[:3]}****{phone[-4:]}"


def _user_payload(user: User) -> dict:
    return {
        "id": user.id,
        "username": user.username,
        "phone": _mask_phone(user.phone),
        "email": user.email,
        "full_name": user.full_name,
        "role": user.role,
        "is_superuser": user.is_superuser,
        "is_active": user.is_active,
        "is_member": user.is_member,
        "member_since": user.member_since.isoformat() if user.member_since else None,
        "created_at": user.created_at.isoformat() if user.created_at else None,
        "last_login": user.last_login.isoformat() if user.last_login else None,
    }


def _snapshot_payload(snapshot: MonitoringSnapshot) -> dict:
    return {
        "id": snapshot.id,
        "level": snapshot.level,
        "message": snapshot.message,
        "generated_at": snapshot.generated_at.isoformat() if snapshot.generated_at else None,
        "raw_infos_2h": snapshot.raw_infos_2h,
        "clusters_24h": snapshot.clusters_24h,
        "pending_raw_infos": snapshot.pending_raw_infos,
        "failed_tasks_24h": snapshot.failed_tasks_24h,
        "active_users_24h": snapshot.active_users_24h,
        "low_credit_users": snapshot.low_credit_users,
    }


def _task_payload(task: Task) -> dict:
    return {
        "id": task.id,
        "title": task.title,
        "description": task.description,
        "status": task.status.value if hasattr(task.status, "value") else str(task.status),
        "error_message": task.error_message,
        "created_at": task.created_at.isoformat() if task.created_at else None,
        "updated_at": task.updated_at.isoformat() if task.updated_at else None,
        "started_at": task.started_at.isoformat() if task.started_at else None,
        "completed_at": task.completed_at.isoformat() if task.completed_at else None,
    }


def _alert_payload(alert: MonitoringAlert) -> dict:
    return {
        "id": alert.id,
        "key": alert.key,
        "level": alert.level,
        "title": alert.title,
        "message": alert.message,
        "status": alert.status,
        "value": alert.value,
        "threshold": alert.threshold,
        "last_triggered_at": alert.last_triggered_at.isoformat() if alert.last_triggered_at else None,
        "resolved_at": alert.resolved_at.isoformat() if alert.resolved_at else None,
        "handled_by_user_id": alert.handled_by_user_id,
        "handled_at": alert.handled_at.isoformat() if alert.handled_at else None,
        "note": alert.note,
    }


def _audit_payload(log: AdminAuditLog) -> dict:
    return log.to_dict()


def _public_alert_spec(spec: dict) -> dict:
    """前端当前告警只需要展示字段，不能返回内部 payload，避免循环引用。"""
    return {key: value for key, value in spec.items() if key != "payload"}


def _request_metadata(request: Request) -> dict:
    forwarded_for = request.headers.get("x-forwarded-for")
    ip = forwarded_for.split(",", 1)[0].strip() if forwarded_for else None
    if not ip and request.client:
        ip = request.client.host
    return {
        "ip": ip,
        "user_agent": request.headers.get("user-agent"),
    }


def _add_audit_log(
    db: AsyncSession,
    *,
    actor_user_id: Optional[int],
    action: str,
    target_type: Optional[str] = None,
    target_id: Optional[str] = None,
    summary: Optional[str] = None,
    detail: Optional[str] = None,
    metadata: Optional[dict] = None,
) -> AdminAuditLog:
    log = AdminAuditLog(
        actor_user_id=actor_user_id,
        action=action,
        target_type=target_type,
        target_id=target_id,
        summary=summary,
        detail=detail,
        metadata_json=metadata or {},
        occurred_at=utcnow(),
    )
    db.add(log)
    return log


@router.get("/monitoring/overview", response_model=dict)
async def monitoring_overview(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin_permission("monitoring:read")),
) -> Any:
    """管理员后台监测总览。"""
    data = await collect_admin_monitoring(db)
    data["current_alerts"] = [_public_alert_spec(spec) for spec in build_alert_specs(data)]
    return {"code": 200, "message": "获取监测数据成功", "data": data}


@router.get("/monitoring/source-health", response_model=dict)
async def monitoring_source_health(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin_permission("monitoring:read")),
) -> Any:
    """数据源健康独立监测。"""
    data = await collect_source_health(db)
    return {"code": 200, "message": "获取数据源健康成功", "data": data}


@router.get("/monitoring/ai-costs", response_model=dict)
async def monitoring_ai_costs(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin_permission("payments:read")),
) -> Any:
    """AI 调用成本独立监测。"""
    data = await collect_ai_costs(db)
    return {"code": 200, "message": "获取 AI 成本监测成功", "data": data}


@router.post("/monitoring/ai-costs/pricing", response_model=dict)
async def create_llm_pricing(
    req: LlmPricingRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin_permission("pricing:write")),
) -> Any:
    """新增模型单价配置。"""
    exists = (await db.execute(
        select(LlmModelPricing).where(
            LlmModelPricing.provider == req.provider,
            LlmModelPricing.model == req.model,
        )
    )).scalar_one_or_none()
    if exists:
        raise HTTPException(status_code=400, detail="该 provider/model 已存在")
    row = LlmModelPricing(**req.model_dump())
    db.add(row)
    _add_audit_log(
        db,
        actor_user_id=current_user.id,
        action="llm_pricing.create",
        target_type="llm_model_pricing",
        summary=f"新增模型单价 {req.provider}/{req.model}",
        metadata={**req.model_dump(), **_request_metadata(request)},
    )
    await db.commit()
    await db.refresh(row)
    return {"code": 200, "message": "新增模型单价成功", "data": {"id": row.id}}


@router.patch("/monitoring/ai-costs/pricing/{pricing_id}", response_model=dict)
async def update_llm_pricing(
    pricing_id: int,
    req: LlmPricingUpdateRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin_permission("pricing:write")),
) -> Any:
    """修改模型单价配置。"""
    row = await db.get(LlmModelPricing, pricing_id)
    if not row:
        raise HTTPException(status_code=404, detail="模型单价配置不存在")
    before = {
        "input_price_per_million": float(row.input_price_per_million or 0),
        "output_price_per_million": float(row.output_price_per_million or 0),
        "enabled": row.enabled,
    }
    for key, value in req.model_dump(exclude_unset=True).items():
        setattr(row, key, value)
    row.updated_at = utcnow()
    _add_audit_log(
        db,
        actor_user_id=current_user.id,
        action="llm_pricing.update",
        target_type="llm_model_pricing",
        target_id=str(pricing_id),
        summary=f"修改模型单价 {row.provider}/{row.model}",
        metadata={"before": before, "after": req.model_dump(exclude_unset=True), **_request_metadata(request)},
    )
    await db.commit()
    await db.refresh(row)
    return {"code": 200, "message": "修改模型单价成功", "data": {"id": row.id}}


@router.get("/monitoring/api-health", response_model=dict)
async def monitoring_api_health(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin_permission("monitoring:read")),
) -> Any:
    """接口 500/P95 独立监测。"""
    data = await collect_api_health(db)
    return {"code": 200, "message": "获取接口健康成功", "data": data}


@router.get("/monitoring/user-stats", response_model=dict)
async def monitoring_user_stats(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin_permission("monitoring:read")),
) -> Any:
    """用户统计独立监测。"""
    data = await collect_user_stats(db)
    return {"code": 200, "message": "获取用户统计成功", "data": data}


@router.get("/monitoring/security-health", response_model=dict)
async def monitoring_security_health(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin_permission("monitoring:read")),
) -> Any:
    """P2 安全基线与部署健康检查。"""
    cost_guard_status = await collect_llm_guard_status(db)
    data = collect_security_health(cost_guard_status)
    return {"code": 200, "message": "获取安全健康成功", "data": data}


@router.get("/monitoring/snapshots", response_model=dict)
async def monitoring_snapshots(
    limit: int = Query(24, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin_permission("monitoring:read")),
) -> Any:
    """最近监测快照历史。"""
    rows = (await db.execute(
        select(MonitoringSnapshot)
        .order_by(MonitoringSnapshot.generated_at.desc())
        .limit(limit)
    )).scalars().all()
    return {
        "code": 200,
        "message": "获取监测历史成功",
        "data": {"items": [_snapshot_payload(row) for row in rows]},
    }


@router.get("/monitoring/alerts", response_model=dict)
async def monitoring_alerts(
    status_filter: str = Query("open", alias="status", description="open/resolved/all"),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin_permission("monitoring:read")),
) -> Any:
    """监测告警列表。"""
    stmt = select(MonitoringAlert).order_by(MonitoringAlert.last_triggered_at.desc()).limit(limit)
    if status_filter != "all":
        stmt = stmt.where(MonitoringAlert.status == status_filter)
    rows = (await db.execute(stmt)).scalars().all()
    return {
        "code": 200,
        "message": "获取监测告警成功",
        "data": {"items": [_alert_payload(row) for row in rows]},
    }


@router.patch("/monitoring/alerts/{alert_id}", response_model=dict)
async def update_monitoring_alert(
    alert_id: int,
    req: AlertUpdateRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin_permission("alerts:write")),
) -> Any:
    """更新告警处理备注，必要时手动标记已恢复。"""
    alert = await db.get(MonitoringAlert, alert_id)
    if not alert:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="告警不存在")

    now = utcnow()
    if req.note is not None:
        alert.note = req.note.strip() or None
    alert.handled_by_user_id = current_user.id
    alert.handled_at = now
    if req.resolve:
        alert.status = "resolved"
        alert.resolved_at = now
    db.add(alert)
    _add_audit_log(
        db,
        actor_user_id=current_user.id,
        action="monitoring_alert.update",
        target_type="monitoring_alert",
        target_id=str(alert.id),
        summary=f"处理告警：{alert.title}",
        detail=req.note,
        metadata={"resolve": req.resolve, "alert_key": alert.key, "alert_level": alert.level, **_request_metadata(request)},
    )
    await db.commit()
    await db.refresh(alert)

    return {
        "code": 200,
        "message": "告警已更新",
        "data": _alert_payload(alert),
    }


@router.get("/audit-logs", response_model=dict)
async def list_audit_logs(
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin_permission("audit:read")),
) -> Any:
    """最近管理员操作记录。"""
    rows = (await db.execute(
        select(AdminAuditLog)
        .order_by(AdminAuditLog.occurred_at.desc())
        .limit(limit)
    )).scalars().all()
    return {
        "code": 200,
        "message": "获取操作审计成功",
        "data": {"items": [_audit_payload(row) for row in rows]},
    }


@router.get("/admins", response_model=dict)
async def list_admins(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin_permission("admin:manage")),
) -> Any:
    """查看当前管理员列表。"""
    rows = (await db.execute(
        select(User)
        .where(or_(User.role.in_(ADMIN_ROLES), User.is_superuser.is_(True)))
        .order_by(User.is_superuser.desc(), User.id.asc())
    )).scalars().all()
    return {
        "code": 200,
        "message": "获取管理员列表成功",
        "data": {
            "items": [_user_payload(u) for u in rows],
            "super_admin_phone": _mask_phone(settings.SUPER_ADMIN_PHONE),
            "roles": sorted(ADMIN_ROLES),
        },
    }


@router.get("/users", response_model=dict)
async def list_users(
    keyword: Optional[str] = Query(None, description="用户名/手机号/邮箱关键词"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin_permission("users:read")),
) -> Any:
    """管理员查看用户概览。"""
    conditions = []
    if keyword:
        like = f"%{keyword}%"
        conditions.append(or_(User.username.ilike(like), User.email.ilike(like), User.phone.ilike(like)))

    total_stmt = select(func.count(User.id))
    list_stmt = (
        select(User, UserCredit.balance)
        .outerjoin(UserCredit, UserCredit.user_id == User.id)
        .order_by(User.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    if conditions:
        total_stmt = total_stmt.where(*conditions)
        list_stmt = list_stmt.where(*conditions)

    total = (await db.execute(total_stmt)).scalar_one()
    rows = (await db.execute(list_stmt)).all()
    items = []
    for user, balance in rows:
        data = _user_payload(user)
        data["credit_balance"] = int(balance or 0)
        items.append(data)
    return {
        "code": 200,
        "message": "获取用户列表成功",
        "data": {
            "items": items,
            "total": int(total),
            "limit": limit,
            "offset": offset,
        },
    }


@router.get("/tasks/failed", response_model=dict)
async def list_failed_tasks(
    limit: int = Query(30, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin_permission("monitoring:read")),
) -> Any:
    """最近失败任务列表。"""
    rows = (await db.execute(
        select(Task)
        .where(Task.status == TaskStatus.FAILED)
        .order_by(Task.updated_at.desc())
        .limit(limit)
    )).scalars().all()
    return {
        "code": 200,
        "message": "获取失败任务成功",
        "data": {"items": [_task_payload(task) for task in rows]},
    }


@router.patch("/users/{user_id}/status", response_model=dict)
async def update_user_status(
    user_id: int,
    req: UserStatusUpdateRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin_permission("users:status")),
) -> Any:
    """启用或禁用用户账号。"""
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用户不存在")
    if user.is_superuser and not req.is_active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="不能禁用最高管理员")

    before = {"is_active": user.is_active}
    user.is_active = req.is_active
    db.add(user)
    _add_audit_log(
        db,
        actor_user_id=current_user.id,
        action="user.status.update",
        target_type="user",
        target_id=str(user.id),
        summary=("启用用户" if req.is_active else "禁用用户") + f"：{user.id}",
        detail=req.reason,
        metadata={
            "target_user_id": user.id,
            "before": before,
            "after": {"is_active": user.is_active},
            **_request_metadata(request),
        },
    )
    await db.commit()
    await db.refresh(user)
    return {"code": 200, "message": "用户状态已更新", "data": _user_payload(user)}


@router.patch("/users/{user_id}/membership", response_model=dict)
async def update_user_membership(
    user_id: int,
    req: UserMembershipUpdateRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin_permission("users:status")),
) -> Any:
    """管理员设置或取消用户会员资格。"""
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用户不存在")

    before = {"is_member": user.is_member}
    user.is_member = req.is_member
    if req.is_member and not user.member_since:
        user.member_since = utcnow()
    elif not req.is_member:
        user.member_since = None
    db.add(user)
    _add_audit_log(
        db,
        actor_user_id=current_user.id,
        action="user.membership.update",
        target_type="user",
        target_id=str(user.id),
        summary=("设为会员" if req.is_member else "取消会员") + f"：{user.id}",
        detail=req.reason,
        metadata={
            "target_user_id": user.id,
            "before": before,
            "after": {"is_member": user.is_member},
            **_request_metadata(request),
        },
    )
    await db.commit()
    await db.refresh(user)
    return {"code": 200, "message": "会员状态已更新", "data": _user_payload(user)}


@router.post("/admins", response_model=dict)
async def set_admin(
    req: AdminGrantRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_super_admin_user),
) -> Any:
    """最高管理员按手机号设置或取消管理员。"""
    user = (await db.execute(select(User).where(User.phone == req.phone))).scalars().first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="未找到该手机号用户")

    target_role = (req.role or ("admin" if req.is_admin else "user")).strip().lower()
    if target_role != "user" and target_role not in ADMIN_ROLES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"无效后台角色，可选：user, {allowed_roles_text()}",
        )
    if user.phone == settings.SUPER_ADMIN_PHONE and target_role == "user":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="不能取消最高管理员权限")

    before = {"role": user.role, "is_superuser": user.is_superuser}
    user.role = target_role
    if user.phone == settings.SUPER_ADMIN_PHONE:
        user.is_superuser = True
    elif target_role == "user":
        user.is_superuser = False
    db.add(user)
    _add_audit_log(
        db,
        actor_user_id=current_user.id,
        action="admin.role.update",
        target_type="user",
        target_id=str(user.id),
        summary=f"更新后台角色为 {target_role}：{_mask_phone(user.phone)}",
        metadata={
            "target_user_id": user.id,
            "target_phone_masked": _mask_phone(user.phone),
            "before": before,
            "after": {"role": user.role, "is_superuser": user.is_superuser},
            **_request_metadata(request),
        },
    )
    await db.commit()
    await db.refresh(user)

    return {
        "code": 200,
        "message": "管理员权限已更新",
        "data": _user_payload(user),
    }
