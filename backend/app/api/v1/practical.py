"""实操 / 商稿创作流端点。

两段式（中间在前端做「研究确认 + 卖点选择」）：
  POST /practical/research  → run_id；SSE 推研究进度，result = ProductResearch
  POST /practical/draft     → run_id；SSE 推写作进度，result = 成稿
进度流统一走 GET /practical/stream/{run_id}。
"""

import logging
from typing import List, Optional
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
from app.services.practical_creation import (
    research_product, generate_practical_draft, ProductResearch,
)

logger = logging.getLogger(__name__)
router = APIRouter()


# ────────────── 请求 / 响应 ──────────────
class RunResponse(BaseModel):
    run_id: str
    message: str = "任务已创建"


class ResearchRequest(BaseModel):
    product: str = Field(..., min_length=1, description="产品 / 工具名")
    brief: str = Field(default="", description="商单 brief（选填）")


class DraftRequest(BaseModel):
    research: dict = Field(..., description="（用户编辑后的）ProductResearch")
    selected: List[str] = Field(..., description="入选功能点名称列表")
    template: str = Field(default="tool", description="tool=工具主线 / case=案例主线")
    brief_banned: List[str] = Field(default_factory=list, description="brief 禁忌词")
    brief_tone: Optional[str] = Field(default=None, description="brief 调性")


# ────────────── 积分校验 ──────────────
async def _ensure_credits(user_id: int, operation: str):
    async with AsyncSessionLocal() as db:
        check = await CreditService(db).check_balance(user_id, operation)
    if not check["sufficient"]:
        raise HTTPException(status_code=402, detail={
            "code": "INSUFFICIENT_CREDITS",
            "message": f"积分不足，需要 {check['required']}，余额 {check['balance']}",
            "balance": check["balance"], "required": check["required"],
        })


async def _deduct(user_id: int, operation: str, run_id: str):
    try:
        async with AsyncSessionLocal() as db:
            await CreditService(db).deduct_credits(
                user_id=user_id, operation=operation, operation_id=run_id)
            await db.commit()
    except Exception as e:
        logger.warning(f"积分扣费失败 {operation}: {e}")


# ────────────── 研究阶段 ──────────────
async def _run_research(product: str, brief: str, run_id: str, user_id: int):
    try:
        async def cb(ev):
            await progress_store.push(run_id, ev)
        research = await research_product(product, brief, progress_callback=cb)
        result = research.to_dict()
        await progress_store.push(run_id, {"event": "result", "data": result})
        await track_complete(run_id, result, display_title=f"产品研究 · {product}")
        await _deduct(user_id, "practical_research", run_id)
    except Exception as e:
        logger.error(f"产品研究失败: {e}", exc_info=True)
        await progress_store.push(run_id, {"event": "error", "data": {"message": str(e)}})
        await track_fail(run_id, str(e))


@router.post("/research", response_model=RunResponse)
async def start_research(req: ResearchRequest, current_user: User = Depends(get_current_user)):
    await _ensure_credits(current_user.id, "practical_research")
    run_id = progress_store.create_run()
    await track_start(
        user_id=current_user.id, type="practical_research", run_id=run_id,
        input_snapshot={"product": req.product, "brief_len": len(req.brief)},
        display_title=f"产品研究 · {req.product}",
        resume_context={"route": "/creation/practical", "query": {}},
    )
    spawn(_run_research(req.product, req.brief, run_id, current_user.id))
    return RunResponse(run_id=run_id)


# ────────────── 成稿阶段 ──────────────
async def _run_draft(req: DraftRequest, run_id: str, user_id: int):
    try:
        async def cb(ev):
            await progress_store.push(run_id, ev)
        research = ProductResearch.from_dict(req.research)
        result = await generate_practical_draft(
            research, selected=req.selected, template=req.template,
            brief_banned=req.brief_banned, brief_tone=req.brief_tone,
            progress_callback=cb, user_id=user_id,
        )
        await progress_store.push(run_id, {"event": "result", "data": result})
        await track_complete(run_id, result, display_title=result.get("title", "实操成稿"))
        await _deduct(user_id, "practical_draft", run_id)
    except Exception as e:
        logger.error(f"实操成稿失败: {e}", exc_info=True)
        await progress_store.push(run_id, {"event": "error", "data": {"message": str(e)}})
        await track_fail(run_id, str(e))


@router.post("/draft", response_model=RunResponse)
async def start_draft(req: DraftRequest, current_user: User = Depends(get_current_user)):
    await _ensure_credits(current_user.id, "practical_draft")
    run_id = progress_store.create_run()
    product = (req.research or {}).get("product", "")
    await track_start(
        user_id=current_user.id, type="practical_draft", run_id=run_id,
        input_snapshot={"product": product, "selected": req.selected, "template": req.template},
        display_title=f"实操成稿 · {product}",
        resume_context={"route": "/creation/practical", "query": {}},
    )
    spawn(_run_draft(req, run_id, current_user.id))
    return RunResponse(run_id=run_id)


# ────────────── 共用 SSE ──────────────
@router.get("/stream/{run_id}")
async def stream_progress(run_id: str, token: str = Query(None)) -> StreamingResponse:
    if token:
        from app.core.security import decode_token
        if not decode_token(token):
            raise HTTPException(status_code=401, detail="无效的 token")
    if not progress_store.exists(run_id):
        raise HTTPException(status_code=404, detail=f"run {run_id} 不存在或已过期")
    return StreamingResponse(
        progress_store.stream(run_id),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
    )
