"""初稿诊断入口：上传/粘贴初稿，复用已确认经验并保存诊断记录。"""

from __future__ import annotations

import logging
import json
from datetime import datetime
from typing import Any, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.product_access import is_admin_user
from app.core.rate_limit import enforce_rate_limit, rule_from_setting, user_actor
from app.core.security import get_current_user
from app.core.upload_security import UploadSecurityError, validate_document_upload
from app.db.session import get_db
from app.models.content_version import ExperienceCard
from app.models.draft_diagnosis import DraftDiagnosis
from app.models.user import User
from app.schemas.draft_diagnosis import (
    DraftDiagnosisCreate,
    DraftDiagnosisExperienceDraftCreate,
    DraftDiagnosisTitleUpdate,
    MAX_DRAFT_DIAGNOSIS_CHARS,
)
from app.services.draft_diagnosis_service import (
    DraftDiagnosisAnalysisError,
    diagnose_draft,
    normalize_brief_context,
)
from app.services.experience_service import (
    build_card_payload,
    create_experience_card,
    enqueue_embedding,
    match_experience_cards,
)
from app.services.team_service import can_access_team_collaboration
from app.utils.file_extractor import UnsupportedFileType, extract_text

logger = logging.getLogger(__name__)
router = APIRouter()

MAX_DRAFT_DIAGNOSIS_UPLOAD_SIZE = 20 * 1024 * 1024


async def _require_diagnosis_access(db: AsyncSession, user: User) -> None:
    if not await can_access_team_collaboration(db, user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="仅在职员工和管理员可访问初稿诊断",
        )


def _iso(value: Optional[datetime]) -> Optional[str]:
    return value.isoformat() if value else None


def _user_payload(user: Optional[User]) -> Optional[dict]:
    if user is None:
        return None
    return {
        "id": user.id,
        "username": user.username,
        "full_name": user.full_name,
    }


def _clean_optional(value: Optional[str], max_length: int) -> Optional[str]:
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned[:max_length] if cleaned else None


def _parse_brief_context_json(value: Optional[str]) -> Optional[dict]:
    if not value or not value.strip():
        return None
    try:
        parsed = json.loads(value)
    except (TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="商单 brief 上下文格式不正确，请重新读取并解析",
        ) from exc
    if not isinstance(parsed, dict):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="商单 brief 上下文格式不正确，请重新读取并解析",
        )
    return parsed


def _diagnosis_payload(
    diagnosis: DraftDiagnosis,
    *,
    include_content: bool = True,
    matched_cards: Optional[list[dict]] = None,
) -> dict:
    return {
        "id": diagnosis.id,
        "title": diagnosis.title,
        "source_type": diagnosis.source_type,
        "source_filename": diagnosis.source_filename,
        "content": diagnosis.content_text if include_content else None,
        "content_char_count": diagnosis.content_char_count,
        "content_truncated": bool(diagnosis.content_truncated),
        "goal": diagnosis.goal,
        "audience": diagnosis.audience,
        "channel": diagnosis.channel,
        "brief_context": diagnosis.brief_context,
        "status": diagnosis.status,
        "analysis": diagnosis.analysis,
        "matched_experience_ids": list(diagnosis.matched_experience_ids or []),
        "matched_experiences": matched_cards if matched_cards is not None else list(diagnosis.matched_experiences or []),
        "analysis_error": diagnosis.analysis_error,
        "created_by": diagnosis.created_by,
        "created_by_user": _user_payload(diagnosis.creator),
        "created_at": _iso(diagnosis.created_at),
        "updated_at": _iso(diagnosis.updated_at),
    }


async def _load_diagnosis(
    db: AsyncSession,
    diagnosis_id: int,
) -> Optional[DraftDiagnosis]:
    return (await db.execute(
        select(DraftDiagnosis)
        .where(DraftDiagnosis.id == diagnosis_id)
        .options(selectinload(DraftDiagnosis.creator))
    )).scalar_one_or_none()


