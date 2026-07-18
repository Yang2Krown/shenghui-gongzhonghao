"""Mac 本地 XHS 采集节点：绑定、命令通道、进度与结果上传。"""
from __future__ import annotations

import asyncio
import hashlib
import hmac
import secrets
from datetime import date, datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, WebSocket, WebSocketDisconnect, status
from pydantic import BaseModel, Field
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_super_admin_user
from app.core.admin_permissions import require_admin_permission
from app.core.config import settings
from app.core.timezone import utcnow
from app.db.session import AsyncSessionLocal, get_db
from app.models.user import User
from app.models.xhs import (
    XhsAgentBatch, XhsAgentCommand, XhsAgentPairing, XhsCollectorDevice,
    XhsKeyword, XhsKeywordRun,
)
from app.services.xhs_agent_ingestion import AgentIngestionConflict, ingest_agent_result

router = APIRouter()
admin_router = APIRouter()
COMMAND_TYPES = {"test_keyword", "pause", "resume", "stop", "login"}
DEFAULT_SCHEDULE = {
    "enabled": True,
    "window_start": "09:30",
    "window_end": "22:30",
    "jitter_minutes": 8,
    "daily_derived_limit": 5,
    "grace_minutes": 12,
    "no_catch_up": True,
    "detail_gap_seconds": [20, 40],
    "stop_on_risk": True,
}
STALE_BATCH_MINUTES = 15
MANUAL_RETRY_GAP_MINUTES = 15


def _secret_hash(value: str) -> str:
    return hmac.new(settings.SECRET_KEY.encode(), value.encode(), hashlib.sha256).hexdigest()


def _schedule_payload(device: XhsCollectorDevice) -> dict[str, Any]:
    return {**DEFAULT_SCHEDULE, **(device.schedule_config or {})}


def _device_payload(device: XhsCollectorDevice, connected: bool = False) -> dict[str, Any]:
    return {
        "id": device.public_id,
        "name": device.name,
        "enabled": device.enabled,
        "platform": device.platform,
        "agent_version": device.agent_version,
        "cookie_status": device.cookie_status,
        "status": "online" if connected else device.current_status,
        "connected": connected,
        "current_keyword": device.current_keyword,
        "last_seen_at": device.last_seen_at.isoformat() if device.last_seen_at else None,
        "last_error": device.last_error,
        "schedule": _schedule_payload(device),
    }


async def _close_stale_batches(db: AsyncSession, device_id: int | None = None, close_running_now: bool = False) -> int:
    """Close batches whose Agent stopped reporting, so monitoring cannot stay running forever."""
    query = select(XhsAgentBatch).where(
        XhsAgentBatch.status.in_(("running", "paused")),
    )
    if not close_running_now:
        query = query.where(
            XhsAgentBatch.last_progress_at < utcnow() - timedelta(minutes=STALE_BATCH_MINUTES),
        )
    if device_id is not None:
        query = query.where(XhsAgentBatch.device_id == device_id)
    batches = (await db.scalars(query)).all()
    if not batches:
        return 0
    now = utcnow()
    for batch in batches:
        batch.status = "failed"
        batch.finished_at = now
        batch.current_keyword_id = None
        batch.metadata_json = {
            **(batch.metadata_json or {}),
            "last_error": "本地 Agent 超过 15 分钟未上报进度，已自动结束",
        }
    await db.commit()
    return len(batches)


class AgentConnectionManager:
    def __init__(self) -> None:
        self._connections: dict[int, WebSocket] = {}
        self._lock = asyncio.Lock()

    async def connect(self, device_id: int, websocket: WebSocket) -> None:
        await websocket.accept()
        async with self._lock:
            previous = self._connections.get(device_id)
            self._connections[device_id] = websocket
        if previous and previous is not websocket:
            await previous.close(code=4001, reason="new connection")

    async def disconnect(self, device_id: int, websocket: WebSocket) -> bool:
        async with self._lock:
            if self._connections.get(device_id) is websocket:
                self._connections.pop(device_id, None)
                return True
        return False

    def connected(self, device_id: int) -> bool:
        return device_id in self._connections

    async def send_command(self, device_id: int, command: XhsAgentCommand) -> bool:
        websocket = self._connections.get(device_id)
        if not websocket:
            return False
        try:
            await websocket.send_json({"type": "command", "command": _command_payload(command)})
            return True
        except Exception:
            await self.disconnect(device_id, websocket)
            return False


