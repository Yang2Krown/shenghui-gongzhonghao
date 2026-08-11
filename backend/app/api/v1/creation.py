import json
from typing import Any, List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from pydantic import BaseModel, Field
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.product_access import is_admin_user
from app.core.security import get_current_user
from app.crud.creation import creation as creation_crud
from app.db.session import get_db
from app.models.user import User
from app.models.creation import ContentCreation
from app.models.generation_record import GenerationRecord
from app.schemas.creation import (
    ContentCreationCreate,
    ContentCreationUpdate,
    ContentCreationResponse,
    ContentCreationListResponse,
    ContentGenerationRequest,
    ContentGenerationResponse
)
from app.services.creation_publication import (
    publication_payload,
    record_creation_publication,
)
from app.services.team_service import (
    can_access_creation,
    can_delete_creation,
    can_edit_creation,
    can_publish_creation,
    is_active_team_user,
)

router = APIRouter()


class CreationPublishedRequest(BaseModel):
    """公众号草稿箱上传成功后的本地状态回写。"""

    platform: str = "wechat_draft"
    external_id: Optional[str] = Field(None, max_length=200)
    external_url: Optional[str] = Field(None, max_length=1000)
    request_key: Optional[str] = Field(None, max_length=100)


def _decode_creation_content(raw: Optional[str]) -> str:
    """兼容旧的纯文本正文和当前保存的 JSON 正文快照。"""
    if not raw:
        return ""
    try:
        value = json.loads(raw)
        if isinstance(value, dict):
            return str(value.get("final_text") or value.get("content") or "")
    except (TypeError, ValueError):
        pass
    return raw


def _append_unique(items: list, seen: set, value: str, payload: dict) -> None:
    value = (value or "").strip()
    if not value or value in seen:
        return
    seen.add(value)
    items.append({**payload, "value": value})