async def _load_matched_cards(
    db: AsyncSession,
    diagnosis: DraftDiagnosis,
    current_user: User,
) -> list[dict]:
    ids = []
    for raw_id in diagnosis.matched_experience_ids or []:
        try:
            card_id = int(raw_id)
        except (TypeError, ValueError):
            continue
        if card_id not in ids:
            ids.append(card_id)
    if not ids:
        return list(diagnosis.matched_experiences or [])

    cards = (await db.execute(
        select(ExperienceCard)
        .where(ExperienceCard.id.in_(ids))
        .options(
            selectinload(ExperienceCard.creator),
            selectinload(ExperienceCard.creation),
            selectinload(ExperienceCard.suggestion),
        )
    )).scalars().all()
    by_id = {card.id: card for card in cards}
    snapshots = {
        int(item.get("id")): item
        for item in (diagnosis.matched_experiences or [])
        if isinstance(item, dict) and str(item.get("id", "")).isdigit()
    }
    result: list[dict] = []
    for card_id in ids:
        card = by_id.get(card_id)
        if card is None:
            # 经验可能已经被清理；保留诊断当时的快照，避免历史结果失去依据。
            if card_id in snapshots:
                result.append(snapshots[card_id])
            continue
        snapshot = snapshots.get(card_id, {})
        result.append(build_card_payload(
            card,
            creator=card.creator,
            source_creation=card.creation,
            suggestion=card.suggestion,
            similarity=snapshot.get("similarity"),
            match_method=snapshot.get("match_method", "diagnosis"),
        ))
    return result


async def _run_diagnosis(
    db: AsyncSession,
    *,
    current_user: User,
    content: str,
    title: Optional[str],
    source_type: str,
    source_filename: Optional[str],
    goal: Optional[str],
    audience: Optional[str],
    channel: Optional[str],
    brief_context: Optional[dict],
) -> dict:
    content = content.strip()
    if not content:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="初稿内容不能为空")
    if len(content) > MAX_DRAFT_DIAGNOSIS_CHARS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"初稿内容不能超过 {MAX_DRAFT_DIAGNOSIS_CHARS:,} 字符",
        )

    brief_context = normalize_brief_context(brief_context)
    diagnosis = DraftDiagnosis(
        title=_clean_optional(title, 200) or "未命名初稿诊断",
        source_type=source_type,
        source_filename=_clean_optional(source_filename, 500),
        content_text=content,
        content_char_count=len(content),
        content_truncated=False,
        goal=_clean_optional(goal, 5_000),
        audience=_clean_optional(audience, 500),
        channel=_clean_optional(channel, 100),
        brief_context=brief_context,
        status="processing",
        matched_experience_ids=[],
        matched_experiences=[],
        created_by=current_user.id,
    )
    db.add(diagnosis)
    await db.commit()
    await db.refresh(diagnosis)

    query_text = "\n".join(
        value
        for value in (
            diagnosis.goal,
            diagnosis.audience,
            diagnosis.channel,
            json.dumps(brief_context, ensure_ascii=False) if brief_context else None,
            content[:8_000],
        )
        if value
    )
    try:
        rows, _search_mode, _embedding_available = await match_experience_cards(
            db,
            query_text,
            page_size=8,
        )
        matched_snapshots = []
        for card, similarity, match_method in rows:
            matched_snapshots.append({
                "id": card.id,
                "title": card.title,
                "category": card.category,
                "content": card.content,
                "similarity": round(similarity, 6) if similarity is not None else None,
                "match_method": match_method,
            })
        analysis = await diagnose_draft(
            content,
            title=diagnosis.title,
            goal=diagnosis.goal,
            audience=diagnosis.audience,
            channel=diagnosis.channel,
            brief_context=diagnosis.brief_context,
            matched_experiences=matched_snapshots,
        )
    except DraftDiagnosisAnalysisError as exc:
        await db.rollback()
        failed = await _load_diagnosis(db, diagnosis.id)
        if failed is not None:
            failed.status = "failed"
            failed.analysis_error = str(exc)[:2_000]
            await db.commit()
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
    except Exception as exc:
        await db.rollback()
        failed = await _load_diagnosis(db, diagnosis.id)
        if failed is not None:
            failed.status = "failed"
            failed.analysis_error = "初稿诊断暂时失败，请稍后重试"
            await db.commit()
        logger.warning("初稿诊断失败 diagnosis_id=%s: %s", diagnosis.id, exc, exc_info=True)
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="初稿诊断暂时失败，请稍后重试") from exc

    diagnosis.status = "completed"
    diagnosis.analysis = analysis
    diagnosis.matched_experience_ids = [item["id"] for item in matched_snapshots]
    diagnosis.matched_experiences = matched_snapshots
    diagnosis.analysis_error = None
    await db.commit()
    loaded = await _load_diagnosis(db, diagnosis.id)
    assert loaded is not None
    matched_cards = await _load_matched_cards(db, loaded, current_user)
    return {
        "code": 200,
        "message": "初稿诊断完成",
        "data": {
            "diagnosis": _diagnosis_payload(
                loaded,
                include_content=True,
                matched_cards=matched_cards,
            ),
            "match_count": len(matched_cards),
        },
    }