manager = AgentConnectionManager()


def _command_payload(command: XhsAgentCommand) -> dict[str, Any]:
    return {
        "id": command.public_id,
        "command_type": command.command_type,
        "payload": command.payload or {},
        "expires_at": command.expires_at.isoformat(),
    }


async def _agent_from_token(db: AsyncSession, authorization: str | None) -> XhsCollectorDevice:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "缺少采集节点凭据")
    token = authorization.split(" ", 1)[1].strip()
    if len(token) < 32:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "采集节点凭据无效")
    device = (await db.execute(select(XhsCollectorDevice).where(XhsCollectorDevice.token_hash == _secret_hash(token), XhsCollectorDevice.enabled.is_(True)))).scalar_one_or_none()
    if not device:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "采集节点未绑定或已撤销")
    return device


async def get_agent(
    authorization: str | None = Header(None),
    db: AsyncSession = Depends(get_db),
) -> XhsCollectorDevice:
    return await _agent_from_token(db, authorization)


class PairBody(BaseModel):
    code: str = Field(..., min_length=6, max_length=32)
    name: str = Field(..., min_length=1, max_length=120)
    agent_version: str = Field("0.3.4", max_length=40)
    platform: str = Field("macos", max_length=40)


class HeartbeatBody(BaseModel):
    status: str = Field("idle", pattern="^(idle|running|paused|risk_blocked|needs_login)$")
    cookie_status: str = Field("unknown", pattern="^(unknown|valid|expired|missing|verification_required)$")
    current_keyword: str | None = Field(None, max_length=120)
    last_error: str | None = Field(None, max_length=1000)
    agent_version: str | None = Field(None, max_length=40)
    daily_plan: dict[str, Any] | None = None


class BatchBody(BaseModel):
    local_batch_key: str = Field(..., min_length=8, max_length=120)
    mode: str = Field(..., pattern="^(scheduled|manual|test)$")
    schedule_date: date
    schedule_group: int | None = Field(None, ge=1, le=3)
    total_keywords: int = Field(0, ge=0, le=100)
    command_id: str | None = None


class BatchProgressBody(BaseModel):
    status: str = Field(..., pattern="^(running|paused|completed|partial|failed|stopped|risk_blocked)$")
    current_keyword_id: int | None = None
    completed_keywords: int = Field(..., ge=0, le=100)
    failed_keywords: int = Field(..., ge=0, le=100)
    error: str | None = Field(None, max_length=1000)


class UploadBody(BaseModel):
    keyword_id: int
    idempotency_key: str = Field(..., min_length=12, max_length=160)
    status: str = Field("success", pattern="^(success|failed|risk_blocked)$")
    error: str | None = Field(None, max_length=1000)
    notes: list[dict[str, Any]] = Field(default_factory=list, max_length=50)
    diagnostics: dict[str, Any] = Field(default_factory=dict)


class CommandStatusBody(BaseModel):
    status: str = Field(..., pattern="^(delivered|running|succeeded|failed|cancelled)$")
    result: dict[str, Any] = Field(default_factory=dict)
    error: str | None = Field(None, max_length=1000)


class CommandBody(BaseModel):
    device_id: str
    command_type: str
    keyword_id: int | None = None
    schedule_group: int | None = Field(None, ge=1, le=3)


@admin_router.post("/agent/pairings")
async def create_pairing(admin: User = Depends(get_current_super_admin_user), db: AsyncSession = Depends(get_db)):
    code = "-".join((secrets.token_hex(2).upper(), secrets.token_hex(2).upper()))
    pairing = XhsAgentPairing(code_hash=_secret_hash(code), created_by_user_id=admin.id, expires_at=utcnow() + timedelta(minutes=10))
    db.add(pairing)
    await db.commit()
    return {"code": code, "expires_at": pairing.expires_at.isoformat()}


