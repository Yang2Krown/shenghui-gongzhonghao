"""课程资料 API — 章节列表 / 详情 / 管理员 CRUD。"""

from typing import Any, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel as PydanticBaseModel
from pydantic import Field
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_current_admin_user, get_current_user
from app.db.session import get_db
from app.models.course import CourseChapter
from app.models.user import User

router = APIRouter()


# ── Pydantic schemas ──────────────────────────────────────────

class ChapterCreate(PydanticBaseModel):
    title: str = Field(..., max_length=500)
    subtitle: Optional[str] = Field(None, max_length=200)
    kicker: Optional[str] = Field(None, max_length=50)
    content_html: Optional[str] = None
    sort_order: int = 0
    is_published: bool = True


class ChapterUpdate(PydanticBaseModel):
    title: Optional[str] = Field(None, max_length=500)
    subtitle: Optional[str] = Field(None, max_length=200)
    kicker: Optional[str] = Field(None, max_length=50)
    content_html: Optional[str] = None
    sort_order: Optional[int] = None
    is_published: Optional[bool] = None


class ReorderItem(PydanticBaseModel):
    id: int
    sort_order: int


class ReorderRequest(PydanticBaseModel):
    items: List[ReorderItem]


# ── 序列化 ─────────────────────────────────────────────────────

def _serialize_list(ch: CourseChapter) -> dict:
    """侧边栏列表用——不含 content_html。"""
    return {
        "id": ch.id,
        "title": ch.title,
        "subtitle": ch.subtitle or "",
        "kicker": ch.kicker or "",
        "sort_order": ch.sort_order,
        "is_published": ch.is_published,
    }


def _serialize_detail(ch: CourseChapter) -> dict:
    """详情用——含 content_html。"""
    data = _serialize_list(ch)
    data["content_html"] = ch.content_html or ""
    return data


# ── GET /courses/chapters — 列表（侧边栏用） ──────────────────

@router.get("/chapters", response_model=dict)
async def list_chapters(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    """返回所有章节（按 sort_order 排序，不含正文 HTML）。"""
    result = await db.execute(
        select(CourseChapter)
        .order_by(CourseChapter.sort_order)
    )
    chapters = result.scalars().all()

    # 普通用户只看到已发布的
    if current_user.role != "admin" and not current_user.is_superuser:
        chapters = [ch for ch in chapters if ch.is_published]

    return {
        "code": 200,
        "message": "获取章节列表成功",
        "data": {
            "chapters": [_serialize_list(ch) for ch in chapters],
        },
    }


# ── GET /courses/chapters/{id} — 详情 ──────────────────────────

@router.get("/chapters/{chapter_id}", response_model=dict)
async def get_chapter(
    chapter_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    """返回单个章节详情（含正文 HTML）。"""
    ch = (
        await db.execute(
            select(CourseChapter).where(CourseChapter.id == chapter_id)
        )
    ).scalar_one_or_none()

    if not ch:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="章节不存在")

    # 普通用户不能看未发布章节
    if not ch.is_published and current_user.role != "admin" and not current_user.is_superuser:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="章节不存在")

    return {
        "code": 200,
        "message": "获取章节详情成功",
        "data": _serialize_detail(ch),
    }


# ── POST /courses/chapters — 新建（管理员） ────────────────────

@router.post("/chapters", response_model=dict)
async def create_chapter(
    body: ChapterCreate,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_current_admin_user),
) -> Any:
    """新建章节。"""
    # 如果 sort_order 未指定，自动放到末尾
    if body.sort_order == 0:
        max_order = (
            await db.execute(
                select(CourseChapter.sort_order)
                .order_by(desc(CourseChapter.sort_order))
                .limit(1)
            )
        ).scalar()
        body.sort_order = (max_order or 0) + 1

    ch = CourseChapter(
        title=body.title,
        subtitle=body.subtitle,
        kicker=body.kicker,
        content_html=body.content_html,
        sort_order=body.sort_order,
        is_published=body.is_published,
    )
    db.add(ch)
    await db.flush()
    await db.commit()
    await db.refresh(ch)

    return {
        "code": 200,
        "message": "创建章节成功",
        "data": _serialize_detail(ch),
    }


# ── PUT /courses/chapters/reorder — 批量排序（管理员） ─────────
# 注意：静态路由必须放在 {chapter_id} 参数路由前面，否则 "reorder" 会被当作 chapter_id 匹配

@router.put("/chapters/reorder", response_model=dict)
async def reorder_chapters(
    body: ReorderRequest,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_current_admin_user),
) -> Any:
    """批量更新章节排序。"""
    for item in body.items:
        ch = (
            await db.execute(
                select(CourseChapter).where(CourseChapter.id == item.id)
            )
        ).scalar_one_or_none()
        if ch:
            ch.sort_order = item.sort_order

    await db.flush()
    await db.commit()

    return {
        "code": 200,
        "message": "排序更新成功",
        "data": None,
    }


# ── PUT /courses/chapters/{id} — 更新（管理员） ────────────────

@router.put("/chapters/{chapter_id}", response_model=dict)
async def update_chapter(
    chapter_id: int,
    body: ChapterUpdate,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_current_admin_user),
) -> Any:
    """更新章节。"""
    ch = (
        await db.execute(
            select(CourseChapter).where(CourseChapter.id == chapter_id)
        )
    ).scalar_one_or_none()

    if not ch:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="章节不存在")

    update_data = body.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(ch, key, value)

    await db.flush()
    await db.commit()
    await db.refresh(ch)

    return {
        "code": 200,
        "message": "更新章节成功",
        "data": _serialize_detail(ch),
    }


# ── DELETE /courses/chapters/{id} — 删除（管理员） ─────────────

@router.delete("/chapters/{chapter_id}", response_model=dict)
async def delete_chapter(
    chapter_id: int,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_current_admin_user),
) -> Any:
    """删除章节。"""
    ch = (
        await db.execute(
            select(CourseChapter).where(CourseChapter.id == chapter_id)
        )
    ).scalar_one_or_none()

    if not ch:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="章节不存在")

    await db.delete(ch)
    await db.commit()

    return {
        "code": 200,
        "message": "删除章节成功",
        "data": None,
    }
