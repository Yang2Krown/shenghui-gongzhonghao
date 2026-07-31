"""飞书商单 brief 接入 API。

飞书设备码授权 + 读链接 + AI 结构化总结。原生飞书 OAuth，token 存库按 user_id 隔离。
- 授权：POST /feishu/auth/start → 返回授权链接；后台轮询完成后写入 token。前端轮询 GET /feishu/auth/status。
- 读取：POST /feishu/brief/read（飞书链接 / 粘贴文本）、POST /feishu/brief/upload（上传文件）
- 总结：POST /feishu/brief/summarize → StructuredBrief（可直接喂 practical 流程）
"""

import logging
from datetime import timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_current_user
from app.core.rate_limit import limit_ai_generation, limit_file_upload, limit_link_extract
from app.core.upload_security import UploadSecurityError, validate_document_upload
from app.core.background import spawn
from app.core.timezone import utcnow
from app.db.session import get_db, AsyncSessionLocal
from app.models.user import User
from app.models.feishu_auth import FeishuAuth
from app.schemas.brief import (
    StructuredBrief,
    FeishuAuthStartResponse,
    FeishuAuthStatusResponse,
    BriefReadRequest,
    BriefReadResponse,
    BriefSummarizeRequest,
)
from app.services.feishu.client import feishu_client, FeishuError
from app.services.feishu.summarizer import summarize_brief
from app.utils.file_extractor import extract_text, UnsupportedFileType

logger = logging.getLogger(__name__)
router = APIRouter()


# ── 辅助 ─────────────────────────────────────────────────

async def _get_or_create_auth(db: AsyncSession, user_id: int) -> FeishuAuth:
    result = await db.execute(select(FeishuAuth).where(FeishuAuth.user_id == user_id))
    auth = result.scalar_one_or_none()
    if not auth:
        auth = FeishuAuth(user_id=user_id, status="none")
        db.add(auth)
        await db.commit()
        await db.refresh(auth)
    return auth


def _apply_tokens(auth: FeishuAuth, tok: dict) -> None:
    """把 token 响应写进绑定记录。"""
    auth.access_token = tok.get("access_token")
    if tok.get("refresh_token"):
        auth.refresh_token = tok["refresh_token"]
    if tok.get("expires_in"):
        auth.token_expires_at = utcnow() + timedelta(seconds=int(tok["expires_in"]) - 60)
    if tok.get("refresh_token_expires_in"):
        auth.refresh_expires_at = utcnow() + timedelta(seconds=int(tok["refresh_token_expires_in"]) - 60)
    if tok.get("scope"):
        auth.scopes = tok["scope"]


async def _complete_auth_bg(user_id: int, device_code: str, interval: int, expires_in: int) -> None:
    """后台轮询直到用户在浏览器完成授权，成功后回写 token + 身份。"""
    try:
        tok = await feishu_client.wait_for_authorization(device_code, interval, expires_in)
        info = await feishu_client.get_user_info(tok["access_token"])
        async with AsyncSessionLocal() as db:
            auth = await _get_or_create_auth(db, user_id)
            if auth.status != "pending" or auth.device_code != device_code:
                logger.info(f"飞书授权已取消或被新授权替代，忽略旧轮询结果 user={user_id}")
                return
            _apply_tokens(auth, tok)
            auth.feishu_user_name = info.get("name")
            auth.feishu_open_id = info.get("open_id")
            auth.status = "valid"
            auth.device_code = None
            auth.last_error = None
            auth.authorized_at = utcnow()
            await db.commit()
        logger.info(f"飞书授权成功 user={user_id} feishu={info.get('name')}")
    except Exception as e:
        logger.error(f"飞书授权完成失败 user={user_id}: {e}", exc_info=True)
        async with AsyncSessionLocal() as db:
            auth = await _get_or_create_auth(db, user_id)
            if auth.status != "pending" or auth.device_code != device_code:
                logger.info(f"飞书授权已取消或被新授权替代，忽略旧轮询错误 user={user_id}")
                return
            auth.status = "none"
            auth.device_code = None
            auth.last_error = str(e)[:500]
            await db.commit()


async def _valid_access_token(db: AsyncSession, auth: FeishuAuth) -> str:
    """返回可用的 access_token，必要时用 refresh_token 续期并落库。"""
    if auth.access_token and auth.token_expires_at and auth.token_expires_at > utcnow():
        return auth.access_token
    if not auth.refresh_token:
        raise HTTPException(status_code=403, detail="飞书授权已失效，请重新连接飞书")
    try:
        tok = await feishu_client.refresh(auth.refresh_token)
    except FeishuError as e:
        auth.status = "expired"
        auth.last_error = str(e)[:500]
        await db.commit()
        raise HTTPException(status_code=403, detail="飞书授权已过期，请重新连接飞书")
    _apply_tokens(auth, tok)
    await db.commit()
    return auth.access_token


# ── 授权 ─────────────────────────────────────────────────