@router.post("", response_model=dict)
async def create_creation(
    creation_in: ContentCreationCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Any:
    """创建新创作"""
    if creation_in.status not in (None, "draft"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="新创作只能从 draft 状态开始",
        )
    # 创建创作记录
    creation = await creation_crud.create(
        db,
        obj_in=creation_in,
        user_id=current_user.id
    )
    
    return {
        "code": 200,
        "message": "创作创建成功",
        "data": ContentCreationResponse.from_orm(creation).dict()
    }


@router.get("", response_model=dict)
async def get_creations(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    status: Optional[str] = Query(None, description="状态筛选"),
    topic_id: Optional[int] = Query(None, description="选题ID筛选")
) -> Any:
    """获取创作列表"""
    if not await is_active_team_user(db, current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="团队账号已停用")
    # 计算偏移量
    skip = (page - 1) * page_size
    
    # 获取创作列表
    creations = await creation_crud.get_accessible(
        db,
        user_id=current_user.id,
        skip=skip,
        limit=page_size,
        status=status,
        topic_id=topic_id,
        include_all=is_admin_user(current_user),
    )
    
    # 获取总数
    total = await creation_crud.count_accessible(
        db,
        user_id=current_user.id,
        status=status,
        topic_id=topic_id,
        include_all=is_admin_user(current_user),
    )
    
    return {
        "code": 200,
        "message": "获取创作列表成功",
        "data": {
            "items": [ContentCreationResponse.from_orm(creation).dict() for creation in creations],
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": (total + page_size - 1) // page_size
        }
    }


@router.get("/{creation_id}/adjustment-options", response_model=dict)
async def get_creation_adjustment_options(
    creation_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    """获取草稿调整弹窗需要的当前内容和历史生成版本。"""
    creation = await creation_crud.get(db, id=creation_id)
    if not creation:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="创作不存在")
    if not await can_access_creation(db, current_user, creation):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权访问他人创作")

    current_content = _decode_creation_content(creation.content)
    title_options: list = []
    content_options: list = []
    seen_titles: set = set()
    seen_contents: set = set()

    # 生成记录原本按 candidate_id 关联；草稿保存后仍可恢复该选题的全部历史生成结果。
    if creation.candidate_id:
        result = await db.execute(
            select(GenerationRecord)
            .where(
                GenerationRecord.user_id == current_user.id,
                GenerationRecord.candidate_id == creation.candidate_id,
                GenerationRecord.status == "completed",
                GenerationRecord.type.in_(["title_generate", "content_generate"]),
            )
            .order_by(desc(GenerationRecord.created_at))
        )
        records = result.scalars().all()

        for record in records:
            snapshot = record.output_snapshot or {}
            if not isinstance(snapshot, dict):
                continue

            if record.type == "title_generate":
                # 推荐标题和全部候选都保留；相同标题只展示一次。
                title_items = []
                for key in ("recommendations", "titles", "candidates"):
                    values = snapshot.get(key)
                    if isinstance(values, list):
                        title_items.extend(values)
                if not title_items and snapshot.get("title"):
                    title_items = [snapshot]
                for item in title_items:
                    if isinstance(item, str):
                        title = item
                        meta = {}
                    elif isinstance(item, dict):
                        title = item.get("title") or item.get("editable_title") or ""
                        meta = {
                            key: item[key]
                            for key in ("rank", "score", "final_score", "method", "reason", "is_top3", "is_top5")
                            if item.get(key) is not None
                        }
                    else:
                        continue
                    _append_unique(
                        title_options,
                        seen_titles,
                        title,
                        {
                            "record_id": record.id,
                            "generated_at": record.created_at,
                            "is_current": False,
                            **meta,
                        },
                    )
            else:
                content = snapshot.get("final_text") or snapshot.get("content") or ""
                if content:
                    _append_unique(
                        content_options,
                        seen_contents,
                        content,
                        {
                            "record_id": record.id,
                            "generated_at": record.created_at,
                            "is_current": False,
                            "word_count": len(content),
                        },
                    )

    # 当前草稿可能是手动编辑后的值，也可能来自旧数据，必须始终可选。
    current_title = (creation.title or "").strip()
    if current_title and current_title not in seen_titles:
        title_options.insert(0, {
            "record_id": None,
            "generated_at": creation.updated_at,
            "is_current": True,
            "value": current_title,
        })
    else:
        for item in title_options:
            if item["value"] == current_title:
                item["is_current"] = True
                break

    if current_content and current_content not in seen_contents:
        content_options.insert(0, {
            "record_id": None,
            "generated_at": creation.updated_at,
            "is_current": True,
            "word_count": len(current_content),
            "value": current_content,
        })
    else:
        for item in content_options:
            if item["value"] == current_content:
                item["is_current"] = True
                break

    return {
        "code": 200,
        "data": {
            "creation": {
                "id": creation.id,
                "title": current_title,
                "content": current_content,
                "status": creation.status,
            },
            "titles": title_options,
            "contents": content_options,
        },
    }


@router.post("/{creation_id}/mark-published", response_model=dict)
async def mark_creation_published(
    creation_id: int,
    req: CreationPublishedRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    """公众号草稿箱上传成功后，记录为“草稿箱”而不是正式发布。"""
    creation = await creation_crud.get(db, id=creation_id)
    if not creation:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="创作不存在")
    if not await can_publish_creation(db, current_user, creation):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权发布他人创作")

    stored_creation, publication, idempotent = await record_creation_publication(
        db,
        creation_id=creation.id,
        initiated_by=current_user.id,
        platform=req.platform or "wechat_draft",
        operation="draft_upload",
        external_id=req.external_id,
        external_url=req.external_url,
        request_key=req.request_key,
    )
    return {
        "code": 200,
        "message": "已记录公众号草稿箱状态",
        "data": {
            "creation": ContentCreationResponse.from_orm(stored_creation).dict(),
            "publication": publication_payload(publication),
            "idempotent": idempotent,
        },
    }


@router.get("/{creation_id}", response_model=dict)
async def get_creation(
    creation_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Any:
    """获取创作详情"""
    creation = await creation_crud.get(db, id=creation_id)
    if not creation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="创作不存在"
        )
    
    if not await can_access_creation(db, current_user, creation):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权访问他人创作"
        )
    
    return {
        "code": 200,
        "message": "获取创作详情成功",
        "data": ContentCreationResponse.from_orm(creation).dict()
    }