@router.post("/pair")
async def pair_agent(body: PairBody, db: AsyncSession = Depends(get_db)):
    now = utcnow()
    pairing = (await db.execute(select(XhsAgentPairing).where(XhsAgentPairing.code_hash == _secret_hash(body.code), XhsAgentPairing.used_at.is_(None), XhsAgentPairing.expires_at > now).with_for_update())).scalar_one_or_none()
    if not pairing:
        raise HTTPException(400, "绑定码无效或已过期")
    token = secrets.token_urlsafe(48)
    device = XhsCollectorDevice(
        name=body.name, token_hash=_secret_hash(token), platform=body.platform,
        agent_version=body.agent_version, current_status="offline",
        schedule_config=DEFAULT_SCHEDULE,
    )
    db.add(device)
    await db.flush()
    pairing.used_at = now
    pairing.device_id = device.id
    await db.commit()
    return {"device_id": device.public_id, "device_token": token, "schedule": device.schedule_config}


@router.get("/manifest")
async def manifest(agent: XhsCollectorDevice = Depends(get_agent), db: AsyncSession = Depends(get_db)):
    now = utcnow()
    keywords = (await db.scalars(select(XhsKeyword).where(XhsKeyword.enabled.is_(True)).order_by(XhsKeyword.keyword_type, XhsKeyword.schedule_group, XhsKeyword.id))).all()
    completed_today = set((await db.scalars(
        select(XhsKeywordRun.keyword_id).where(
            XhsKeywordRun.run_date == now.date(),
            XhsKeywordRun.status.in_(("completed", "partial")),
        )
    )).all())
    return {
        "device": _device_payload(agent, manager.connected(agent.id)),
        "keywords": [{
            "id": item.id, "keyword": item.keyword, "type": item.keyword_type, "group": item.schedule_group,
            "eligible": item.keyword_type == "base" or (
                (item.cooldown_until is None or item.cooldown_until <= now.date())
                and (item.next_run_at is None or item.next_run_at <= now)
            ),
            "completed_today": item.id in completed_today,
        } for item in keywords],
        "rules": {"max_age_days": 7, "likes_gt": 2000, "max_per_keyword": 10, "sort": "popular"},
        "schedule": _schedule_payload(agent),
    }


@router.post("/heartbeat")
async def heartbeat(body: HeartbeatBody, agent: XhsCollectorDevice = Depends(get_agent), db: AsyncSession = Depends(get_db)):
    if body.status in {"idle", "risk_blocked", "needs_login"}:
        await _close_stale_batches(db, agent.id, close_running_now=True)
    agent.last_seen_at = utcnow()
    agent.current_status = body.status
    agent.cookie_status = body.cookie_status
    agent.current_keyword = body.current_keyword
    agent.last_error = body.last_error
    if body.agent_version:
        agent.agent_version = body.agent_version
    if body.daily_plan is not None:
        slots = body.daily_plan.get("slots")
        if not isinstance(slots, list) or len(slots) > 50:
            raise HTTPException(400, "今日采集计划格式无效")
        agent.schedule_config = {**_schedule_payload(agent), "today_plan": body.daily_plan}
    await db.commit()
    return {"ok": True, "server_time": utcnow().isoformat()}


@router.post("/batches")
async def create_batch(body: BatchBody, agent: XhsCollectorDevice = Depends(get_agent), db: AsyncSession = Depends(get_db)):
    existing = (await db.execute(select(XhsAgentBatch).where(XhsAgentBatch.device_id == agent.id, XhsAgentBatch.local_batch_key == body.local_batch_key))).scalar_one_or_none()
    if existing:
        return {"batch_id": existing.public_id, "duplicate": True}
    command = None
    if body.command_id:
        command = (await db.execute(select(XhsAgentCommand).where(XhsAgentCommand.public_id == body.command_id, XhsAgentCommand.device_id == agent.id))).scalar_one_or_none()
    now = utcnow()
    batch = XhsAgentBatch(
        device_id=agent.id, command_id=command.id if command else None,
        local_batch_key=body.local_batch_key, mode=body.mode, status="running",
        schedule_date=body.schedule_date, schedule_group=body.schedule_group,
        total_keywords=body.total_keywords, started_at=now, last_progress_at=now,
    )
    db.add(batch)
    await db.commit()
    return {"batch_id": batch.public_id, "duplicate": False}