@router.get("", response_model=dict)
async def list_draft_diagnoses(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    await _require_diagnosis_access(db, current_user)
    query = (
        select(DraftDiagnosis)
        .where(DraftDiagnosis.created_by == current_user.id)
        .options(selectinload(DraftDiagnosis.creator))
        .order_by(DraftDiagnosis.created_at.desc(), DraftDiagnosis.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    rows = (await db.execute(query)).scalars().all()
    return {
        "code": 200,
        "message": "初稿诊断记录获取成功",
        "data": {
            "items": [
                _diagnosis_payload(item, include_content=False)
                for item in rows
            ],
            "page": page,
            "page_size": page_size,
            "has_more": len(rows) == page_size,
        },
    }


@router.post("", response_model=dict)
async def create_pasted_draft_diagnosis(
    diagnosis_in: DraftDiagnosisCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    await _require_diagnosis_access(db, current_user)
    return await _run_diagnosis(
        db,
        current_user=current_user,
        content=diagnosis_in.content,
        title=diagnosis_in.title,
        source_type="pasted",
        source_filename=None,
        goal=diagnosis_in.goal,
        audience=diagnosis_in.audience,
        channel=diagnosis_in.channel,
        brief_context=diagnosis_in.brief_context,
    )


@router.post("/upload", response_model=dict)
async def create_uploaded_draft_diagnosis(
    request: Request,
    file: UploadFile = File(...),
    title: Optional[str] = Form(None),
    goal: Optional[str] = Form(None),
    audience: Optional[str] = Form(None),
    channel: Optional[str] = Form(None),
    brief_context_json: Optional[str] = Form(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    await _require_diagnosis_access(db, current_user)
    await enforce_rate_limit(
        [rule_from_setting(
            "file:upload:user",
            settings.RATE_LIMIT_FILE_UPLOAD_USER,
            user_actor(current_user.id),
        )],
        request=request,
    )
    if not file.filename:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="文件名不能为空")
    data = await file.read()
    try:
        safe = validate_document_upload(
            filename=file.filename,
            data=data,
            max_size=MAX_DRAFT_DIAGNOSIS_UPLOAD_SIZE,
        )
        content = await extract_text(
            filename=file.filename,
            data=safe.data,
            content_type=safe.content_type,
        )
    except UploadSecurityError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except UnsupportedFileType as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except Exception as exc:
        logger.warning("初稿诊断文件解析失败 filename=%s: %s", file.filename, exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="文件解析失败，请上传未加密的文字版 PDF/Word",
        ) from exc
    content = (content or "").strip()
    if not content:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="未能提取文字，请上传文字版 PDF/Word，扫描件或加密文件请先转成可复制文本",
        )
    return await _run_diagnosis(
        db,
        current_user=current_user,
        content=content,
        title=title or file.filename,
        source_type="file",
        source_filename=file.filename,
        goal=goal,
        audience=audience,
        channel=channel,
        brief_context=_parse_brief_context_json(brief_context_json),
    )


@router.get("/{diagnosis_id}", response_model=dict)
async def get_draft_diagnosis(
    diagnosis_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    await _require_diagnosis_access(db, current_user)
    diagnosis = await _load_diagnosis(db, diagnosis_id)
    if diagnosis is None or diagnosis.created_by != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="初稿诊断不存在")
    matched_cards = await _load_matched_cards(db, diagnosis, current_user)
    return {
        "code": 200,
        "message": "初稿诊断获取成功",
        "data": {
            "diagnosis": _diagnosis_payload(
                diagnosis,
                include_content=True,
                matched_cards=matched_cards,
            )
        },
    }


def _can_manage_diagnosis(diagnosis: DraftDiagnosis, user: User) -> bool:
    """只有诊断创建者或管理员可以修改标题 / 删除记录。"""

    return bool(diagnosis.created_by == user.id or is_admin_user(user))


@router.put("/{diagnosis_id}/title", response_model=dict)
async def update_draft_diagnosis_title(
    diagnosis_id: int,
    title_in: DraftDiagnosisTitleUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    """更新初稿诊断标题，不影响已完成的分析产物。"""

    await _require_diagnosis_access(db, current_user)
    diagnosis = await _load_diagnosis(db, diagnosis_id)
    if diagnosis is None or not _can_manage_diagnosis(diagnosis, current_user):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="初稿诊断不存在")

    diagnosis.title = title_in.title
    await db.commit()
    await db.refresh(diagnosis)
    return {
        "code": 200,
        "message": "初稿诊断标题已更新",
        "data": {"diagnosis": _diagnosis_payload(diagnosis, include_content=False)},
    }


@router.delete("/{diagnosis_id}", response_model=dict)
async def delete_draft_diagnosis(
    diagnosis_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    """删除初稿诊断记录；通过 source_meta 引用它的经验卡片不受影响。"""

    await _require_diagnosis_access(db, current_user)
    diagnosis = await _load_diagnosis(db, diagnosis_id)
    if diagnosis is None or not _can_manage_diagnosis(diagnosis, current_user):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="初稿诊断不存在")

    await db.delete(diagnosis)
    await db.commit()
    return {
        "code": 200,
        "message": "初稿诊断已删除",
        "data": {"diagnosis_id": diagnosis_id},
    }


@router.post("/{diagnosis_id}/experience-drafts", response_model=dict)
async def create_draft_diagnosis_experience(
    diagnosis_id: int,
    draft_in: DraftDiagnosisExperienceDraftCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    """把诊断发现保存为 pending 经验，等待人工修订和确认。"""

    await _require_diagnosis_access(db, current_user)
    diagnosis = await _load_diagnosis(db, diagnosis_id)
    if diagnosis is None or diagnosis.created_by != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="初稿诊断不存在")
    if diagnosis.status != "completed" or not isinstance(diagnosis.analysis, dict):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="只有完成的诊断可以沉淀经验")
    issues = diagnosis.analysis.get("issues") or []
    if draft_in.finding_index >= len(issues):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="诊断问题不存在")
    finding = issues[draft_in.finding_index]
    if not isinstance(finding, dict):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="诊断问题格式不正确")
    title = draft_in.title or finding.get("title") or "来自初稿诊断的经验"
    content = draft_in.content or "\n".join(
        value
        for value in (
            f"问题：{finding.get('problem') or ''}",
            f"证据：{finding.get('evidence') or '正文未提供'}",
            f"建议：{finding.get('recommendation') or ''}",
        )
        if value.strip()
    )
    if not content.strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="诊断问题没有可沉淀内容")
    card = await create_experience_card(
        db,
        title=title,
        content=content,
        category=draft_in.category,
        source_type="review_feedback",
        source_meta={
            "diagnosis_id": diagnosis.id,
            "finding_index": draft_in.finding_index,
            "source_title": diagnosis.title,
        },
        created_by=current_user.id,
        status="pending",
    )
    loaded = (await db.execute(
        select(ExperienceCard)
        .where(ExperienceCard.id == card.id)
        .options(selectinload(ExperienceCard.creator))
    )).scalar_one()
    return {
        "code": 200,
        "message": "诊断发现已进入待确认经验",
        "data": {
            "card": build_card_payload(loaded, creator=loaded.creator),
        },
    }
