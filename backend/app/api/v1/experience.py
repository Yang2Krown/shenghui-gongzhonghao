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
from app.schemas.content_version import (
    EXPERIENCE_SOURCE_TYPES,
    EXPERIENCE_STATUSES,
    ExperienceCardCreate,
    ExperienceCardDraftCreate,
    ExperienceMergeConfirmRequest,
    ExperienceMergePreviewRequest,
    ExperienceCardUpdate,
)
from app.services.experience_merge_service import (
    ExperienceMergeError,
    find_overlapping_cards,
    find_similar_cards,
    merge_experiences,
    preview_merge_experiences,
)
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


async def _load_card(
    db: AsyncSession,
    card_id: int,
) -> Optional[ExperienceCard]:
    return (await db.execute(
        select(ExperienceCard)
        .where(ExperienceCard.id == card_id)
        .options(
            selectinload(ExperienceCard.creator),
            selectinload(ExperienceCard.creation),
            selectinload(ExperienceCard.suggestion),
        )
    )).scalar_one_or_none()


async def _card_payload_for_user(
    db: AsyncSession,
    current_user: User,
    card: ExperienceCard,
) -> dict:
    source_accessible = None
    if card.creation is not None:
        source_accessible = await can_access_creation(db, current_user, card.creation)
    return build_card_payload(
        card,
        source_creation=card.creation,
        creator=card.creator,
        suggestion=card.suggestion,
        source_accessible=source_accessible,
    )


@router.get("", response_model=dict)
async def list_experience_cards(
    q: Optional[str] = Query(None, max_length=200),
    category: Optional[str] = Query(None, max_length=50),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    source_type: Optional[str] = Query(None, max_length=20),
    card_status: str = Query("confirmed", alias="status", max_length=20),
) -> Any:
    await _require_experience_access(db, current_user)
    # 这些参数在单元测试中也会直接调用路由函数；FastAPI 的 Query 默认
    # 对象需要在这种调用方式下还原成业务默认值。
    if not isinstance(source_type, (str, type(None))):
        source_type = None
    if not isinstance(card_status, str):
        card_status = "confirmed"
    if source_type and len(source_type) > 20:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="经验来源类型过长")
    if len(card_status) > 20:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="经验状态过长")
    if card_status not in EXPERIENCE_STATUSES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="经验状态不合法")
    if source_type and source_type not in EXPERIENCE_SOURCE_TYPES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="经验来源类型不合法")
    rows, total, search_mode, embedding_available = await load_experience_cards(
        db,
        q=q,
        category=category,
        page=page,
        page_size=page_size,
        source_type=source_type,
        status=card_status,
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
            "status": card_status,
            "source_type": source_type,
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
        source_meta=experience_in.source_meta,
        suggestion_id=experience_in.suggestion_id,
        created_by=current_user.id,
        status="confirmed",
    )
    embedding_result = await enqueue_embedding(card, db)
    card = await _load_card(db, card.id)
    assert card is not None
    return {
        "code": 200,
        "message": "经验卡片已保存",
        "data": {
            "card": await _card_payload_for_user(db, current_user, card),
            "embedding": embedding_result,
        },
    }


