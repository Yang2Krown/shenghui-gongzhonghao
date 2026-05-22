"""
标题生成端点

提供标题生成任务的创建、执行和结果查询功能。
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
import uuid
import logging

from app.core.database import get_db, async_session_factory
from app.models.task import Task, TaskStatus
from app.models.title import TitleGenerationResult
from app.schemas.title_generation import (
    TitleGenerationRequest,
    TitleGenerationResponse,
    TitleGenerationResultResponse,
    TitleCandidateResponse,
    FinalRecommendationResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter()


async def _run_title_generation_background(task_id: str, request_data: dict):
    """
    后台执行标题生成任务的独立函数
    
    在独立的数据库会话中创建TitleGenerationService实例并执行，
    避免在请求处理阶段就实例化Agent（需要API密钥）。
    
    Args:
        task_id: 任务ID
        request_data: 请求数据（已序列化为dict）
    """
    # 延迟导入，避免在请求处理阶段加载Agent模块
    from app.services.title_generation_service import TitleGenerationService
    from app.schemas.title_generation import TitleGenerationRequest
    
    # 在后台任务中创建独立的数据库会话
    async with async_session_factory() as db:
        try:
            # 反序列化请求数据
            request = TitleGenerationRequest(**request_data)
            
            # 在后台任务中实例化Service（此时才加载Agent，需要API密钥）
            service = TitleGenerationService(db)
            await service.execute_title_generation(
                task_id=task_id,
                request=request,
            )
        except Exception as e:
            logger.error(f"后台标题生成任务 {task_id} 失败: {str(e)}", exc_info=True)
            # 更新任务状态为失败
            from sqlalchemy import update
            from datetime import datetime
            await db.execute(
                update(Task).where(Task.id == task_id).values(
                    status=TaskStatus.FAILED,
                    error_message=str(e),
                    completed_at=datetime.now(),
                )
            )
            await db.commit()


@router.post("/", response_model=TitleGenerationResponse)
async def create_title_generation(
    request: TitleGenerationRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """
    创建标题生成任务
    
    基于选题和大纲生成标题候选，经过4个Agent协作流程输出Top 3推荐标题。
    
    ## Agent流程
    1. **Agent A (标题创作员)**: 生成10-15个标题候选，覆盖至少6种套路
    2. **Agent B (标题评审员)**: 一票否决扫描 + 6维度评分 + 筛选Top 5
    3. **Agent C (读者点击预测员)**: 模拟读者场景，预测点击意愿
    4. **Agent D (最终判定员)**: 综合评分，输出Top 3推荐标题
    
    ## 重生机制
    - 如果Top 3综合分 < 7.0，将扣分理由喂给Agent A重新生成
    - 最多重生1次，失败则标记"难以成标题"丢回人工
    """
    # 创建任务记录
    task = Task(
        id=str(uuid.uuid4()),
        title=f"标题生成任务 - {request.topic.title if request.topic else '未命名'}",
        description="基于选题和大纲生成标题候选",
        status=TaskStatus.PENDING,
        input_data={
            "topic": request.topic.dict() if request.topic else None,
            "outline": request.outline.dict() if request.outline else None,
        },
    )
    
    db.add(task)
    await db.flush()
    
    # 序列化请求数据，传给后台任务（避免传递ORM session）
    request_data = request.dict()
    
    # 启动后台任务（Service和Agent在后台任务中延迟实例化）
    background_tasks.add_task(
        _run_title_generation_background,
        task_id=task.id,
        request_data=request_data,
    )
    
    return TitleGenerationResponse(
        task_id=task.id,
        status=task.status,
        message="标题生成任务已创建，正在后台执行",
    )


@router.get("/{task_id}", response_model=TitleGenerationResultResponse)
async def get_title_generation_result(
    task_id: str,
    db: AsyncSession = Depends(get_db),
):
    """
    获取标题生成结果
    
    获取指定任务的标题生成结果，包括所有候选标题、评分和最终推荐。
    
    Args:
        task_id: 任务ID
    
    Returns:
        标题生成结果，包括:
        - 候选标题列表
        - Top 5评分结果
        - 点击预测结果
        - Top 3最终推荐
        - 生成过程归档
    """
    # 查询任务
    from sqlalchemy import select
    result = await db.execute(select(Task).where(Task.id == task_id))
    task = result.scalar_one_or_none()
    
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    
    if task.status == TaskStatus.PENDING or task.status == TaskStatus.PROCESSING:
        return TitleGenerationResultResponse(
            task_id=task.id,
            status=task.status,
            message="任务正在处理中，请稍后查询",
        )
    
    if task.status == TaskStatus.FAILED:
        return TitleGenerationResultResponse(
            task_id=task.id,
            status=task.status,
            message=task.error_message or "任务处理失败",
        )
    
    # 查询结果
    result_query = await db.execute(
        select(TitleGenerationResult).where(TitleGenerationResult.task_id == task_id)
    )
    generation_result = result_query.scalar_one_or_none()
    
    if not generation_result:
        raise HTTPException(status_code=500, detail="结果数据不存在")
    
    return TitleGenerationResultResponse(
        task_id=task.id,
        status=task.status,
        message="标题生成完成",
        result=generation_result,
    )


@router.get("/{task_id}/candidates", response_model=List[TitleCandidateResponse])
async def get_candidates(
    task_id: str,
    db: AsyncSession = Depends(get_db),
):
    """
    获取候选标题列表
    
    获取指定任务的所有候选标题（Agent A输出）。
    
    Args:
        task_id: 任务ID
    
    Returns:
        候选标题列表
    """
    # 查询任务
    from sqlalchemy import select
    result = await db.execute(select(Task).where(Task.id == task_id))
    task = result.scalar_one_or_none()
    
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    
    # 查询结果
    result_query = await db.execute(
        select(TitleGenerationResult).where(TitleGenerationResult.task_id == task_id)
    )
    generation_result = result_query.scalar_one_or_none()
    
    if not generation_result:
        raise HTTPException(status_code=404, detail="结果数据不存在")
    
    return generation_result.candidates


@router.get("/{task_id}/recommendations", response_model=List[FinalRecommendationResponse])
async def get_recommendations(
    task_id: str,
    db: AsyncSession = Depends(get_db),
):
    """
    获取最终推荐标题
    
    获取指定任务的Top 3推荐标题（Agent D输出）。
    
    Args:
        task_id: 任务ID
    
    Returns:
        Top 3推荐标题列表
    """
    # 查询任务
    from sqlalchemy import select
    result = await db.execute(select(Task).where(Task.id == task_id))
    task = result.scalar_one_or_none()
    
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    
    # 查询结果
    result_query = await db.execute(
        select(TitleGenerationResult).where(TitleGenerationResult.task_id == task_id)
    )
    generation_result = result_query.scalar_one_or_none()
    
    if not generation_result:
        raise HTTPException(status_code=404, detail="结果数据不存在")
    
    return generation_result.final_recommendations
