"""管理员后台 API。"""

import asyncio
from datetime import datetime, timedelta
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import desc, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_super_admin_user
from app.api.v1.commercial import UNTITLED_PREFIX, _is_frontend_noise
from app.core.admin_permissions import ADMIN_ROLES, allowed_roles_text, require_admin_permission
from app.core.config import settings
from app.core.product_access import (
    ALL_PRODUCTS,
    PRODUCT_CREATION_TOOL,
    PRODUCT_LABELS,
    effective_product_access,
    is_admin_user,
    normalize_product_access,
)
from app.core.timezone import utcnow
from app.db.session import get_db
from app.models.admin_audit import AdminAuditLog
from app.models.api_request_log import ApiRequestLog
from app.models.celery_task_run import CeleryTaskRun
from app.models.credit import UserCredit
from app.models.generation_record import GenerationRecord
from app.models.llm_monitoring import LlmCallLog, LlmModelPricing
from app.models.monitoring import MonitoringAlert, MonitoringSnapshot
from app.models.raw_info import RawInfo
from app.models.source_registry import SourceRegistry
from app.models.system_announcement import SystemAnnouncement
from app.models.task import Task, TaskStatus
from app.models.user import User
from app.services.monitoring.checks import build_alert_specs, collect_admin_monitoring
from app.services.monitoring.modules import collect_ai_costs, collect_api_health, collect_source_health, collect_user_stats
from app.services.monitoring.security_health import collect_security_health
from app.services.llm.cost_guard import collect_llm_guard_status
from app.services.credit_service import CreditService
from app.services.wechat_pay_service import MEMBERSHIP_GIFT_CREDITS

router = APIRouter()


async def _activate_manual_creation_subscription(user: User, db: AsyncSession) -> bool:
    """管理员首次授予创作工具时，同步建立订阅和本期赠送积分。

    只对没有有效订阅的普通用户执行，反复保存同一份权益不会重复发放。
    """
    if is_admin_user(user) or PRODUCT_CREATION_TOOL not in normalize_product_access(user.product_access):
        return False
    service = CreditService(db)
    account = await service.get_or_create_account(user.id)
    if account.subscription_expires_at and account.subscription_expires_at > utcnow():
        return False
    await service.activate_subscription(
        user_id=user.id,
        gift_amount=MEMBERSHIP_GIFT_CREDITS,
        description="管理员开通创作工具赠送积分",
    )
    return True


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


class UserProductAccessUpdateRequest(BaseModel):
    product_access: list[str] = Field(default_factory=list, description="已开通产品：creation_tool/potential_commercial/practical_camp/xhs_topic")
    reason: Optional[str] = Field(None, max_length=1000, description="操作原因")


class UserCreditAdjustRequest(BaseModel):
    amount: int = Field(..., description="调整数量：mode=delta 时为增减量（可为负），mode=set 时为目标余额")
    mode: str = Field("delta", description="delta=在当前余额上增减；set=直接设为指定余额")
    reason: str = Field(..., min_length=1, max_length=500, description="调整原因（必填，便于审计追溯）")


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


class SystemAnnouncementRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=120)
    content: str = Field(..., min_length=1, max_length=10000)
    expires_at: datetime


class SystemAnnouncementUpdateRequest(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=120)
    content: Optional[str] = Field(None, min_length=1, max_length=10000)
    expires_at: Optional[datetime] = None
    is_published: Optional[bool] = None


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
        "product_access": effective_product_access(user),
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


