"""经验库检索、手动新增和 PDF/Word 解析接口（Phase 1c）。"""

from __future__ import annotations

import logging
from typing import Any, Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.rate_limit import enforce_rate_limit, rule_from_setting, user_actor
from app.core.security import get_current_user
from app.core.upload_security import UploadSecurityError, validate_document_upload
from app.db.session import get_db
from app.models.content_version import ExperienceCard
from app.models.creation import ContentCreation
from app.models.meeting import MeetingSuggestion
from app.models.user import User
from app.schemas.content_version import ExperienceCardCreate
from app.services.experience_service import (
    build_card_payload,
    create_experience_card,
    enqueue_embedding,
    load_experience_cards,
)
from app.services.team_service import can_access_creation, can_access_team_collaboration
from app.utils.file_extractor import UnsupportedFileType, extract_text

logger = logging.getLogger(__name__)
router = APIRouter()

MAX_EXPERIENCE_UPLOAD_SIZE = 20 * 1024 * 1024
MAX_EXPERIENCE_UPLOAD_CHARS = 100_000


async def _require_experience_access(db: AsyncSession, user: User) -> None:
    if not await can_access_team_collaboration(db, user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="仅在职员工和管理员可访问经验库",
        )


async def _load_optional_creation(
    db: AsyncSession,
    user: User,
    creation_id: Optional[int],
) -> Optional[ContentCreation]:
    if creation_id is None:
        return None
    creation = (await db.execute(
        select(ContentCreation).where(ContentCreation.id == creation_id)
    )).scalar_one_or_none()
    if creation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="来源文章不存在")
    if not await can_access_creation(db, user, creation):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权关联来源文章")
    return creation


async def _load_optional_suggestion(
    db: AsyncSession,
    user: User,
    suggestion_id: Optional[int],
    creation_id: Optional[int],
) -> Optional[MeetingSuggestion]:
    if suggestion_id is None:
        return None
    suggestion = (await db.execute(
        select(MeetingSuggestion).where(MeetingSuggestion.id == suggestion_id)
    )).scalar_one_or_none()
    if suggestion is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="关联会议建议不存在")
    if creation_id is not None and suggestion.related_creation_id != creation_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="会议建议未关联当前来源文章")
    if suggestion.related_creation_id is not None:
        await _load_optional_creation(db, user, suggestion.related_creation_id)
    return suggestion


@router.get("", response_model=dict)
async def list_experience_cards(
    q: Optional[str] = Query(None, max_length=200),
    category: Optional[str] = Query(None, max_length=50),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    await _require_experience_access(db, current_user)
    rows, total, search_mode, embedding_available = await load_experience_cards(
        db,
        q=q,
        category=category,
        page=page,
        page_size=page_size,
    )
    items = []
    for card, similarity, match_method in rows:
        source_creation = card.creation
        source_accessible = None
        if source_creation is not None:
            source_accessible = await can_access_creation(db, current_user, source_creation)
        items.append(build_card_payload(
            card,
            source_creation=source_creation,
            creator=card.creator,
            suggestion=card.suggestion,
            similarity=similarity,
            match_method=match_method,
            source_accessible=source_accessible,
        ))
    return {
        "code": 200,
        "message": "经验库获取成功",
        "data": {
            "items": items,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": (total + page_size - 1) // page_size,
            "search_mode": search_mode,
            "embedding_available": embedding_available,
        },
    }


@router.post("", response_model=dict)
async def create_manual_experience(
    experience_in: ExperienceCardCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    await _require_experience_access(db, current_user)
    if experience_in.source_type != "manual":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="手动新增经验的 source_type 必须是 manual")
    await _load_optional_creation(db, current_user, experience_in.creation_id)
    await _load_optional_suggestion(
        db,
        current_user,
        experience_in.suggestion_id,
        experience_in.creation_id,
    )
    card = await create_experience_card(
        db,
        title=experience_in.title,
        content=experience_in.content,
        category=experience_in.category,
        source_type="manual",
        creation_id=experience_in.creation_id,
        version_pair=experience_in.version_pair,
        suggestion_id=experience_in.suggestion_id,
        created_by=current_user.id,
    )
    embedding_result = await enqueue_embedding(card, db)
    card = (await db.execute(
        select(ExperienceCard)
        .where(ExperienceCard.id == card.id)
        .options(
            selectinload(ExperienceCard.creator),
            selectinload(ExperienceCard.creation),
            selectinload(ExperienceCard.suggestion),
        )
    )).scalar_one()
    return {
        "code": 200,
        "message": "经验卡片已保存",
        "data": {
            "card": build_card_payload(
                card,
                source_creation=card.creation,
                creator=card.creator,
                suggestion=card.suggestion,
                source_accessible=(
                    await can_access_creation(db, current_user, card.creation)
                    if card.creation else None
                ),
            ),
            "embedding": embedding_result,
        },
    }


@router.post("/upload", response_model=dict)
async def parse_experience_upload(
    request: Request,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    """解析 PDF/DOCX/TXT/MD，返回可编辑文本，不直接创建经验卡片。"""

    # 先做团队门禁，再读取和解析文件，避免普通用户借上传接口探测内部能力。
    # 仍沿用项目已有的上传限流策略和真实文件签名检查。
    await _require_experience_access(db, current_user)
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
            max_size=MAX_EXPERIENCE_UPLOAD_SIZE,
        )
    except UploadSecurityError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    try:
        extracted = await extract_text(
            filename=file.filename,
            data=safe.data,
            content_type=safe.content_type,
        )
    except UnsupportedFileType as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except Exception as exc:
        logger.warning("经验库上传解析失败 filename=%s: %s", file.filename, exc, exc_info=True)
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="文件解析失败，请上传未加密的文字版 PDF/Word") from exc
    extracted = (extracted or "").strip()
    if not extracted:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="未能提取文字，请上传文字版 PDF/Word，扫描件或加密文件请先转成可复制文本",
        )
    truncated = len(extracted) > MAX_EXPERIENCE_UPLOAD_CHARS
    if truncated:
        extracted = extracted[:MAX_EXPERIENCE_UPLOAD_CHARS]
    return {
        "code": 200,
        "message": "文件解析成功",
        "data": {
            "filename": file.filename,
            "text": extracted,
            "char_count": len(extracted),
            "truncated": truncated,
            "parse_mode": "pdf_or_docx",
        },
    }
