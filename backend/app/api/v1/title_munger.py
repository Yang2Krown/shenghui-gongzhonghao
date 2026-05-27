"""
芒格版标题生成与评分 API 端点

支持 SSE 实时推送 Agent 进度。
"""

import asyncio
import logging
from typing import Optional
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse

from fastapi import Depends
from app.core.progress import progress_store
from app.core.security import get_current_user
from app.models.user import User
from app.schemas.title_munger import (
    MungerGenerationRequest,
    MungerGenerationResponse,
    ScorerRequest,
    ScorerResponse,
)
from app.services.generation_tracker import track_start, track_complete, track_fail

logger = logging.getLogger(__name__)

router = APIRouter()


async def _run_munger_generate_background(content: str, run_id: str):
    from app.services.title_munger_generation.service import MungerTitleGenerationService

    try:
        async def _progress_cb(event):
            await progress_store.push(run_id, event)

        service = MungerTitleGenerationService(progress_callback=_progress_cb)
        result = await service.generate(content)

        result_data = {
            "success": result.get("success", False),
            "positioning": result.get("positioning", ""),
            "all_titles": result.get("all_titles", []),
            "top5": result.get("top5", []),
            "verdicts": result.get("verdicts", []),
            "final_pick": result.get("final_pick", ""),
            "loop_count": result.get("loop_count", 0),
            "failure_reasons": result.get("failure_reasons", []),
            "duration_seconds": result.get("duration_seconds", 0),
            "message": result.get("message", ""),
        }
        await progress_store.push(run_id, {
            "event": "result",
            "data": result_data,
        })
        final_pick = result.get("final_pick", "")
        await track_complete(run_id, result_data, display_title=f"芒格标题 · {final_pick[:30]}" if final_pick else None)
    except Exception as e:
        logger.error(f"芒格版标题生成失败: {str(e)}", exc_info=True)
        await progress_store.push(run_id, {
            "event": "error",
            "data": {"message": str(e)},
        })
        await track_fail(run_id, str(e))


async def _run_munger_score_background(title: str, summary: Optional[str], run_id: str):
    from app.services.title_scorer.service import TitleScorerService

    try:
        async def _progress_cb(event):
            await progress_store.push(run_id, event)

        service = TitleScorerService(progress_callback=_progress_cb)
        result = await service.score(title, summary)

        await progress_store.push(run_id, {
            "event": "result",
            "data": result,
        })
        await track_complete(run_id, result)
    except Exception as e:
        logger.error(f"芒格版标题评分失败: {str(e)}", exc_info=True)
        await progress_store.push(run_id, {
            "event": "error",
            "data": {"message": str(e)},
        })
        await track_fail(run_id, str(e))


@router.post("/munger-generate")
async def munger_title_generate(
    request: MungerGenerationRequest,
    current_user: User = Depends(get_current_user),
):
    """
    芒格版标题生成（SSE 模式）

    返回 run_id，前端通过 SSE 获取实时进度。
    """
    if not request.content or len(request.content) < 10:
        raise HTTPException(status_code=400, detail="文章内容至少需要10个字符")

    run_id = progress_store.create_run()

    await track_start(
        user_id=current_user.id,
        type="munger_generate",
        run_id=run_id,
        input_snapshot={"content_length": len(request.content)},
        display_title=f"芒格标题 · {request.content[:30]}…",
        resume_context={"route": "/munger-generation", "query": {}},
    )

    asyncio.create_task(
        _run_munger_generate_background(request.content, run_id)
    )

    return {
        "code": 200,
        "message": "芒格版标题生成任务已提交",
        "run_id": run_id,
    }


@router.post("/munger-score")
async def munger_title_score(
    request: ScorerRequest,
    current_user: User = Depends(get_current_user),
):
    """
    芒格版标题评分（SSE 模式）

    返回 run_id，前端通过 SSE 获取实时进度。
    """
    if not request.title:
        raise HTTPException(status_code=400, detail="请输入标题内容")

    run_id = progress_store.create_run()

    await track_start(
        user_id=current_user.id,
        type="munger_score",
        run_id=run_id,
        input_snapshot={"title": request.title, "summary": request.summary},
        display_title=f"标题评分 · {request.title[:30]}",
        resume_context={"route": "/munger-scorer", "query": {}},
    )

    asyncio.create_task(
        _run_munger_score_background(request.title, request.summary, run_id)
    )

    return {
        "code": 200,
        "message": "芒格版标题评分任务已提交",
        "run_id": run_id,
    }


@router.get("/stream/{run_id}")
async def stream_munger_progress(
    run_id: str,
    token: str = Query(None, description="认证 token（EventSource 不支持 header）"),
) -> StreamingResponse:
    """SSE 端点：实时推送芒格版标题生成/评分进度。"""
    if token:
        from app.core.security import decode_token
        payload = decode_token(token)
        if not payload:
            raise HTTPException(status_code=401, detail="无效的 token")

    if not progress_store.exists(run_id):
        raise HTTPException(status_code=404, detail=f"run {run_id} 不存在或已过期")

    return StreamingResponse(
        progress_store.stream(run_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
