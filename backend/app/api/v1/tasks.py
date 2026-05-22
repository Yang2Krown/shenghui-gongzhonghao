"""
任务管理端点

管理标题生成任务的创建、查询、更新和删除。
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
import uuid

from app.core.database import get_db
from app.models.task import Task, TaskStatus
from app.schemas.task import (
    TaskCreate,
    TaskResponse,
    TaskListResponse,
    TaskUpdate,
)

router = APIRouter()


@router.post("/", response_model=TaskResponse)
async def create_task(
    task_data: TaskCreate,
    db: AsyncSession = Depends(get_db),
):
    """
    创建新的标题生成任务
    
    Args:
        task_data: 任务创建数据
        db: 数据库会话
    
    Returns:
        创建的任务信息
    """
    task = Task(
        id=str(uuid.uuid4()),
        title=task_data.title,
        description=task_data.description,
        status=TaskStatus.PENDING,
        input_data=task_data.input_data.dict() if task_data.input_data else None,
    )
    
    db.add(task)
    await db.flush()
    await db.refresh(task)
    
    return task


@router.get("/", response_model=TaskListResponse)
async def list_tasks(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    status: Optional[TaskStatus] = Query(None, description="状态筛选"),
    db: AsyncSession = Depends(get_db),
):
    """
    获取任务列表
    
    Args:
        page: 页码
        page_size: 每页数量
        status: 状态筛选
        db: 数据库会话
    
    Returns:
        任务列表
    """
    # 构建查询
    query = select(Task)
    count_query = select(func.count()).select_from(Task)
    
    if status:
        query = query.where(Task.status == status)
        count_query = count_query.where(Task.status == status)
    
    # 获取总数
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0
    
    # 获取分页数据
    query = query.order_by(Task.created_at.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)
    
    result = await db.execute(query)
    tasks = result.scalars().all()
    
    return TaskListResponse(
        items=tasks,
        total=total,
        page=page,
        page_size=page_size,
        pages=(total + page_size - 1) // page_size,
    )


@router.get("/{task_id}", response_model=TaskResponse)
async def get_task(
    task_id: str,
    db: AsyncSession = Depends(get_db),
):
    """
    获取单个任务详情
    
    Args:
        task_id: 任务ID
        db: 数据库会话
    
    Returns:
        任务详情
    """
    result = await db.execute(select(Task).where(Task.id == task_id))
    task = result.scalar_one_or_none()
    
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    
    return task


@router.patch("/{task_id}", response_model=TaskResponse)
async def update_task(
    task_id: str,
    task_data: TaskUpdate,
    db: AsyncSession = Depends(get_db),
):
    """
    更新任务信息
    
    Args:
        task_id: 任务ID
        task_data: 更新数据
        db: 数据库会话
    
    Returns:
        更新后的任务信息
    """
    result = await db.execute(select(Task).where(Task.id == task_id))
    task = result.scalar_one_or_none()
    
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    
    # 更新字段
    update_data = task_data.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(task, field, value)
    
    await db.flush()
    await db.refresh(task)
    
    return task


@router.delete("/{task_id}")
async def delete_task(
    task_id: str,
    db: AsyncSession = Depends(get_db),
):
    """
    删除任务
    
    Args:
        task_id: 任务ID
        db: 数据库会话
    
    Returns:
        删除确认信息
    """
    result = await db.execute(select(Task).where(Task.id == task_id))
    task = result.scalar_one_or_none()
    
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    
    await db.delete(task)
    
    return {"message": "任务已删除", "task_id": task_id}