def _celery_task_payload(task: CeleryTaskRun) -> dict:
    return {
        "id": task.id,
        "task_id": task.task_id,
        "task_name": task.task_name,
        "category": task.category,
        "queue": task.queue,
        "status": task.status,
        "retry_count": task.retry_count or 0,
        "worker": task.worker,
        "args": task.args_json,
        "kwargs": task.kwargs_json,
        "result": task.result_json,
        "error_message": task.error_message,
        "created_at": task.created_at.isoformat() if task.created_at else None,
        "updated_at": task.updated_at.isoformat() if task.updated_at else None,
        "started_at": task.started_at,
        "finished_at": task.finished_at,
        "last_seen_at": task.last_seen_at,
        "is_dead_letter": bool(task.is_dead_letter),
        "retried_from_id": task.retried_from_id,
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


def _announcement_admin_payload(row: SystemAnnouncement) -> dict:
    return {
        "id": row.id, "title": row.title, "content": row.content,
        "is_published": row.is_published,
        "published_at": row.published_at.isoformat() if row.published_at else None,
        "expires_at": row.expires_at.isoformat() if row.expires_at else None,
        "created_by_user_id": row.created_by_user_id,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


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


@router.get("/announcements", response_model=dict)
async def list_system_announcements(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_super_admin_user),
) -> Any:
    """最高管理员查看全部系统公告（含过期和已停用）。"""
    rows = (await db.execute(select(SystemAnnouncement).order_by(SystemAnnouncement.created_at.desc()))).scalars().all()
    return {"code": 200, "message": "获取系统公告成功", "data": {"items": [_announcement_admin_payload(row) for row in rows]}}


@router.post("/announcements", response_model=dict)
async def create_system_announcement(
    req: SystemAnnouncementRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_super_admin_user),
) -> Any:
    """发布一条立即生效的系统公告。"""
    now = utcnow()
    if req.expires_at <= now:
        raise HTTPException(status_code=400, detail="提示到期时间必须晚于当前时间")
    row = SystemAnnouncement(title=req.title.strip(), content=req.content.strip(), expires_at=req.expires_at, published_at=now, created_by_user_id=current_user.id)
    db.add(row)
    _add_audit_log(db, actor_user_id=current_user.id, action="system_announcement.create", target_type="system_announcement", summary=f"发布系统公告：{row.title}", metadata={"expires_at": req.expires_at.isoformat(), **_request_metadata(request)})
    await db.commit()
    await db.refresh(row)
    return {"code": 200, "message": "系统公告已发布", "data": _announcement_admin_payload(row)}


@router.patch("/announcements/{announcement_id}", response_model=dict)
async def update_system_announcement(
    announcement_id: int,
    req: SystemAnnouncementUpdateRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_super_admin_user),
) -> Any:
    """修改公告，或通过 is_published=false 立即停止提示。"""
    row = await db.get(SystemAnnouncement, announcement_id)
    if not row:
        raise HTTPException(status_code=404, detail="系统公告不存在")
    changes = req.model_dump(exclude_unset=True)
    if "expires_at" in changes and changes["expires_at"] <= utcnow():
        raise HTTPException(status_code=400, detail="提示到期时间必须晚于当前时间")
    for key, value in changes.items():
        setattr(row, key, value.strip() if isinstance(value, str) else value)
    row.updated_at = utcnow()
    _add_audit_log(db, actor_user_id=current_user.id, action="system_announcement.update", target_type="system_announcement", target_id=str(row.id), summary=f"更新系统公告：{row.title}", metadata={"changes": {k: (v.isoformat() if isinstance(v, datetime) else v) for k, v in changes.items()}, **_request_metadata(request)})
    await db.commit()
    await db.refresh(row)
    return {"code": 200, "message": "系统公告已更新", "data": _announcement_admin_payload(row)}


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