@router.post("/drafts", response_model=dict)
async def create_experience_draft(
    draft_in: ExperienceCardDraftCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    """保存上传或会议提炼出的待确认经验，不直接进入正式经验库。"""

    await _require_experience_access(db, current_user)
    card = await create_experience_card(
        db,
        title=draft_in.title,
        content=draft_in.content,
        category=draft_in.category,
        source_type=draft_in.source_type,
        source_meta=draft_in.source_meta,
        created_by=current_user.id,
        status="pending",
    )
    loaded = await _load_card(db, card.id)
    assert loaded is not None
    return {
        "code": 200,
        "message": "经验已进入待确认",
        "data": {"card": await _card_payload_for_user(db, current_user, loaded)},
    }


@router.post("/overlaps", response_model=dict)
async def scan_experience_overlaps(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    """扫描正式经验中语义重合的分组。"""

    await _require_experience_access(db, current_user)
    groups = await find_overlapping_cards(db)
    return {
        "code": 200,
        "message": "重合经验扫描完成",
        "data": {"groups": groups, "group_count": len(groups)},
    }


@router.get("/{card_id}/similar", response_model=dict)
async def list_similar_experiences(
    card_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    """返回与指定经验语义相近的正式经验。"""

    await _require_experience_access(db, current_user)
    items = await find_similar_cards(db, card_id)
    return {
        "code": 200,
        "message": "相似经验获取成功",
        "data": {"items": items},
    }


@router.post("/merge/preview", response_model=dict)
async def preview_experience_merge(
    merge_in: ExperienceMergePreviewRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    """用 LLM 生成多条重合经验的合并草稿，不写库。"""

    await _require_experience_access(db, current_user)
    try:
        preview = await preview_merge_experiences(db, merge_in.source_ids)
    except ExperienceMergeError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return {"code": 200, "message": "合并草稿已生成", "data": preview}


@router.post("/merge", response_model=dict)
async def confirm_experience_merge(
    merge_in: ExperienceMergeConfirmRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    """确认合并：保留一条正式经验，其余来源标记为已合并。"""

    await _require_experience_access(db, current_user)
    try:
        survivor = await merge_experiences(
            db,
            merge_in.source_ids,
            surviving_id=merge_in.surviving_id,
            title=merge_in.title,
            content=merge_in.content,
            category=merge_in.category,
        )
    except ExperienceMergeError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    loaded = await _load_card(db, survivor.id)
    assert loaded is not None
    return {
        "code": 200,
        "message": "经验已合并",
        "data": {"card": await _card_payload_for_user(db, current_user, loaded)},
    }


@router.get("/{card_id}", response_model=dict)
async def get_experience_card(
    card_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    await _require_experience_access(db, current_user)
    card = await _load_card(db, card_id)
    if card is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="经验卡片不存在")
    return {
        "code": 200,
        "message": "经验卡片获取成功",
        "data": {"card": await _card_payload_for_user(db, current_user, card)},
    }


@router.patch("/{card_id}", response_model=dict)
async def update_experience_card(
    card_id: int,
    update_in: ExperienceCardUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    await _require_experience_access(db, current_user)
    card = await _load_card(db, card_id)
    if card is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="经验卡片不存在")
    if card.status != "pending":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="只有待确认经验可以修改")
    changes = update_in.model_dump(exclude_unset=True)
    for field, value in changes.items():
        setattr(card, field, value)
    if "content" in changes:
        card.embedding = None
        card.embedding_status = "waiting"
        card.embedding_error = None
        card.embedding_task_id = None
    await db.commit()
    loaded = await _load_card(db, card.id)
    assert loaded is not None
    return {
        "code": 200,
        "message": "待确认经验已更新",
        "data": {"card": await _card_payload_for_user(db, current_user, loaded)},
    }


@router.post("/{card_id}/confirm", response_model=dict)
async def confirm_experience_card(
    card_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    await _require_experience_access(db, current_user)
    card = await _load_card(db, card_id)
    if card is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="经验卡片不存在")
    if card.status != "pending":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="当前经验不在待确认状态")
    card.status = "confirmed"
    await db.commit()
    embedding_result = await enqueue_embedding(card, db)
    loaded = await _load_card(db, card.id)
    assert loaded is not None
    return {
        "code": 200,
        "message": "经验已确认并进入正式经验库",
        "data": {
            "card": await _card_payload_for_user(db, current_user, loaded),
            "embedding": embedding_result,
        },
    }


@router.post("/{card_id}/reject", response_model=dict)
async def reject_experience_card(
    card_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    await _require_experience_access(db, current_user)
    card = await _load_card(db, card_id)
    if card is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="经验卡片不存在")
    if card.status != "pending":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="只有待确认经验可以退回")
    card.status = "rejected"
    await db.commit()
    return {
        "code": 200,
        "message": "经验已退回",
        "data": {"card_id": card.id, "status": card.status},
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
