"""面向管理员后台的监测聚合、快照和告警同步。"""

from __future__ import annotations

from datetime import timedelta
from typing import Any, Dict

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.timezone import utcnow
from app.models.credit import UserCredit
from app.models.info_cluster import InfoCluster
from app.models.monitoring import MonitoringAlert, MonitoringSnapshot
from app.models.raw_info import RAW_STATE_PENDING, RawInfo
from app.models.task import Task, TaskStatus
from app.models.user import User


def _iso(dt) -> str | None:
    return dt.isoformat() if dt else None


def _status(level: str, message: str, value: Any = None) -> Dict[str, Any]:
    return {"level": level, "message": message, "value": value}


async def collect_admin_monitoring(db: AsyncSession) -> Dict[str, Any]:
    """采集后台监测总览。"""
    now = utcnow()
    last_2h = now - timedelta(hours=2)
    last_24h = now - timedelta(hours=24)

    latest_raw_at = (await db.execute(select(func.max(RawInfo.scraped_at)))).scalar_one_or_none()
    latest_cluster_at = (await db.execute(select(func.max(InfoCluster.created_at)))).scalar_one_or_none()

    raw_2h = (await db.execute(
        select(func.count(RawInfo.id)).where(RawInfo.scraped_at >= last_2h)
    )).scalar_one()
    raw_24h = (await db.execute(
        select(func.count(RawInfo.id)).where(RawInfo.scraped_at >= last_24h)
    )).scalar_one()
    clusters_2h = (await db.execute(
        select(func.count(InfoCluster.id)).where(InfoCluster.created_at >= last_2h)
    )).scalar_one()
    clusters_24h = (await db.execute(
        select(func.count(InfoCluster.id)).where(InfoCluster.created_at >= last_24h)
    )).scalar_one()
    pending_raw = (await db.execute(
        select(func.count(RawInfo.id)).where(RawInfo.state == RAW_STATE_PENDING)
    )).scalar_one()

    tasks_24h = (await db.execute(
        select(Task.status, func.count(Task.id))
        .where(Task.created_at >= last_24h)
        .group_by(Task.status)
    )).all()
    task_counts = {str(status.value if hasattr(status, "value") else status): count for status, count in tasks_24h}
    failed_24h = int(task_counts.get(TaskStatus.FAILED.value, 0))
    pending_tasks = int(task_counts.get(TaskStatus.PENDING.value, 0))
    processing_tasks = int(task_counts.get(TaskStatus.PROCESSING.value, 0))

    latest_completed_task_at = (await db.execute(
        select(func.max(Task.completed_at)).where(Task.status == TaskStatus.COMPLETED)
    )).scalar_one_or_none()
    latest_failed_task_at = (await db.execute(
        select(func.max(Task.updated_at)).where(Task.status == TaskStatus.FAILED)
    )).scalar_one_or_none()

    total_users = (await db.execute(select(func.count(User.id)))).scalar_one()
    active_users_24h = (await db.execute(
        select(func.count(User.id)).where(User.last_login >= last_24h)
    )).scalar_one()
    admins = (await db.execute(
        select(func.count(User.id)).where((User.role == "admin") | (User.is_superuser.is_(True)))
    )).scalar_one()
    low_credit_users = (await db.execute(
        select(func.count(UserCredit.id)).where(UserCredit.balance < 10)
    )).scalar_one()

    signals = {
        "data_freshness": _status(
            "ok" if raw_2h > 0 else "warn",
            "最近 2 小时有新资讯" if raw_2h > 0 else "最近 2 小时没有新资讯入库",
            raw_2h,
        ),
        "preprocess_backlog": _status(
            "ok" if pending_raw < 300 else "warn",
            "预处理积压正常" if pending_raw < 300 else "预处理 pending 已超过 300 条",
            pending_raw,
        ),
        "task_failures": _status(
            "ok" if failed_24h == 0 else "warn",
            "最近 24 小时没有任务失败" if failed_24h == 0 else f"最近 24 小时有 {failed_24h} 个任务失败",
            failed_24h,
        ),
        "cluster_output": _status(
            "ok" if clusters_24h > 0 else "warn",
            "最近 24 小时有新信息簇" if clusters_24h > 0 else "最近 24 小时没有新信息簇",
            clusters_24h,
        ),
    }

    level_order = {"ok": 0, "warn": 1, "critical": 2}
    overall_level = max((s["level"] for s in signals.values()), key=lambda x: level_order[x])

    return {
        "generated_at": _iso(now),
        "overall": {
            "level": overall_level,
            "message": "系统运行正常" if overall_level == "ok" else "有监测项需要关注",
        },
        "signals": signals,
        "content_pipeline": {
            "raw_infos_2h": int(raw_2h),
            "raw_infos_24h": int(raw_24h),
            "clusters_2h": int(clusters_2h),
            "clusters_24h": int(clusters_24h),
            "pending_raw_infos": int(pending_raw),
            "latest_raw_scraped_at": _iso(latest_raw_at),
            "latest_cluster_created_at": _iso(latest_cluster_at),
        },
        "tasks": {
            "counts_24h": task_counts,
            "pending_24h": pending_tasks,
            "processing_24h": processing_tasks,
            "failed_24h": failed_24h,
            "latest_completed_at": _iso(latest_completed_task_at),
            "latest_failed_at": _iso(latest_failed_task_at),
        },
        "users": {
            "total": int(total_users),
            "active_24h": int(active_users_24h),
            "admins": int(admins),
            "low_credit_users": int(low_credit_users),
        },
    }