@router.patch("/batches/{batch_id}/progress")
async def update_batch(batch_id: str, body: BatchProgressBody, agent: XhsCollectorDevice = Depends(get_agent), db: AsyncSession = Depends(get_db)):
    batch = (await db.execute(select(XhsAgentBatch).where(XhsAgentBatch.public_id == batch_id, XhsAgentBatch.device_id == agent.id))).scalar_one_or_none()
    if not batch:
        raise HTTPException(404, "采集批次不存在")
    batch.status = body.status
    batch.current_keyword_id = body.current_keyword_id
    batch.completed_keywords = body.completed_keywords
    batch.failed_keywords = body.failed_keywords
    batch.last_progress_at = utcnow()
    if body.error:
        batch.metadata_json = {**(batch.metadata_json or {}), "last_error": body.error}
    if body.status in {"completed", "partial", "failed", "stopped", "risk_blocked"}:
        batch.finished_at = utcnow()
    await db.commit()
    return {"ok": True}


@router.post("/batches/{batch_id}/results")
async def upload_result(batch_id: str, body: UploadBody, agent: XhsCollectorDevice = Depends(get_agent)):
    try:
        return await asyncio.to_thread(
            ingest_agent_result, device_id=agent.id, batch_public_id=batch_id,
            keyword_id=body.keyword_id, idempotency_key=body.idempotency_key,
            payload=body.model_dump(),
        )
    except AgentIngestionConflict as exc:
        raise HTTPException(409, str(exc))
    except ValueError as exc:
        raise HTTPException(400, str(exc))


@router.post("/commands/{command_id}/status")
async def update_command(command_id: str, body: CommandStatusBody, agent: XhsCollectorDevice = Depends(get_agent), db: AsyncSession = Depends(get_db)):
    command = (await db.execute(select(XhsAgentCommand).where(XhsAgentCommand.public_id == command_id, XhsAgentCommand.device_id == agent.id))).scalar_one_or_none()
    if not command:
        raise HTTPException(404, "命令不存在")
    command.status = body.status
    command.result = body.result
    command.error_message = body.error
    now = utcnow()
    if body.status == "delivered": command.delivered_at = now
    if body.status == "running": command.started_at = now
    if body.status in {"succeeded", "failed", "cancelled"}: command.finished_at = now
    await db.commit()
    return {"ok": True}


@admin_router.get("/agent/devices")
async def list_devices(_admin: User = Depends(require_admin_permission("monitoring:read")), db: AsyncSession = Depends(get_db)):
    await _close_stale_batches(db)
    devices = (await db.scalars(select(XhsCollectorDevice).order_by(desc(XhsCollectorDevice.id)))).all()
    batches = (await db.scalars(select(XhsAgentBatch).order_by(desc(XhsAgentBatch.id)).limit(20))).all()
    return {
        "devices": [_device_payload(item, manager.connected(item.id)) for item in devices],
        "batches": [{
            "id": item.public_id, "device_id": next((d.public_id for d in devices if d.id == item.device_id), None),
            "mode": item.mode, "status": item.status, "schedule_date": item.schedule_date.isoformat(),
            "total_keywords": item.total_keywords, "completed_keywords": item.completed_keywords,
            "failed_keywords": item.failed_keywords, "last_progress_at": item.last_progress_at.isoformat() if item.last_progress_at else None,
            "error": (item.metadata_json or {}).get("last_error"),
        } for item in batches],
    }