@router.get("/monitoring/commercial-diagnostics", response_model=dict)
async def monitoring_commercial_diagnostics(
    days: int = Query(10, ge=1, le=180, description="前端当前时间范围"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin_permission("monitoring:read")),
) -> Any:
    """极致了公众号商单链路诊断。"""
    cutoff = datetime.utcnow() - timedelta(days=days)
    rows = (await db.execute(
        select(
            RawInfo.content,
            RawInfo.commercial_level,
            RawInfo.commercial_meta,
            RawInfo.published_at,
        )
        .join(SourceRegistry, RawInfo.source_registry_id == SourceRegistry.id)
        .where(SourceRegistry.source_type == "dajiala_wechat")
    )).all()

    data = {
        "total": len(rows),
        "total_in_days": 0,
        "with_fulltext": 0,
        "ai_done": 0,
        "ai_none": 0,
        "suspected": 0,
        "likely": 0,
        "frontend_visible": 0,
    }
    for content, level, meta, published_at in rows:
        in_days = bool(published_at and published_at >= cutoff)
        meta = meta or {}
        signals = meta.get("signals") if isinstance(meta, dict) else {}
        if in_days:
            data["total_in_days"] += 1
        if len(content or "") > 300:
            data["with_fulltext"] += 1
        if isinstance(signals, dict) and signals.get("layer") == "llm":
            data["ai_done"] += 1
        if level == "none":
            data["ai_none"] += 1
        elif level == "suspected":
            data["suspected"] += 1
        elif level == "likely":
            data["likely"] += 1
    # 这里必须复用潜在商单页面的来源、标题和噪声过滤，不能把所有
    # suspected/likely 都直接算作“前端当前可见”。
    frontend_candidates = (
        await db.execute(
            select(RawInfo)
            .join(SourceRegistry, RawInfo.source_registry_id == SourceRegistry.id)
            .where(
                RawInfo.commercial_level.in_(["suspected", "likely"]),
                or_(
                    RawInfo.url.ilike("%mp.weixin.qq.com%"),
                    SourceRegistry.source_type.in_(["dajiala_wechat", "sogou_wechat", "exa_wechat"]),
                ),
                RawInfo.title.isnot(None),
                RawInfo.title != "",
                ~RawInfo.title.ilike(f"{UNTITLED_PREFIX}%"),
                RawInfo.published_at >= cutoff,
            )
            .order_by(desc(RawInfo.published_at).nulls_last())
        )
    ).scalars().all()

    frontend_items = []
    for row in frontend_candidates:
        meta = row.commercial_meta if isinstance(row.commercial_meta, dict) else {}
        item = {
            "id": row.id,
            "title": row.title,
            "summary": row.summary,
            "commercial_brand": row.commercial_brand or meta.get("brand") or "",
            "product": meta.get("product") or "",
        }
        if _is_frontend_noise(item):
            continue
        frontend_items.append({
            "id": row.id,
            "title": row.title,
            "url": row.url,
            "commercial_level": row.commercial_level or "none",
            "commercial_brand": item["commercial_brand"],
            "commercial_category": row.commercial_category or meta.get("category") or "",
            "product": item["product"],
            "published_at": row.published_at.isoformat() if row.published_at else None,
            "scraped_at": row.scraped_at.isoformat() if row.scraped_at else None,
        })
    data["frontend_visible"] = len(frontend_items)
    data["items"] = frontend_items[:200]

    if data["total"] == 0:
        diagnosis = "极致了文章还没有入库。先跑历史补库或等待当天发文任务。"
    elif data["with_fulltext"] == 0:
        diagnosis = "文章已入库，但没有抓到正文。需要跑全文补抓任务。"
    elif data["ai_done"] == 0:
        diagnosis = "正文已有，但还没有完成 DeepSeek 商单判断。需要触发重检。"
    elif data["suspected"] + data["likely"] == 0:
        diagnosis = "DeepSeek 已判断，但全部是 none。前端为空是因为没有 suspected/likely。"
    elif data["frontend_visible"] == 0:
        diagnosis = f"有商单结果，但按前端展示规则在最近 {days} 天内没有可见记录。"
    else:
        diagnosis = "后端已有可展示商单；如果前端仍为空，是页面筛选或接口请求问题。"

    data["diagnosis"] = diagnosis
    return {"code": 200, "message": "获取商单诊断成功", "data": data}


