"""文案润色 API 端点。

提供文案润色的 RESTful 接口，支持 SSE 实时进度推送。
复用正文生成的 Agent B/D/E/C 四个 Agent，跳过 Agent A。
"""

import asyncio
import logging
from typing import Any, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.core.security import get_current_user
from app.core.progress import progress_store
from app.core.background import spawn
from app.models.user import User
from app.services.generation_tracker import track_start, track_complete, track_fail

logger = logging.getLogger(__name__)
router = APIRouter()


# ──────────────────────────────────────────────
# 请求/响应 Schema
# ──────────────────────────────────────────────

class PolishRequest(BaseModel):
    """文案润色请求。"""
    text: str = Field(..., min_length=10, description="用户提供的原始文案文本")
    title: str = Field(default="", description="文章标题（可选，用于金句催化上下文）")


class PolishResponse(BaseModel):
    """文案润色响应。"""
    run_id: str = Field(..., description="进度流 ID，前端可通过 GET /content-polish/stream/{run_id} 获取实时进度")


# ──────────────────────────────────────────────
# API 端点
# ──────────────────────────────────────────────

@router.post("/generate", response_model=dict)
async def generate_polish(
    req: PolishRequest,
    current_user: User = Depends(get_current_user),
) -> Any:
    """文案润色（SSE 实时进度）。

    接收用户提供的文本，复用正文生成的 Agent B/D/E/C 进行润色。
    返回 run_id，前端可通过 GET /content-polish/stream/{run_id} 获取实时进度。
    润色结果通过 SSE 的 result 事件返回。
    """
    run_id = progress_store.create_run()

    await track_start(
        user_id=current_user.id,
        type="content_polish",
        run_id=run_id,
        input_snapshot={
            "text_length": len(req.text),
            "title": req.title,
        },
        display_title=f"文案润色 · {req.title[:30] if req.title else req.text[:30]}",
        resume_context={
            "route": "/creation/polish",
            "query": {},
        },
    )

    async def _run():
        try:
            from app.services.content_polish.orchestrator import polish_content
            from app.services.content_polish.schemas import PolishInput

            inp = PolishInput(
                text=req.text,
                title=req.title if req.title else None,
            )

            async def _progress_cb(event):
                await progress_store.push(run_id, event)

            output = await polish_content(inp, progress_callback=_progress_cb)

            # 发送结果数据
            result_data = {
                "final_text": output.polished_text,
                "final_word_count": output.polished_word_count,
                "original_word_count": output.original_word_count,
                "word_change_pct": output.word_change_pct,
                "gold_sentences": output.gold_sentences,
                "rewrite_table": output.rewrite_table,
                "skipped_sections": output.skipped_sections,
                "quality_check": output.quality_check,
                "factual_summary": output.factual_summary,
                "factual_corrections": output.factual_corrections,
                "agent_b_sentence_count": output.agent_b_sentence_count,
                "agent_c_rewrite_count": output.agent_c_rewrite_count,
                "agent_d_error_count": output.agent_d_error_count,
                "agent_e_correction_count": output.agent_e_correction_count,
                "style_anchor": "",
            }

            await progress_store.push(run_id, {
                "event": "result",
                "data": result_data,
            })
            await track_complete(run_id, result_data)

        except Exception as e:
            logger.error(f"文案润色失败: {e}", exc_info=True)
            await progress_store.push(run_id, {
                "event": "error",
                "data": {"message": str(e)},
            })
            await track_fail(run_id, str(e))

    spawn(_run())

    return {
        "code": 200,
        "message": "文案润色任务已提交",
        "data": {"run_id": run_id},
    }


@router.get("/stream/{run_id}")
async def stream_polish_progress(
    run_id: str,
    token: str = Query(None, description="认证 token（EventSource 不支持 header）"),
) -> StreamingResponse:
    """SSE 端点：实时推送文案润色进度。"""
    # 验证 token
    if token:
        from app.core.security import decode_token
        payload = decode_token(token)
        if not payload:
            raise HTTPException(status_code=401, detail="无效的 token")

    if not progress_store.exists(run_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"run {run_id} 不存在或已过期",
        )

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

