"""正文续写端点 - 分析已写内容，生成自然收尾的续写方案。"""

import logging
from pydantic import BaseModel, Field

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse

from app.core.progress import progress_store
from app.core.background import spawn
from app.core.security import get_current_user
from app.models.user import User
from app.services.generation_tracker import track_start, track_complete, track_fail

logger = logging.getLogger(__name__)
router = APIRouter()


class ContentContinuationRequest(BaseModel):
    """正文续写请求"""
    content: str = Field(..., min_length=50, description="已写好的文章正文")
    preference: str = Field(default="", description="续写偏好（选填）")


class ContentContinuationResponse(BaseModel):
    """正文续写响应"""
    run_id: str = Field(..., description="进度流 ID")
    message: str = Field(default="续写任务已创建")


async def _run_continuation_background(
    content: str,
    preference: str,
    run_id: str,
    user_id: int = None,
):
    """后台执行续写任务"""
    try:
        from app.services.content_continuation import analyze_and_continue

        await progress_store.push(run_id, {
            "event": "step_start",
            "data": {
                "step": 0,
                "agent": "内容分析师",
                "action": "正在分析文章脉络和情感走向...",
                "avatar": "/agents/title-a.png",
            },
        })

        # 调用续写服务
        result = await analyze_and_continue(content, preference)

        await progress_store.push(run_id, {
            "event": "step_done",
            "data": {"step": 0, "agent": "内容分析师"},
        })

        # 推送结果
        await progress_store.push(run_id, {
            "event": "result",
            "data": result,
        })

        await track_complete(
            run_id,
            result,
            display_title=f"正文续写 · {result.get('plans', [{}])[0].get('approach', '')[:20]}",
        )

    except Exception as e:
        logger.error(f"正文续写失败: {str(e)}", exc_info=True)
        await progress_store.push(run_id, {
            "event": "error",
            "data": {"message": str(e)},
        })
        await track_fail(run_id, str(e))


@router.post("/generate", response_model=ContentContinuationResponse)
async def generate_continuation(
    request: ContentContinuationRequest,
    current_user: User = Depends(get_current_user),
):
    """
    正文续写

    输入已写好的文章正文，AI 会分析内容脉络，给出多个自然收尾的续写方案。
    """
    run_id = progress_store.create_run()

    await track_start(
        user_id=current_user.id,
        type="content_continuation",
        run_id=run_id,
        input_snapshot={
            "content_length": len(request.content),
            "preference": request.preference,
        },
        display_title=f"正文续写 · {request.content[:30]}...",
        resume_context={
            "route": "/creation/continuation",
            "query": {},
        },
    )

    spawn(
        _run_continuation_background(
            content=request.content,
            preference=request.preference,
            run_id=run_id,
            user_id=current_user.id,
        )
    )

    return ContentContinuationResponse(run_id=run_id)


@router.get("/stream/{run_id}")
async def stream_continuation_progress(
    run_id: str,
    token: str = Query(None, description="认证 token"),
) -> StreamingResponse:
    """SSE 端点：实时推送续写进度。"""
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
