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
from app.api.v1.progress_access import ensure_run_owner_from_token
from app.core.background import spawn
from app.core.security import get_current_user
from app.core.rate_limit import limit_ai_generation, limit_link_extract
from app.models.user import User
from app.core.generation_tracker import track_start, track_complete, track_fail
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
    reference_links: List[str] = Field(default_factory=list, description="用户提供的参考文章链接")


class ReAnalyzeRequest(BaseModel):
    product: str = Field(..., min_length=1, description="产品 / 工具名")
    brief: str = Field(default="", description="商单 brief（选填）")
    existing_research: dict = Field(..., description="上次的研究结果（用户可能编辑过）")
    new_reference_links: List[str] = Field(..., description="新增的参考链接")


class AnalyzeFeaturesRequest(BaseModel):
    research: dict = Field(..., description="用户确认后的研究结果（可能被编辑过）")


class ValidateLinkRequest(BaseModel):
    url: str = Field(..., description="要验证的链接")


class ValidateLinkResponse(BaseModel):
    valid: bool
    platform: str = ""
    title: str = ""
    message: str = ""


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
async def _run_research(product: str, brief: str, reference_links: List[str], run_id: str, user_id: int):
    try:
        async def cb(ev):
            await progress_store.push(run_id, ev)
        research = await research_product(product, brief, progress_callback=cb, reference_links=reference_links)
        result = research.to_dict()
        await progress_store.push(run_id, {"event": "result", "data": result})
        await track_complete(run_id, result, display_title=f"产品研究 · {product}")
        await _deduct(user_id, "practical_research", run_id)
    except Exception as e:
        logger.error(f"产品研究失败: {e}", exc_info=True)
        await progress_store.push(run_id, {"event": "error", "data": {"message": str(e)}})
        await track_fail(run_id, str(e))


@router.post("/research", response_model=RunResponse)
async def start_research(req: ResearchRequest, current_user: User = Depends(limit_ai_generation)):
    await _ensure_credits(current_user.id, "practical_research")
    run_id = progress_store.create_run(user_id=current_user.id)
    await track_start(
        user_id=current_user.id, type="practical_research", run_id=run_id,
        input_snapshot={"product": req.product, "brief_len": len(req.brief), "reference_links_count": len(req.reference_links)},
        display_title=f"产品研究 · {req.product}",
        resume_context={"route": "/creation/practical", "query": {}},
    )
    spawn(_run_research(req.product, req.brief, req.reference_links, run_id, current_user.id))
    return RunResponse(run_id=run_id)


# ────────────── 成稿阶段 ──────────────
async def _run_re_analyze(req: ReAnalyzeRequest, run_id: str, user_id: int):
    """补充参考链接后重新分析（不额外扣积分）"""
    try:
        async def cb(ev):
            await progress_store.push(run_id, ev)
        from app.services.practical_creation import re_analyze_product
        research = await re_analyze_product(
            req.product, req.brief, req.existing_research, req.new_reference_links,
            progress_callback=cb
        )
        result = research.to_dict()
        await progress_store.push(run_id, {"event": "result", "data": result})
        await track_complete(run_id, result, display_title=f"产品研究（补充）· {req.product}")
        # 不扣积分
    except Exception as e:
        logger.error(f"补充研究失败: {e}", exc_info=True)
        await progress_store.push(run_id, {"event": "error", "data": {"message": str(e)}})
        await track_fail(run_id, str(e))


@router.post("/re-analyze", response_model=RunResponse)
async def re_analyze(req: ReAnalyzeRequest, current_user: User = Depends(limit_ai_generation)):
    """补充参考链接后重新分析（不额外扣积分）"""
    run_id = progress_store.create_run(user_id=current_user.id)
    await track_start(
        user_id=current_user.id, type="practical_research", run_id=run_id,
        input_snapshot={
            "product": req.product,
            "brief_len": len(req.brief),
            "new_links_count": len(req.new_reference_links),
            "is_reanalyze": True,
        },
        display_title=f"产品研究（补充）· {req.product}",
        resume_context={"route": "/creation/practical", "query": {}},
    )
    spawn(_run_re_analyze(req, run_id, current_user.id))
    return RunResponse(run_id=run_id)