@router.post("/auth/start", response_model=FeishuAuthStartResponse)
async def auth_start(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    """发起飞书设备码授权，返回让用户打开的授权链接。"""
    try:
        dev = await feishu_client.device_authorization()
    except FeishuError as e:
        raise HTTPException(status_code=502, detail=f"发起飞书授权失败：{e}")

    verify = dev.get("verification_uri_complete") or dev.get("verification_uri")
    if not verify or not dev.get("device_code"):
        raise HTTPException(status_code=502, detail="飞书未返回授权链接")

    auth = await _get_or_create_auth(db, current_user.id)
    auth.status = "pending"
    auth.device_code = dev["device_code"]
    auth.last_error = None
    await db.commit()

    spawn(_complete_auth_bg(
        current_user.id, dev["device_code"],
        int(dev.get("interval", 5)), int(dev.get("expires_in", 600)),
    ))

    return FeishuAuthStartResponse(
        verification_url=verify,
        expires_in=dev.get("expires_in"),
        status="pending",
    )


@router.get("/auth/status", response_model=FeishuAuthStatusResponse)
async def auth_status_endpoint(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    """查询当前用户的飞书授权状态（前端轮询用）。"""
    result = await db.execute(select(FeishuAuth).where(FeishuAuth.user_id == current_user.id))
    auth = result.scalar_one_or_none()
    if not auth:
        return FeishuAuthStatusResponse(status="none")
    return FeishuAuthStatusResponse(
        status=auth.status,
        feishu_user_name=auth.feishu_user_name,
        feishu_open_id=auth.feishu_open_id,
        last_error=auth.last_error,
        authorized_at=auth.authorized_at.isoformat() if auth.authorized_at else None,
    )


@router.delete("/auth", response_model=dict)
async def auth_logout(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    """解除飞书绑定，或取消进行中的授权。"""
    result = await db.execute(select(FeishuAuth).where(FeishuAuth.user_id == current_user.id))
    auth = result.scalar_one_or_none()
    if auth:
        auth.status = "none"
        auth.device_code = None
        auth.feishu_user_name = None
        auth.feishu_open_id = None
        auth.access_token = None
        auth.refresh_token = None
        auth.token_expires_at = None
        auth.refresh_expires_at = None
        auth.authorized_at = None
        auth.last_error = None
        await db.commit()
    return {"code": 200, "message": "已解除飞书绑定"}


# ── 读取 brief 原文 ───────────────────────────────────────

@router.post("/brief/read", response_model=BriefReadResponse)
async def brief_read(
    body: BriefReadRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(limit_link_extract),
) -> Any:
    """读取 brief 原文：飞书链接（需已授权）或直接粘贴文本。"""
    if body.source_type == "text":
        return BriefReadResponse(title="", raw_text=body.value.strip())

    if body.source_type == "feishu_link":
        result = await db.execute(select(FeishuAuth).where(FeishuAuth.user_id == current_user.id))
        auth = result.scalar_one_or_none()
        if not auth or auth.status != "valid":
            raise HTTPException(status_code=403, detail="尚未完成飞书授权，请先连接飞书")
        token = await _valid_access_token(db, auth)
        try:
            doc = await feishu_client.read_document(token, body.value.strip())
        except FeishuError as e:
            raise HTTPException(status_code=502, detail=f"读取飞书文档失败：{e}")
        return BriefReadResponse(title=doc.get("title", ""), raw_text=doc.get("content", ""))

    raise HTTPException(status_code=400, detail=f"不支持的来源类型：{body.source_type}")


@router.post("/brief/upload", response_model=BriefReadResponse)
async def brief_upload(
    file: UploadFile = File(...),
    current_user: User = Depends(limit_file_upload),
) -> Any:
    """上传 brief 文件（docx/pdf/txt 等），提取纯文本。"""
    data = await file.read()
    try:
        safe = validate_document_upload(
            filename=file.filename,
            data=data,
            max_size=10 * 1024 * 1024,
        )
    except UploadSecurityError as e:
        raise HTTPException(status_code=400, detail=str(e))
    try:
        text = await extract_text(
            filename=file.filename or "upload",
            data=safe.data,
            content_type=safe.content_type,
        )
    except UnsupportedFileType as e:
        raise HTTPException(status_code=400, detail=f"不支持的文件类型：{e}")
    except Exception as e:
        logger.error(f"brief 文件解析失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="文件解析失败")
    if not text or not text.strip():
        raise HTTPException(
            status_code=400,
            detail="未能从文件中提取到文字内容（可能是空白文件、扫描件过于模糊或文件已加密），请上传文字版 PDF/Word，或改用粘贴文本",
        )
    return BriefReadResponse(title=file.filename or "", raw_text=text)


# ── 结构化总结 ────────────────────────────────────────────

@router.post("/brief/summarize", response_model=StructuredBrief)
async def brief_summarize(
    body: BriefSummarizeRequest,
    current_user: User = Depends(limit_ai_generation),
) -> Any:
    """把 brief 原文总结成结构化 StructuredBrief。"""
    data = await summarize_brief(body.raw_text, title=body.title)
    return StructuredBrief(**data)