@router.put("/{creation_id}", response_model=dict)
async def update_creation(
    creation_id: int,
    creation_in: ContentCreationUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Any:
    """更新创作内容"""
    # 获取创作记录
    creation = await creation_crud.get(db, id=creation_id)
    if not creation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="创作不存在"
        )
    
    if not await can_edit_creation(db, current_user, creation):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权修改他人创作"
        )

    # 生命周期状态只能由专用动作修改，避免普通保存把“草稿箱”和“正式发布”
    # 互相覆盖；标题、正文等编辑字段仍可由 editor 角色更新。
    update_data = creation_in.dict(exclude_unset=True)
    if "status" in update_data and update_data["status"] != creation.status:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="请使用专用发布接口修改创作状态",
        )
    
    # 更新创作
    updated_creation = await creation_crud.update(
        db,
        db_obj=creation,
        obj_in=creation_in
    )
    
    return {
        "code": 200,
        "message": "创作更新成功",
        "data": ContentCreationResponse.from_orm(updated_creation).dict()
    }


@router.delete("/{creation_id}", response_model=dict)
async def delete_creation(
    creation_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Any:
    """删除创作"""
    # 获取创作记录
    creation = await creation_crud.get(db, id=creation_id)
    if not creation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="创作不存在"
        )
    
    if not await can_delete_creation(db, current_user, creation):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权删除他人创作"
        )
    
    # 删除创作
    await creation_crud.remove(db, id=creation_id)
    
    return {
        "code": 200,
        "message": "创作删除成功",
        "data": None
    }


@router.post("/{creation_id}/publish", response_model=dict)
async def publish_creation(
    creation_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Any:
    """发布创作"""
    # 获取创作记录
    creation = await creation_crud.get(db, id=creation_id)
    if not creation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="创作不存在"
        )
    
    if not await can_publish_creation(db, current_user, creation):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权发布他人创作"
        )

    if creation.status == "archived":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="已归档创作不能直接发布"
        )

    published_creation, publication, idempotent = await record_creation_publication(
        db,
        creation_id=creation.id,
        initiated_by=current_user.id,
        platform="local",
        operation="publish",
    )
    
    return {
        "code": 200,
        "message": "创作发布成功",
        "data": {
            "creation": ContentCreationResponse.from_orm(published_creation).dict(),
            "publication": publication_payload(publication),
            "idempotent": idempotent,
        },
    }


@router.post("/from-candidate", response_model=dict)
async def create_creation_from_candidate(
    request: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Any:
    """从选题候选创建创作"""
    candidate_id = request.get("candidate_id")
    cluster_id = request.get("cluster_id")
    
    if not candidate_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="缺少 candidate_id"
        )
    
    # 查询选题候选信息
    from sqlalchemy import select
    from app.models.topic_candidate import TopicCandidate
    
    result = await db.execute(
        select(TopicCandidate).where(TopicCandidate.id == candidate_id)
    )
    candidate = result.scalar_one_or_none()
    
    if not candidate:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="选题候选不存在"
        )
    
    # 创建创作记录
    creation = ContentCreation(
        user_id=current_user.id,
        candidate_id=candidate_id,
        cluster_id=cluster_id or candidate.info_cluster_id,
        title=candidate.title,
        topic_title=candidate.title,
        topic_direction=candidate.direction,
        status="draft",
        outline_status="idle",
        title_status="idle",
        content_status="idle",
    )
    
    db.add(creation)
    await db.commit()
    await db.refresh(creation)
    
    return {
        "code": 200,
        "message": "创作创建成功",
        "data": ContentCreationResponse.from_orm(creation).dict()
    }


@router.post("/generate", response_model=dict)
async def generate_content(
    request: ContentGenerationRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Any:
    """AI生成内容"""
    try:
        # 调用AI服务生成内容
        from app.services.ai_service import ai_service
        from app.services.style_service import style_service
        
        # 获取用户风格
        style_profile = None
        if request.style_profile_id:
            style_profile = await style_service.get_style_profile(
                db,
                style_id=request.style_profile_id,
                user_id=current_user.id
            )
        
        # 生成内容
        generated_content = await ai_service.generate_content(
            topic_title=request.topic_title,
            topic_summary=request.topic_summary,
            style_profile=style_profile,
            custom_prompt=request.custom_prompt,
            content_type=request.content_type
        )
        
        # 创建创作记录
        creation_data = ContentCreationCreate(
            topic_id=request.topic_id,
            title=request.topic_title,
            content=generated_content,
            status="draft"
        )
        
        creation = await creation_crud.create(
            db,
            obj_in=creation_data,
            user_id=current_user.id
        )
        
        return {
            "code": 200,
            "message": "内容生成成功",
            "data": {
                "creation": ContentCreationResponse.from_orm(creation).dict(),
                "generated_content": generated_content
            }
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"内容生成失败: {str(e)}"
        )