async def _run_analyze_features(req: AnalyzeFeaturesRequest, run_id: str, user_id: int):
    """基于用户确认的研究结果分析功能点（不额外扣积分）"""
    try:
        async def cb(ev):
            await progress_store.push(run_id, ev)
        from app.services.practical_creation import analyze_features
        research = await analyze_features(req.research, progress_callback=cb)
        result = research.to_dict()
        await progress_store.push(run_id, {"event": "result", "data": result})
        await track_complete(run_id, result, display_title=f"功能点分析 · {req.research.get('product', '')}")
        # 不扣积分
    except Exception as e:
        logger.error(f"功能点分析失败: {e}", exc_info=True)
        await progress_store.push(run_id, {"event": "error", "data": {"message": str(e)}})
        await track_fail(run_id, str(e))


@router.post("/analyze-features", response_model=RunResponse)
async def analyze_features_endpoint(req: AnalyzeFeaturesRequest, current_user: User = Depends(limit_ai_generation)):
    """基于用户确认的研究结果分析功能点（不额外扣积分）"""
    run_id = progress_store.create_run(user_id=current_user.id)
    product = req.research.get("product", "")
    await track_start(
        user_id=current_user.id, type="practical_research", run_id=run_id,
        input_snapshot={"product": product, "is_analyze_features": True},
        display_title=f"功能点分析 · {product}",
        resume_context={"route": "/creation/practical", "query": {}},
    )
    spawn(_run_analyze_features(req, run_id, current_user.id))
    return RunResponse(run_id=run_id)


@router.post("/validate-link", response_model=ValidateLinkResponse)
async def validate_link(req: ValidateLinkRequest, current_user: User = Depends(limit_link_extract)):
    """验证参考链接是否可访问，并返回平台和标题"""
    from app.services.scraping.link_extractor import extract_link_content, detect_platform, extract_url_from_text

    url = req.url.strip()
    if not url:
        return ValidateLinkResponse(valid=False, message="链接不能为空")

    # 清理链接（处理分享链接格式）
    actual_url = extract_url_from_text(url) or url

    if not actual_url.startswith("http"):
        return ValidateLinkResponse(valid=False, message="链接需要以 http:// 或 https:// 开头")

    # 识别平台
    platform = detect_platform(actual_url)
    platform_names = {"gzh": "公众号", "xhs": "小红书", "zhihu": "知乎", "douyin": "抖音"}
    platform_name = platform_names.get(platform, "网页")

    try:
        result = await extract_link_content(actual_url)
        content = result.get("content", "")
        title = result.get("title", "")

        if content and not content.startswith("暂不支持"):
            return ValidateLinkResponse(
                valid=True,
                platform=platform_name,
                title=(title or "")[:50],
                message=f"✅ {platform_name}文章「{(title or '未知')[:30]}」"
            )
        else:
            return ValidateLinkResponse(
                valid=False,
                platform=platform_name,
                message=f"❌ {platform_name}链接无法抓取内容，请检查链接是否有效"
            )
    except Exception as e:
        logger.error(f"[验证链接] 失败 {url}: {e}")
        return ValidateLinkResponse(
            valid=False,
            platform=platform_name,
            message=f"❌ 验证失败：{str(e)[:50]}"
        )


async def _run_draft(req: DraftRequest, run_id: str, user_id: int):
    try:
        async def cb(ev):
            await progress_store.push(run_id, ev)
        research = ProductResearch.from_dict(req.research)
        async with AsyncSessionLocal() as db:
            from app.services.content_generation.persona import get_user_persona

            persona = await get_user_persona(db, user_id)
        result = await generate_practical_draft(
            research, selected=req.selected, template=req.template,
            brief_banned=req.brief_banned, brief_tone=req.brief_tone,
            progress_callback=cb, user_id=user_id, persona=persona,
        )
        await progress_store.push(run_id, {"event": "result", "data": result})
        await track_complete(run_id, result, display_title=result.get("title", "实操成稿"))
        await _deduct(user_id, "practical_draft", run_id)
    except Exception as e:
        logger.error(f"实操成稿失败: {e}", exc_info=True)
        await progress_store.push(run_id, {"event": "error", "data": {"message": str(e)}})
        await track_fail(run_id, str(e))


@router.post("/draft", response_model=RunResponse)
async def start_draft(req: DraftRequest, current_user: User = Depends(limit_ai_generation)):
    await _ensure_credits(current_user.id, "practical_draft")
    run_id = progress_store.create_run(user_id=current_user.id)
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
    ensure_run_owner_from_token(progress_store, run_id, token)
    return StreamingResponse(
        progress_store.stream(run_id),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
    )