class MultiModelPolishRequest(BaseModel):
    """多模型对比润色请求"""
    text: str = Field(..., min_length=10, description="用户提供的原始文案文本")
    title: str = Field(default="", description="文章标题（可选）")
    providers: list = Field(default=["deepseek", "aigocode"], description="要对比的模型列表")


class MultiModelPolishResponse(BaseModel):
    """多模型对比润色响应"""
    success: bool = Field(default=True)
    comparison: dict = Field(..., description="各模型的生成结果对比")


async def _run_polish_compare_background(
    text: str,
    title: str,
    run_id: str,
    providers: list,
    user_id: int = None,
):
    """后台执行多模型对比润色任务"""
    try:
        from app.services.content_polish.orchestrator import polish_content
        from app.services.content_polish.schemas import PolishInput

        inp = PolishInput(text=text, title=title or None)

        await progress_store.push(run_id, {
            "event": "step_start",
            "data": {
                "step": 0,
                "agent": "多模型润色",
                "action": f"正在用 {len(providers)} 个模型并行润色...",
                "avatar": "/agents/content-b.png",
            },
        })

        async def polish_with_provider(provider_name: str):
            """用指定 provider 运行润色流水线"""
            try:
                output = await polish_content(inp, provider=provider_name)
                return provider_name, {
                    "success": True,
                    "final_text": output.polished_text,
                    "final_word_count": output.polished_word_count,
                    "original_word_count": output.original_word_count,
                    "word_change_pct": output.word_change_pct,
                    "gold_sentences": output.gold_sentences,
                    "rewrite_table": output.rewrite_table,
                    "factual_summary": output.factual_summary,
                    "factual_corrections": output.factual_corrections,
                    "agent_b_sentence_count": output.agent_b_sentence_count,
                    "agent_c_rewrite_count": output.agent_c_rewrite_count,
                    "agent_d_error_count": output.agent_d_error_count,
                    "agent_e_correction_count": output.agent_e_correction_count,
                }
            except Exception as e:
                logger.error(f"Provider {provider_name} 润色失败: {e}")
                return provider_name, {
                    "success": False,
                    "error": str(e),
                }

        tasks = [polish_with_provider(p) for p in providers]
        results = await asyncio.gather(*tasks)

        comparison = {"models": {}}
        for provider_name, result in results:
            comparison["models"][provider_name] = result

        await progress_store.push(run_id, {
            "event": "step_done",
            "data": {"step": 0, "agent": "多模型润色"},
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
        await track_complete(run_id, result_data, display_title="多模型对比润色")

    except Exception as e:
        logger.error(f"多模型对比润色失败: {str(e)}", exc_info=True)
        await progress_store.push(run_id, {
            "event": "error",
            "data": {"message": str(e)},
        })
        await track_fail(run_id, str(e))


@router.post("/compare", response_model=MultiModelPolishResponse)
async def compare_multi_model_polish(
    request: MultiModelPolishRequest,
    current_user: User = Depends(get_current_user),
):
    """多模型对比润色

    同时用多个模型运行润色流水线，用于对比不同模型的效果。
    Agent E (Kimi联网纠错) 在所有模型中都会使用 Moonshot/Kimi。
    """
    run_id = progress_store.create_run()

    await track_start(
        user_id=current_user.id,
        type="multi_model_polish",
        run_id=run_id,
        input_snapshot={"text_length": len(request.text), "providers": request.providers},
        display_title="多模型对比润色",
        resume_context={
            "route": "/creation/polish",
            "query": {},
        },
    )

    spawn(
        _run_polish_compare_background(
            text=request.text,
            title=request.title,
            run_id=run_id,
            providers=request.providers,
            user_id=current_user.id,
        )
    )

    return MultiModelPolishResponse(
        success=True,
        comparison={"run_id": run_id, "message": "多模型对比润色任务已创建"},
    )


@router.get("/compare/stream/{run_id}")
async def stream_polish_compare_progress(
    run_id: str,
    token: str = Query(None, description="认证 token"),
) -> StreamingResponse:
    """SSE 端点：实时推送多模型对比润色进度。"""
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