@router.delete("/monitoring/commercial-diagnostics/{raw_info_id}", response_model=dict)
async def delete_commercial_diagnostic(
    raw_info_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_super_admin_user),
) -> Any:
    """移除一条商单判断结果，但保留原始文章，仅最高管理员可操作。"""
    row = await db.get(RawInfo, raw_info_id)
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="商单记录不存在")
    if row.commercial_level not in ("suspected", "likely"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="该文章当前不是商单记录")

    source_type = (
        await db.execute(
            select(SourceRegistry.source_type).where(SourceRegistry.id == row.source_registry_id)
        )
    ).scalar_one_or_none()
    if source_type != "dajiala_wechat":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="只能删除极致了来源的商单记录")

    title = (row.title or "未命名文章").strip()
    _add_audit_log(
        db,
        actor_user_id=current_user.id,
        action="commercial_diagnostic.delete",
        target_type="raw_info",
        target_id=str(row.id),
        summary=f"删除商单诊断记录：{title[:120]}",
        metadata={
            "title": row.title,
            "url": row.url,
            "commercial_level": row.commercial_level,
            "commercial_brand": row.commercial_brand,
            "commercial_category": row.commercial_category,
            **_request_metadata(request),
        },
    )
    row.commercial_level = "none"
    row.commercial_meta = {}
    row.commercial_brand = None
    row.commercial_category = None
    await db.commit()
    return {"code": 200, "message": "商单记录已删除，原文已保留", "data": {"id": raw_info_id}}


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
    current_user: User = Depends(get_current_super_admin_user),
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
    current_user: User = Depends(get_current_super_admin_user),
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
    current_user: User = Depends(get_current_super_admin_user),
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
    current_user: User = Depends(require_admin_permission("users:read")),
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
            "products": [{"value": p, "label": PRODUCT_LABELS[p]} for p in sorted(ALL_PRODUCTS)],
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


@router.get("/task-center/overview", response_model=dict)
async def task_center_overview(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin_permission("monitoring:read")),
) -> Any:
    """Celery 队列、Worker 和任务生命周期总览。"""
    from app.services.monitoring.celery_tasks import collect_celery_overview

    data = await collect_celery_overview(db)
    return {"code": 200, "message": "获取任务中心总览成功", "data": data}


@router.get("/task-center/tasks", response_model=dict)
async def task_center_tasks(
    status_filter: str = Query("all", alias="status"),
    category: Optional[str] = Query(None),
    queue: Optional[str] = Query(None),
    dead_letter: Optional[bool] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin_permission("monitoring:read")),
) -> Any:
    """管理员查看任务运行历史、失败任务和死信任务。"""
    stmt = select(CeleryTaskRun).order_by(CeleryTaskRun.created_at.desc()).limit(limit)
    if status_filter != "all":
        stmt = stmt.where(CeleryTaskRun.status == status_filter)
    if category:
        stmt = stmt.where(CeleryTaskRun.category == category)
    if queue:
        stmt = stmt.where(CeleryTaskRun.queue == queue)
    if dead_letter is not None:
        stmt = stmt.where(CeleryTaskRun.is_dead_letter.is_(dead_letter))

    rows = (await db.execute(stmt)).scalars().all()
    return {
        "code": 200,
        "message": "获取任务列表成功",
        "data": {"items": [_celery_task_payload(row) for row in rows]},
    }


@router.post("/task-center/tasks/{task_run_id}/retry", response_model=dict)
async def retry_task_center_task(
    task_run_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin_permission("tasks:retry")),
) -> Any:
    """重新投递失败或死信任务。仅允许后台管理员操作。"""
    row = await db.get(CeleryTaskRun, task_run_id)
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="任务记录不存在")
    if row.status not in {"failed", "dead_letter"} and not row.is_dead_letter:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="只有失败或死信任务可以重试")
    if not row.task_name or row.task_name == "unknown":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="任务缺少可重试的任务名称")

    args = row.args_json if isinstance(row.args_json, list) else []
    kwargs = row.kwargs_json if isinstance(row.kwargs_json, dict) else {}
    try:
        from app.core.celery_app import celery_app

        result = await asyncio.to_thread(
            celery_app.send_task,
            row.task_name,
            args=args,
            kwargs=kwargs,
            queue=row.queue or "default",
        )
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=f"任务重新投递失败：{str(exc)[:200]}")

    _add_audit_log(
        db,
        actor_user_id=current_user.id,
        action="celery_task.retry",
        target_type="celery_task_run",
        target_id=str(row.id),
        summary=f"重试 Celery 任务：{row.task_name}",
        detail=row.error_message,
        metadata={
            "old_task_id": row.task_id,
            "new_task_id": result.id,
            "queue": row.queue,
            **_request_metadata(request),
        },
    )
    await db.commit()

    # after_task_publish 通常会先落库；如果当前进程没有加载 signal，也不影响返回新任务 ID。
    new_row = (await db.execute(
        select(CeleryTaskRun).where(CeleryTaskRun.task_id == result.id)
    )).scalar_one_or_none()
    if new_row:
        new_row.retried_from_id = row.id
        await db.commit()

    return {
        "code": 200,
        "message": "任务已重新投递",
        "data": {"task_id": result.id, "task_name": row.task_name, "queue": row.queue},
    }