async def save_monitoring_snapshot(db: AsyncSession, payload: Dict[str, Any]) -> MonitoringSnapshot:
    """保存一次监测快照。"""
    content = payload.get("content_pipeline") or {}
    tasks = payload.get("tasks") or {}
    users = payload.get("users") or {}
    overall = payload.get("overall") or {}

    snapshot = MonitoringSnapshot(
        level=overall.get("level") or "ok",
        message=overall.get("message"),
        generated_at=utcnow(),
        raw_infos_2h=int(content.get("raw_infos_2h") or 0),
        clusters_24h=int(content.get("clusters_24h") or 0),
        pending_raw_infos=int(content.get("pending_raw_infos") or 0),
        failed_tasks_24h=int(tasks.get("failed_24h") or 0),
        active_users_24h=int(users.get("active_24h") or 0),
        low_credit_users=int(users.get("low_credit_users") or 0),
        payload=payload,
    )
    db.add(snapshot)
    await db.commit()
    await db.refresh(snapshot)
    return snapshot


def build_alert_specs(payload: Dict[str, Any]) -> list[Dict[str, Any]]:
    """根据监测结果生成当前应触发的告警规格。"""
    content = payload.get("content_pipeline") or {}
    tasks = payload.get("tasks") or {}
    users = payload.get("users") or {}
    alerts: list[Dict[str, Any]] = []

    raw_2h = int(content.get("raw_infos_2h") or 0)
    pending_raw = int(content.get("pending_raw_infos") or 0)
    clusters_24h = int(content.get("clusters_24h") or 0)
    failed_24h = int(tasks.get("failed_24h") or 0)
    low_credit_users = int(users.get("low_credit_users") or 0)

    if raw_2h <= 0:
        alerts.append({
            "key": "data_freshness.raw_infos_2h_zero",
            "level": "critical",
            "title": "采集可能断流",
            "message": "最近 2 小时没有新资讯入库，请检查采集任务、Celery Beat 和外部数据源。",
            "value": raw_2h,
            "threshold": 1,
        })

    if pending_raw >= 300:
        alerts.append({
            "key": "preprocess.pending_raw_high",
            "level": "warn" if pending_raw < 800 else "critical",
            "title": "预处理积压偏高",
            "message": f"当前有 {pending_raw} 条 raw_infos 仍在 pending，可能影响选题更新速度。",
            "value": pending_raw,
            "threshold": 300,
        })

    if clusters_24h <= 0:
        alerts.append({
            "key": "pipeline.clusters_24h_zero",
            "level": "warn",
            "title": "信息簇产出停滞",
            "message": "最近 24 小时没有新信息簇，可能是预处理、聚类或 AI 相关性过滤异常。",
            "value": clusters_24h,
            "threshold": 1,
        })

    if failed_24h > 0:
        alerts.append({
            "key": "tasks.failed_24h_nonzero",
            "level": "warn" if failed_24h < 5 else "critical",
            "title": "后台任务失败",
            "message": f"最近 24 小时有 {failed_24h} 个任务失败，请查看失败任务列表。",
            "value": failed_24h,
            "threshold": 1,
        })

    if low_credit_users >= 10:
        alerts.append({
            "key": "users.low_credit_many",
            "level": "warn",
            "title": "低余额用户较多",
            "message": f"当前有 {low_credit_users} 个用户积分低于 10，可能影响后续创作转化。",
            "value": low_credit_users,
            "threshold": 10,
        })

    for alert in alerts:
        alert["payload"] = payload
    return alerts


async def sync_monitoring_alerts(db: AsyncSession, payload: Dict[str, Any]) -> list[MonitoringAlert]:
    """同步当前告警状态：触发的打开，未触发的自动恢复。"""
    now = utcnow()
    specs = build_alert_specs(payload)
    active_keys = {spec["key"] for spec in specs}

    existing = (await db.execute(select(MonitoringAlert))).scalars().all()
    by_key = {alert.key: alert for alert in existing}
    changed: list[MonitoringAlert] = []

    for spec in specs:
        alert = by_key.get(spec["key"])
        if not alert:
            alert = MonitoringAlert(
                key=spec["key"],
                level=spec["level"],
                title=spec["title"],
                message=spec["message"],
                status="open",
                value=spec.get("value"),
                threshold=spec.get("threshold"),
                last_triggered_at=now,
                payload=spec.get("payload") or {},
            )
            db.add(alert)
        else:
            alert.level = spec["level"]
            alert.title = spec["title"]
            alert.message = spec["message"]
            alert.status = "open"
            alert.value = spec.get("value")
            alert.threshold = spec.get("threshold")
            alert.last_triggered_at = now
            alert.resolved_at = None
            alert.payload = spec.get("payload") or {}
        changed.append(alert)

    for alert in existing:
        if alert.status == "open" and alert.key not in active_keys:
            alert.status = "resolved"
            alert.resolved_at = now
            changed.append(alert)

    await db.commit()
    for alert in changed:
        await db.refresh(alert)
    return [alert for alert in changed if alert.status == "open"]
