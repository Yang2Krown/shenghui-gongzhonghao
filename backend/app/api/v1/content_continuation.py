"""正文续写端点 - 分析已写内容，生成自然收尾的续写方案。"""

import asyncio
import logging
from typing import Optional
from pydantic import BaseModel, Field

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse

from app.core.progress import progress_store
from app.core.background import spawn
from app.core.security import get_current_user
from app.models.user import User
from app.services.generation_tracker import track_start, track_complete, track_fail
from app.services.credit_service import CreditService
from app.db.session import AsyncSessionLocal

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
        
        # 成功后扣减积分
        try:
            async with AsyncSessionLocal() as credit_db:
                credit_svc = CreditService(credit_db)
                await credit_svc.deduct_credits(
                    user_id=user_id,
                    operation="content_continuation",
                    operation_id=run_id,
                )
                await credit_db.commit()
        except Exception as credit_err:
            logger.warning(f"积分扣费失败: {credit_err}")

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
    # 检查积分
    async with AsyncSessionLocal() as credit_db:
        credit_service = CreditService(credit_db)
        balance_check = await credit_service.check_balance(current_user.id, "content_continuation")
        if not balance_check["sufficient"]:
            raise HTTPException(
                status_code=402,
                detail={
                    "code": "INSUFFICIENT_CREDITS",
                    "message": f"积分不足，需要 {balance_check['required']} 积分，当前余额 {balance_check['balance']} 积分",
                    "balance": balance_check["balance"],
                    "required": balance_check["required"],
                },
            )
    
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


# ──────────────────────────────────────────────
# 多模型对比
# ──────────────────────────────────────────────

class MultiModelContinuationRequest(BaseModel):
    """多模型对比续写请求"""
    content: str = Field(..., min_length=50, description="已写好的文章正文")
    preference: str = Field(default="", description="续写偏好（选填）")
    providers: list = Field(default=["deepseek", "aigocode"], description="要对比的模型列表")


class MultiModelContinuationResponse(BaseModel):
    """多模型对比续写响应"""
    success: bool = Field(default=True)
    comparison: dict = Field(..., description="各模型的生成结果对比")


async def _run_continuation_compare_background(
    content: str,
    preference: str,
    run_id: str,
    providers: list,
    user_id: int = None,
):
    """后台执行多模型对比续写任务"""
    from app.services.content_continuation import analyze_and_continue

    try:
        await progress_store.push(run_id, {
            "event": "step_start",
            "data": {
                "step": 0,
                "agent": "内容分析师",
                "action": "正在分析文章脉络和情感走向...",
                "avatar": "/agents/title-a.png",
            },
        })

        # 分析只需做一次（用默认 provider）
        # 实际分析在每个 provider 的生成中都会做，这里只做进度展示
        await progress_store.push(run_id, {
            "event": "step_done",
            "data": {"step": 0, "agent": "内容分析师"},
        })

        # Step 1: 用多个模型并行生成续写方案
        await progress_store.push(run_id, {
            "event": "step_start",
            "data": {
                "step": 1,
                "agent": "多模型创作",
                "action": f"正在用 {len(providers)} 个模型并行生成续写方案...",
                "avatar": "/agents/title-a.png",
            },
        })

        async def generate_with_provider(provider_name: str):
            """用指定 provider 生成续写方案"""
            try:
                result = await analyze_and_continue(content, preference, provider=provider_name)
                return provider_name, {
                    "success": True,
                    "analysis": result.get("analysis", {}),
                    "plans": result.get("plans", []),
                    "count": len(result.get("plans", [])),
                }
            except Exception as e:
                logger.error(f"Provider {provider_name} 续写生成失败: {e}")
                return provider_name, {
                    "success": False,
                    "error": str(e),
                    "analysis": {},
                    "plans": [],
                    "count": 0,
                }

        tasks = [generate_with_provider(p) for p in providers]
        results = await asyncio.gather(*tasks)

        comparison = {"models": {}}
        for provider_name, result in results:
            comparison["models"][provider_name] = result

        await progress_store.push(run_id, {
            "event": "step_done",
            "data": {"step": 1, "agent": "多模型创作"},
        })

        result_data = {
            "status": "completed",
            "comparison": comparison,
            "meta": {
                "providers": providers,
                "total_models": len(providers),
            },
        }

        await progress_store.push(run_id, {
            "event": "result",
            "data": result_data,
        })
        await track_complete(run_id, result_data, display_title=f"多模型对比续写")

    except Exception as e:
        logger.error(f"多模型对比续写失败: {str(e)}", exc_info=True)
        await progress_store.push(run_id, {
            "event": "error",
            "data": {"message": str(e)},
        })
        await track_fail(run_id, str(e))


@router.post("/compare", response_model=MultiModelContinuationResponse)
async def compare_multi_model_continuation(
    request: MultiModelContinuationRequest,
    current_user: User = Depends(get_current_user),
):
    """多模型对比续写

    同时用多个模型生成续写方案，用于对比不同模型的效果。
    """
    run_id = progress_store.create_run()

    await track_start(
        user_id=current_user.id,
        type="multi_model_continuation",
        run_id=run_id,
        input_snapshot={"content_length": len(request.content), "providers": request.providers},
        display_title=f"多模型对比续写",
        resume_context={
            "route": "/creation/continuation",
            "query": {},
        },
    )

    spawn(
        _run_continuation_compare_background(
            content=request.content,
            preference=request.preference,
            run_id=run_id,
            providers=request.providers,
            user_id=current_user.id,
        )
    )

    return MultiModelContinuationResponse(
        success=True,
        comparison={"run_id": run_id, "message": "多模型对比续写任务已创建"},
    )


@router.get("/compare/stream/{run_id}")
async def stream_continuation_compare_progress(
    run_id: str,
    token: str = Query(None, description="认证 token"),
) -> StreamingResponse:
    """SSE 端点：实时推送多模型对比续写进度。"""
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