@router.patch("/users/{user_id}/status", response_model=dict)
async def update_user_status(
    user_id: int,
    req: UserStatusUpdateRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_super_admin_user),
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
    current_user: User = Depends(get_current_super_admin_user),
) -> Any:
    """管理员设置或取消用户会员资格。"""
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用户不存在")

    before = {"is_member": user.is_member}
    user.is_member = req.is_member
    if req.is_member and not user.member_since:
        user.member_since = utcnow()
        user.product_access = normalize_product_access([*normalize_product_access(user.product_access), "creation_tool"])
    elif not req.is_member:
        user.member_since = None
        user.product_access = []
    db.add(user)
    creation_subscription_activated = False
    if req.is_member:
        creation_subscription_activated = await _activate_manual_creation_subscription(user, db)
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
            "after": {
                "is_member": user.is_member,
                "creation_subscription_activated": creation_subscription_activated,
            },
            **_request_metadata(request),
        },
    )
    await db.commit()
    await db.refresh(user)
    return {"code": 200, "message": "会员状态已更新", "data": _user_payload(user)}


@router.patch("/users/{user_id}/product-access", response_model=dict)
async def update_user_product_access(
    user_id: int,
    req: UserProductAccessUpdateRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_super_admin_user),
) -> Any:
    """最高管理员设置用户已购买的产品权益。"""
    invalid = sorted(set(req.product_access) - ALL_PRODUCTS)
    if invalid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"无效产品权益：{', '.join(invalid)}",
        )
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用户不存在")
    if user.is_superuser:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="最高管理员默认拥有全部功能，无需设置产品权益")

    before = {"product_access": normalize_product_access(user.product_access)}
    user.product_access = normalize_product_access(req.product_access)
    user.is_member = bool(user.product_access)
    if user.is_member and not user.member_since:
        user.member_since = utcnow()
    elif not user.is_member:
        user.member_since = None
    db.add(user)
    creation_subscription_activated = await _activate_manual_creation_subscription(user, db)
    _add_audit_log(
        db,
        actor_user_id=current_user.id,
        action="user.product_access.update",
        target_type="user",
        target_id=str(user.id),
        summary=f"更新用户产品权益：{user.id}",
        detail=req.reason,
        metadata={
            "target_user_id": user.id,
            "before": before,
            "after": {
                "product_access": user.product_access,
                "creation_subscription_activated": creation_subscription_activated,
            },
            **_request_metadata(request),
        },
    )
    await db.commit()
    await db.refresh(user)
    message = "产品权益已更新"
    if creation_subscription_activated:
        message += "，已开通创作工具订阅并赠送 6000 积分"
    return {"code": 200, "message": message, "data": _user_payload(user)}


@router.get("/users/{user_id}/credits", response_model=dict)
async def get_user_credits_detail(
    user_id: int,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin_permission("users:read")),
) -> Any:
    """查看指定用户的积分账户、消耗统计与交易流水。"""
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用户不存在")

    service = CreditService(db)
    account = await service.get_account_info(user_id)
    stats = await service.get_consumption_stats(user_id)
    transactions = await service.get_transactions(user_id, limit=limit, offset=offset)
    total = await service.get_transaction_count(user_id)
    # get_account_info 可能懒创建了积分账户，提交一次
    await db.commit()

    return {
        "code": 200,
        "message": "获取用户积分记录成功",
        "data": {
            "user": {
                "id": user.id,
                "username": user.username,
                "full_name": user.full_name,
                "phone": _mask_phone(user.phone),
            },
            "account": account,
            "stats": stats,
            "transactions": transactions,
            "total": total,
            "limit": limit,
            "offset": offset,
        },
    }


