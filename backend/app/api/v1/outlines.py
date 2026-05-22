"""大纲生成 API。

提供大纲生成、查询等接口。
"""

from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.core.security import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.models.outline import (
    Outline,
    OutlineCandidate,
    OutlineReview,
    OutlineCriticism,
    OutlineInspection,
)
from app.models.topic_candidate import TopicCandidate
from app.services.outline_generation.outline_service import generate_outline

router = APIRouter()


@router.post("/generate", response_model=dict)
async def trigger_outline_generation(
    body: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    """触发大纲生成任务。
    
    body 格式：
    {
        "candidate_id": 123,  # 选题候选ID
        "model": "claude-3-sonnet"  # 可选，指定模型
    }
    """
    candidate_id = body.get("candidate_id")
    if not candidate_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="缺少 candidate_id 参数"
        )
    
    model = body.get("model")
    
    try:
        result = await generate_outline(
            db,
            candidate_id=int(candidate_id),
            model=model,
        )
        
        return {
            "code": 200,
            "message": "大纲生成成功",
            "data": result.model_dump(),
        }
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"大纲生成失败: {str(e)}",
        )


@router.get("", response_model=dict)
async def get_outlines(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    passed: Optional[str] = Query(None, description="筛选状态: passed/failed/pending"),
    direction: Optional[str] = Query(None, description="筛选方向"),
    min_score: Optional[float] = Query(None, ge=0, le=10, description="最低分数"),
    keyword: Optional[str] = Query(None, description="关键词搜索"),
    sort_by: str = Query("total_score", description="排序字段"),
    sort_order: str = Query("desc", description="排序方式"),
) -> Any:
    """获取大纲列表。"""
    skip = (page - 1) * page_size
    
    # 构建查询
    query = select(Outline).options(
        joinedload(Outline.candidate),
        joinedload(Outline.review),
        joinedload(Outline.inspection),
    )
    
    # 筛选
    if passed:
        query = query.where(Outline.passed == passed)
    if direction:
        query = query.where(Outline.direction == direction)
    if min_score is not None:
        query = query.where(Outline.total_score >= min_score)
    if keyword:
        query = query.where(Outline.title.ilike(f"%{keyword}%"))
    
    # 总数
    count_query = select(func.count(Outline.id))
    if passed:
        count_query = count_query.where(Outline.passed == passed)
    if direction:
        count_query = count_query.where(Outline.direction == direction)
    if min_score is not None:
        count_query = count_query.where(Outline.total_score >= min_score)
    if keyword:
        count_query = count_query.where(Outline.title.ilike(f"%{keyword}%"))
    total_result = await db.execute(count_query)
    total = total_result.scalar()
    
    # 排序
    order_col = getattr(Outline, sort_by, Outline.total_score)
    if sort_order == "desc":
        query = query.order_by(desc(order_col))
    else:
        query = query.order_by(order_col)
    
    query = query.offset(skip).limit(page_size)
    result = await db.execute(query)
    outlines = result.scalars().unique().all()
    
    return {
        "code": 200,
        "message": "获取大纲列表成功",
        "data": {
            "items": [_outline_to_dict(o) for o in outlines],
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": (total + page_size - 1) // page_size,
        },
    }


@router.get("/{outline_id}", response_model=dict)
async def get_outline(
    outline_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    """获取大纲详情。"""
    result = await db.execute(
        select(Outline)
        .options(
            joinedload(Outline.candidate),
            joinedload(Outline.candidates),
            joinedload(Outline.review),
            joinedload(Outline.criticism),
            joinedload(Outline.inspection),
        )
        .where(Outline.id == outline_id)
    )
    outline = result.unique().scalar_one_or_none()
    
    if not outline:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="大纲不存在"
        )
    
    data = _outline_to_dict(outline)
    
    # 添加详细信息
    if outline.candidates:
        data["candidates"] = [
            {
                "candidate_number": c.candidate_number,
                "hook_type": c.hook_type,
                "skeleton_feature": c.skeleton_feature,
                "sections": c.sections,
                "total_words": c.total_words,
            }
            for c in outline.candidates
        ]
    
    if outline.review:
        data["review"] = {
            "selected_candidate": outline.review.selected_candidate,
            "review_reason": outline.review.review_reason,
            "reviewed_sections": outline.review.reviewed_sections,
        }
    
    if outline.criticism:
        data["criticism"] = {
            "overall_feeling": outline.criticism.overall_feeling,
            "problem_sections": outline.criticism.problem_sections,
            "revised_sections": outline.criticism.revised_sections,
        }
    
    if outline.inspection:
        data["inspection"] = {
            "hook_score": outline.inspection.hook_score,
            "value_ladder_score": outline.inspection.value_ladder_score,
            "rhythm_score": outline.inspection.rhythm_score,
            "title_scan_score": outline.inspection.title_scan_score,
            "trigger_score": outline.inspection.trigger_score,
            "length_score": outline.inspection.length_score,
            "total_score": outline.inspection.total_score,
            "verdict": outline.inspection.verdict,
            "deduction_reasons": outline.inspection.deduction_reasons,
        }
    
    return {"code": 200, "message": "获取大纲详情成功", "data": data}


@router.get("/stats/overview", response_model=dict)
async def get_stats_overview(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    """获取大纲统计概览。"""
    total = (await db.execute(select(func.count(Outline.id)))).scalar()
    passed = (await db.execute(
        select(func.count(Outline.id)).where(Outline.passed == "passed")
    )).scalar()
    failed = (await db.execute(
        select(func.count(Outline.id)).where(Outline.passed == "failed")
    )).scalar()
    pending = (await db.execute(
        select(func.count(Outline.id)).where(Outline.passed == "pending")
    )).scalar()
    
    # 平均分数
    avg_score_result = (await db.execute(
        select(func.avg(Outline.total_score)).where(Outline.passed != "pending")
    )).scalar()
    avg_score = round(avg_score_result, 2) if avg_score_result else 0.0
    
    # 按方向统计
    direction_result = await db.execute(
        select(Outline.direction, func.count(Outline.id))
        .where(Outline.direction.is_not(None))
        .group_by(Outline.direction)
    )
    direction_stats = {d: c for d, c in direction_result.all()}
    
    return {
        "code": 200,
        "message": "获取统计成功",
        "data": {
            "total": total or 0,
            "passed": passed or 0,
            "failed": failed or 0,
            "pending": pending or 0,
            "average_score": avg_score,
            "by_direction": direction_stats,
        },
    }


def _outline_to_dict(outline: Outline) -> dict:
    """将大纲对象转换为字典。"""
    return {
        "id": outline.id,
        "candidate_id": outline.candidate_id,
        "title": outline.title,
        "direction": outline.direction,
        "routine": outline.routine,
        "sections": outline.sections,
        "total_words": outline.total_words,
        "section_count": outline.section_count,
        "generation_process": outline.generation_process,
        "inspection_score": outline.inspection_score,
        "total_score": outline.total_score,
        "passed": outline.passed,
        "created_at": outline.created_at.isoformat() if outline.created_at else None,
        "candidate": {
            "id": outline.candidate.id,
            "title": outline.candidate.title,
            "direction": outline.candidate.direction,
            "verdict": outline.candidate.verdict,
        } if outline.candidate else None,
    }