@admin_router.post("/agent/commands", status_code=202)
async def create_command(body: CommandBody, admin: User = Depends(require_admin_permission("tasks:retry")), db: AsyncSession = Depends(get_db)):
    if body.command_type not in COMMAND_TYPES:
        raise HTTPException(400, "不支持的本地采集命令")
    device = (await db.execute(select(XhsCollectorDevice).where(XhsCollectorDevice.public_id == body.device_id, XhsCollectorDevice.enabled.is_(True)))).scalar_one_or_none()
    if not device:
        raise HTTPException(404, "本地采集节点不存在")
    if not manager.connected(device.id):
        raise HTTPException(409, "本地采集节点当前离线，未创建命令")
    if body.command_type == "test_keyword" and device.cookie_status != "valid":
        raise HTTPException(409, "本地 Cookie 需要重新扫码或完成人机验证后才能采集")
    payload: dict[str, Any] = {}
    if body.command_type == "test_keyword":
        latest_progress = await db.scalar(
            select(XhsAgentBatch.last_progress_at)
            .where(XhsAgentBatch.device_id == device.id)
            .order_by(desc(XhsAgentBatch.last_progress_at))
            .limit(1)
        )
        retry_at = latest_progress + timedelta(minutes=MANUAL_RETRY_GAP_MINUTES) if latest_progress else None
        if retry_at and retry_at > utcnow():
            remaining = max(1, int((retry_at - utcnow()).total_seconds() / 60) + 1)
            raise HTTPException(409, f"为降低小红书风控风险，请等待约 {remaining} 分钟后再重新执行")
        keyword = await db.get(XhsKeyword, body.keyword_id)
        if not keyword or not keyword.enabled:
            raise HTTPException(404, "关键词不存在或已停用")
        payload = {"keyword_id": keyword.id, "keyword": keyword.keyword}
    command = XhsAgentCommand(
        device_id=device.id, command_type=body.command_type, payload=payload,
        requested_by_user_id=admin.id, expires_at=utcnow() + timedelta(minutes=10),
    )
    db.add(command)
    await db.commit()
    await db.refresh(command)
    delivered = await manager.send_command(device.id, command)
    if delivered:
        command.status = "delivered"
        command.delivered_at = utcnow()
        await db.commit()
    return {"command_id": command.public_id, "status": command.status}


@admin_router.get("/agent/commands/{command_id}")
async def get_command(command_id: str, _admin: User = Depends(require_admin_permission("monitoring:read")), db: AsyncSession = Depends(get_db)):
    command = (await db.execute(select(XhsAgentCommand).where(XhsAgentCommand.public_id == command_id))).scalar_one_or_none()
    if not command:
        raise HTTPException(404, "本地采集命令不存在")
    return {
        "id": command.public_id, "command_type": command.command_type,
        "status": command.status, "result": command.result or {},
        "error": command.error_message,
    }


@admin_router.delete("/agent/devices/{device_id}")
async def revoke_device(device_id: str, _admin: User = Depends(get_current_super_admin_user), db: AsyncSession = Depends(get_db)):
    device = (await db.execute(select(XhsCollectorDevice).where(XhsCollectorDevice.public_id == device_id))).scalar_one_or_none()
    if not device:
        raise HTTPException(404, "本地采集节点不存在")
    device.enabled = False
    device.current_status = "revoked"
    await db.commit()
    return {"revoked": True}


@router.websocket("/ws")
async def agent_websocket(websocket: WebSocket):
    authorization = websocket.headers.get("authorization")
    async with AsyncSessionLocal() as db:
        try:
            device = await _agent_from_token(db, authorization)
        except HTTPException:
            await websocket.close(code=4401)
            return
        device_id = device.id
        await manager.connect(device_id, websocket)
        now = utcnow()
        device.current_status = "online"
        device.last_connected_at = now
        device.last_seen_at = now
        await db.commit()
        queued = (await db.scalars(select(XhsAgentCommand).where(XhsAgentCommand.device_id == device_id, XhsAgentCommand.status == "queued", XhsAgentCommand.expires_at > now).order_by(XhsAgentCommand.id))).all()
        for command in queued:
            await websocket.send_json({"type": "command", "command": _command_payload(command)})
            command.status = "delivered"
            command.delivered_at = utcnow()
        await db.commit()
    try:
        while True:
            message = await websocket.receive_json()
            if message.get("type") == "ping":
                async with AsyncSessionLocal() as db:
                    device = await db.get(XhsCollectorDevice, device_id)
                    if device:
                        device.last_seen_at = utcnow()
                        device.current_status = str(message.get("status") or "idle")[:30]
                        device.current_keyword = str(message.get("current_keyword") or "")[:120] or None
                        await db.commit()
                await websocket.send_json({"type": "pong", "server_time": utcnow().isoformat()})
            else:
                await websocket.send_json({"type": "ack"})
    except WebSocketDisconnect:
        pass
    finally:
        disconnected = await manager.disconnect(device_id, websocket)
        if disconnected:
            async with AsyncSessionLocal() as db:
                device = await db.get(XhsCollectorDevice, device_id)
                if device and device.current_status != "revoked":
                    device.current_status = "offline"
                    device.last_disconnected_at = utcnow()
                    await db.commit()