def _gen_record_payload(record: GenerationRecord) -> dict:
    snapshot = record.output_snapshot if isinstance(record.output_snapshot, dict) else {}
    return {
        "id": record.id,
        "type": record.type,
        "status": record.status,
        "run_id": record.run_id,
        "display_title": record.display_title,
        "error": snapshot.get("error"),
        "input_snapshot": record.input_snapshot,
        "created_at": record.created_at.isoformat() if record.created_at else None,
    }


def _llm_error_payload(row: LlmCallLog) -> dict:
    return {
        "id": row.id,
        "provider": row.provider,
        "model": row.model,
        "operation": row.operation,
        "operation_id": row.operation_id,
        "status": row.status,
        "finish_reason": row.finish_reason,
        "error_message": row.error_message,
        "duration_ms": row.duration_ms,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


def _api_error_payload(row: ApiRequestLog) -> dict:
    return {
        "id": row.id,
        "method": row.method,
        "path": row.path,
        "status_code": row.status_code,
        "duration_ms": row.duration_ms,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


@router.get("/users/{user_id}/diagnostics", response_model=dict)
async def get_user_diagnostics(
    user_id: int,
    limit: int = Query(30, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin_permission("users:read")),
) -> Any:
    """按用户排障：一次性拉取最近生成记录（含失败原因）、失败的 LLM 调用、接口错误。

    用户反馈"生成失败/用不了"时，在此定位到具体是哪一步、报什么错，无需上服务器查日志。
    """
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用户不存在")

    gen_rows = (await db.execute(
        select(GenerationRecord)
        .where(GenerationRecord.user_id == user_id)
        .order_by(GenerationRecord.created_at.desc())
        .limit(limit)
    )).scalars().all()

    llm_rows = (await db.execute(
        select(LlmCallLog)
        .where(LlmCallLog.user_id == user_id, LlmCallLog.status != "success")
        .order_by(LlmCallLog.created_at.desc())
        .limit(limit)
    )).scalars().all()

    api_rows = (await db.execute(
        select(ApiRequestLog)
        .where(ApiRequestLog.user_id == user_id, ApiRequestLog.status_code >= 400)
        .order_by(ApiRequestLog.created_at.desc())
        .limit(limit)
    )).scalars().all()

    return {
        "code": 200,
        "message": "获取用户排障信息成功",
        "data": {
            "user": {
                "id": user.id,
                "username": user.username,
                "full_name": user.full_name,
                "phone": _mask_phone(user.phone),
            },
            "summary": {
                "generation_total": len(gen_rows),
                "generation_failed": sum(1 for r in gen_rows if r.status == "failed"),
                "llm_errors": len(llm_rows),
                "api_errors": len(api_rows),
                "limit": limit,
            },
            "generation_records": [_gen_record_payload(r) for r in gen_rows],
            "llm_errors": [_llm_error_payload(r) for r in llm_rows],
            "api_errors": [_api_error_payload(r) for r in api_rows],
        },
    }


@router.patch("/users/{user_id}/credits", response_model=dict)
async def adjust_user_credits(
    user_id: int,
    req: UserCreditAdjustRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_super_admin_user),
) -> Any:
    """最高管理员手动调整用户积分余额（增加/扣减/设为指定值）。"""
    if req.mode not in ("delta", "set"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="mode 只能为 delta 或 set")

    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用户不存在")

    service = CreditService(db)
    account = await service.get_or_create_account(user_id)
    before = account.balance

    if req.mode == "set":
        if req.amount < 0:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="设定余额不能为负")
        delta = req.amount - before
    else:
        delta = req.amount

    if delta == 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="积分没有变化，无需调整")

    try:
        result = await service.admin_adjust_balance(user_id, delta, req.reason.strip())
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    _add_audit_log(
        db,
        actor_user_id=current_user.id,
        action="user.credits.adjust",
        target_type="user",
        target_id=str(user.id),
        summary=f"调整用户积分 {delta:+d}（{before} → {result['balance']}）：{user.id}",
        detail=req.reason,
        metadata={
            "target_user_id": user.id,
            "mode": req.mode,
            "delta": delta,
            "before": before,
            "after": result["balance"],
            **_request_metadata(request),
        },
    )
    await db.commit()
    return {
        "code": 200,
        "message": "用户积分已调整",
        "data": result,
    }


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
