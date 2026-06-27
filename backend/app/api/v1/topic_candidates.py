"""候选选题 API。

提供候选选题列表、每日清单等接口。
"""

import asyncio
import logging
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.core.security import get_current_user
from app.core.progress import progress_store
from app.core.background import spawn
from app.db.session import get_db
from app.models.user import User
from app.models.topic_candidate import TopicCandidate, PersonaReview, CandidateScore
from app.models.info_cluster import InfoCluster
from app.services.topic_mining.agent_a_deriver import derive_candidates
from app.services.topic_mining.agent_a2_feasibility import audit_feasibility
from app.services.topic_mining.agent_b_scorer import score_candidates
from app.services.topic_mining.schemas import InfoClusterInput, AgentA2Input, AgentBInput
from app.services.preprocess.rules import is_ai_related

logger = logging.getLogger(__name__)
router = APIRouter()

@router.post("/mine", response_model=dict)
async def trigger_mining(
    body: dict = {},
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    """触发选题挖掘任务。

    body 接受两种调用方式：
    - {"cluster_id": 18}                 → 挖指定簇（前端"立即挖掘"按钮）
    - {"limit": 3, "min_heat_score": 4}  → 批量挖未挖掘的热门簇
    """
    cluster_id = body.get("cluster_id")
    if cluster_id is not None:
        return await _mine_one(db, int(cluster_id), current_user.id)

    limit = int(body.get("limit", 3))
    min_heat = float(body.get("min_heat_score", 0))
    result = await _run_mining_batch(db, limit, min_heat, current_user.id)
    return {"code": 200, "message": "挖掘完成", "data": result}


@router.post("/mine-adhoc", response_model=dict)
async def trigger_adhoc_mining(
    body: dict = {},
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    """从自由输入的信息源触发选题挖掘，写入数据库。

    body 格式：
    {
        "sources": [
            {"type": "text", "content": "文字内容..."},
            {"type": "link", "content": "https://..."},
            {"type": "file", "content": "文件内容（已解析的文本）..."}
        ],
        "preference": "可选的创作风格偏好"
    }
    """
    sources = body.get("sources", [])
    preference = body.get("preference", "")

    if not sources:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="至少提供一个信息源",
        )

    # 合并所有信息源内容
    from app.services.scraping.link_extractor import extract_link_content
    combined_text_parts = []
    for src in sources:
        content = (src.get("content") or "").strip()
        src_type = src.get("type", "text")

        if content:
            if src_type == "link":
                # 链接类型：调用链接提取服务获取实际内容
                try:
                    extracted = await extract_link_content(content)
                    title = extracted.get("title", "")
                    text_content = extracted.get("content", "")
                    author = extracted.get("author", "")
                    platform = extracted.get("platform", "")

                    # 组合提取结果
                    parts = []
                    if title:
                        parts.append(f"标题：{title}")
                    if author:
                        parts.append(f"作者：{author}")
                    if text_content:
                        parts.append(text_content)

                    combined_text_parts.append("\n".join(parts) if parts else content)
                except Exception as e:
                    # 提取失败时降级使用原始链接
                    combined_text_parts.append(content)
            else:
                # 文本/文件类型：直接使用
                combined_text_parts.append(content)

    if not combined_text_parts:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="信息源内容不能为空",
        )

    combined_text = "\n\n".join(combined_text_parts)

    # 从合并文本中提取标题
    lines = combined_text.strip().split("\n")
    core_title = lines[0][:80] if lines else combined_text[:80]

    # 1. 创建 InfoCluster 记录
    cluster = InfoCluster(
        core_title=core_title,
        summary=combined_text[:500] if len(combined_text) > 500 else combined_text,
        info_type="资讯型",
        direction=None,
        elements={},
        freshness="today",
        heat_score=5.0,
        source_urls=[],
        mined=False,
    )
    db.add(cluster)
    await db.commit()
    await db.refresh(cluster)

    run_id = progress_store.create_run()
    owner_id = current_user.id  # 背景任务里没有 request 上下文，先抓出来

    async def _run():
        from app.db.session import AsyncSessionLocal
        async with AsyncSessionLocal() as bg_db:
            try:
                async def _progress_cb(event):
                    await progress_store.push(run_id, event)

                # 重新加载 cluster
                bg_cluster = (await bg_db.execute(
                    select(InfoCluster).where(InfoCluster.id == cluster.id)
                )).scalar_one_or_none()
                if not bg_cluster:
                    raise RuntimeError(f"InfoCluster {cluster.id} 已不存在")

                # 构造 InfoClusterInput
                info_input = InfoClusterInput(
                    cluster_id=bg_cluster.id,
                    core_title=core_title,
                    summary=bg_cluster.summary or "",
                    info_type="资讯型",
                    direction=None,
                    elements={},
                    freshness="today",
                    heat_score=5.0,
                    low_fan_hit=False,
                    source_urls=[],
                )

                # Agent A: 衍生候选选题
                await _progress_cb({
                    "event": "step_start",
                    "data": {"step": 1, "agent": "沈知远 · 选题衍生员", "action": "正在分析信息源，衍生候选选题...", "avatar": "/agents/agent-a.png"},
                })
                candidates_a = await derive_candidates(info_input)
                await _progress_cb({
                    "event": "step_done",
                    "data": {"step": 1, "agent": "沈知远 · 选题衍生员"},
                })

                # Agent A2: 可写性审计（联网搜索验证）
                await _progress_cb({
                    "event": "step_start",
                    "data": {"step": 2, "agent": "叶知秋 · 可写性审计员", "action": "正在联网搜索验证选题可写性...", "avatar": "/agents/agent-a2.png"},
                })
                a2_input = AgentA2Input(
                    cluster_id=bg_cluster.id,
                    core_title=core_title,
                    info_type="资讯型",
                    freshness="today",
                    summary=bg_cluster.summary or "",
                    source_urls=[],
                    candidates=candidates_a,
                )
                result_a2 = await audit_feasibility(a2_input)
                feasibility_map = {c.candidate_id: c for c in result_a2.candidates}
                # 过滤 fail 的选题
                candidates_for_b = [c for c in candidates_a if feasibility_map.get(c.candidate_id, None) and feasibility_map[c.candidate_id].verdict != "fail"]
                if not candidates_for_b:
                    candidates_for_b = candidates_a  # 降级：全部通过
                await _progress_cb({
                    "event": "step_done",
                    "data": {"step": 2, "agent": "叶知秋 · 可写性审计员"},
                })

                # Agent B: 评分
                await _progress_cb({
                    "event": "step_start",
                    "data": {"step": 3, "agent": "白景明 · 选题评分员", "action": "正在评分评估候选选题...", "avatar": "/agents/agent-b.png"},
                })
                b_input = AgentBInput(
                    cluster_id=bg_cluster.id,
                    core_title=core_title,
                    info_type="资讯型",
                    freshness="today",
                    candidates=candidates_a,
                )
                result_b = await score_candidates(b_input)
                await _progress_cb({
                    "event": "step_done",
                    "data": {"step": 3, "agent": "白景明 · 选题评分员"},
                })

                # 写入数据库
                total_candidates = 0
                angles = []
                for scored in result_b.candidates:
                    fb = feasibility_map.get(scored.candidate_id)
                    tc = TopicCandidate(
                        user_id=owner_id,
                        info_cluster_id=bg_cluster.id,
                        title=scored.title,
                        summary=fb.enriched_summary if fb and fb.enriched_summary else scored.summary,
                        direction=scored.direction,
                        routine=scored.routine,
                        dimension_combo=scored.dimension_combo,
                        value_promise=scored.value_promise,
                        angle_note=scored.angle_note,
                        persona_divergence=scored.persona_divergence,
                        persona_divergence_flag=scored.persona_divergence_flag,
                        veto_passed=scored.veto_passed,
                        veto_reasons=scored.veto_reasons,
                        business_sensitive=scored.business_sensitive,
                        weighted_score=scored.weighted_score,
                        verdict=scored.verdict,
                        enriched_summary=fb.enriched_summary if fb else None,
                        feasibility_score=fb.feasibility_score if fb else None,
                        feasibility_passed=fb.feasibility_passed if fb else True,
                        feasibility_verdict=fb.verdict if fb else None,
                        feasibility_evidence=[e.model_dump() for e in fb.evidence] if fb else [],
                        feasibility_reasoning=fb.reasoning if fb else None,
                        feasibility_rewrite_suggestion=fb.rewrite_suggestion if fb else None,
                    )
                    bg_db.add(tc)
                    await bg_db.flush()

                    for pr in scored.persona_reviews:
                        bg_db.add(PersonaReview(
                            candidate_id=tc.id,
                            persona=pr.persona,
                            score=pr.score,
                            rationale=pr.rationale,
                        ))
                    bg_db.add(CandidateScore(
                        candidate_id=tc.id,
                        pain_point=scored.pain_point.score,
                        value_density=scored.value_density.score,
                        propagation=scored.propagation.score,
                        differentiation=scored.differentiation.score,
                        freshness=scored.freshness.score,
                        audience_fit=scored.audience_fit.score,
                        evidence={
                            "pain_point": scored.pain_point.evidence,
                            "value_density": scored.value_density.evidence,
                            "propagation": scored.propagation.evidence,
                            "differentiation": scored.differentiation.evidence,
                            "freshness": scored.freshness.evidence,
                            "audience_fit": scored.audience_fit.evidence,
                        },
                    ))

                    angles.append({
                        "id": tc.id,
                        "title": scored.title,
                        "summary": scored.summary,
                        "direction": scored.direction,
                        "routine": scored.routine,
                        "value_promise": scored.value_promise,
                        "angle_note": scored.angle_note,
                        "weighted_score": scored.weighted_score,
                        "verdict": scored.verdict,
                        "veto_passed": scored.veto_passed,
                        "persona_reviews": [
                            {"persona": pr.persona, "score": pr.score, "rationale": pr.rationale}
                            for pr in scored.persona_reviews
                        ],
                        "score": {
                            "pain_point": scored.pain_point.score,
                            "value_density": scored.value_density.score,
                            "propagation": scored.propagation.score,
                            "differentiation": scored.differentiation.score,
                            "freshness": scored.freshness.score,
                            "audience_fit": scored.audience_fit.score,
                            "evidence": {
                                "pain_point": scored.pain_point.evidence,
                                "value_density": scored.value_density.evidence,
                                "propagation": scored.propagation.evidence,
                                "differentiation": scored.differentiation.evidence,
                                "freshness": scored.freshness.evidence,
                                "audience_fit": scored.audience_fit.evidence,
                            },
                        },
                    })
                    total_candidates += 1

                # 标记 cluster 已挖掘
                bg_cluster.mined = True
                await bg_db.commit()

                await progress_store.push(run_id, {
                    "event": "result",
                    "data": {
                        "cluster_id": bg_cluster.id,
                        "angles": angles,
                        "total": total_candidates,
                        "stats": result_b.stats,
                    },
                })
            except Exception as e:
                logger.exception("自由输入挖掘失败")
                await progress_store.push(run_id, {
                    "event": "error",
                    "data": {"message": f"挖掘失败: {type(e).__name__}: {str(e)[:200]}"},
                })

    spawn(_run())

    return {"code": 200, "message": "挖掘任务已提交", "data": {"run_id": run_id, "cluster_id": cluster.id}}


@router.post("/create-adhoc", response_model=dict)
async def create_adhoc_candidate(
    body: dict = {},
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    """从自由输入的信息源同步创建候选选题，直接返回 candidate_id。

    用于大纲生成流程：输入信息源 → 创建候选 → 跳转创作页自动生成大纲。
    """
    sources = body.get("sources", [])
    preference = body.get("preference", "")

    if not sources:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="至少提供一个信息源",
        )

    # 合并所有信息源内容
    from app.services.scraping.link_extractor import extract_link_content
    combined_text_parts = []
    for src in sources:
        content = (src.get("content") or "").strip()
        src_type = src.get("type", "text")

        if content:
            if src_type == "link":
                try:
                    extracted = await extract_link_content(content)
                    title = extracted.get("title", "")
                    text_content = extracted.get("content", "")
                    author = extracted.get("author", "")
                    parts = []
                    if title:
                        parts.append(f"标题：{title}")
                    if author:
                        parts.append(f"作者：{author}")
                    if text_content:
                        parts.append(text_content)
                    combined_text_parts.append("\n".join(parts) if parts else content)
                except Exception:
                    combined_text_parts.append(content)
            else:
                combined_text_parts.append(content)

    combined_text = "\n\n".join(combined_text_parts).strip()
    if not combined_text:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="信息源内容为空",
        )

    # 取前 200 字作为摘要，截断最后一个完整句子
    summary = combined_text[:200]
    last_period = max(summary.rfind("。"), summary.rfind("！"), summary.rfind("？"), summary.rfind("."))
    if last_period > 50:
        summary = summary[:last_period + 1]

    # 取前 30 字作为标题
    title = combined_text[:30]
    last_boundary = max(title.rfind("，"), title.rfind("。"), title.rfind(" "), title.rfind("\n"))
    if last_boundary > 10:
        title = title[:last_boundary]

    # 创建 InfoCluster
    cluster = InfoCluster(
        core_title=title,
        summary=summary,
        source_count=len(sources),
        mined=False,
    )
    db.add(cluster)
    await db.flush()

    # 创建 TopicCandidate
    candidate = TopicCandidate(
        user_id=current_user.id,
        info_cluster_id=cluster.id,
        title=title,
        summary=summary,
        direction="",
        routine="",
        value_promise="",
        angle_note=preference or "",
        veto_passed=True,
        verdict="selected",
    )
    db.add(candidate)
    await db.commit()
    await db.refresh(candidate)

    return {
        "code": 200,
        "message": "候选选题已创建",
        "data": {
            "candidate_id": candidate.id,
            "title": candidate.title,
            "cluster_id": cluster.id,
        },
    }


@router.get("/progress/{run_id}", response_model=dict)
async def get_mining_progress(
    run_id: str,
    current_user: User = Depends(get_current_user),
) -> Any:
    """轮询式进度查询（绕开 SSE，避免反向代理缓冲流式响应）。

    前端每隔 1-2 秒查一次，返回当前步骤 / Agent / 是否完成 / 结果。
    """
    snap = progress_store.snapshot(run_id)
    if snap is None:
        return {"code": 404, "message": "run 不存在或已过期", "data": {"exists": False}}
    return {"code": 200, "message": "ok", "data": snap}


@router.get("/stream/{run_id}")
async def stream_mining_progress(
    run_id: str,
    token: str = Query(None, description="认证 token（EventSource 不支持 header）"),
) -> StreamingResponse:
    """SSE 端点：实时推送选题挖掘进度。"""
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


async def _mine_one(db: AsyncSession, cluster_id: int, user_id: int) -> dict:
    """挖单个指定簇。返回 run_id，前端通过轮询获取实时进度。"""
    logger.info(f"[mine] 开始挖掘 cluster_id={cluster_id} user_id={user_id}")
    cluster = (await db.execute(
        select(InfoCluster).where(InfoCluster.id == cluster_id)
    )).scalar_one_or_none()

    if not cluster:
        raise HTTPException(status_code=404, detail=f"话题 {cluster_id} 不存在")

    # 「已挖掘」按用户判断：当前用户已有候选 且 簇没有新内容 → 跳过
    already_mined = (await db.execute(
        select(func.count(TopicCandidate.id)).where(
            TopicCandidate.info_cluster_id == cluster_id,
            TopicCandidate.user_id == user_id,
        )
    )).scalar() or 0
    if already_mined and not cluster.needs_update:
        return {"code": 200, "message": "已挖掘过", "data": {"cluster_id": cluster_id, "skipped": True}}

    if not cluster.info_type:
        raise HTTPException(
            status_code=400,
            detail="该话题还未完成预处理（缺 info_type），请等预处理跑完再挖掘"
        )

    _title = " ".join(filter(None, [cluster.core_title, getattr(cluster, "core_title_zh", None)]))
    _summary = " ".join(filter(None, [cluster.summary, getattr(cluster, "summary_zh", None)]))
    if not is_ai_related(_title, _summary):
        raise HTTPException(
            status_code=400,
            detail="该话题与 AI 无关，跳过挖掘"
        )

    run_id = progress_store.create_run()

    async def _run():
        from app.db.session import AsyncSessionLocal
        async with AsyncSessionLocal() as bg_db:
            try:
                async def _progress_cb(event):
                    await progress_store.push(run_id, event)

                # 关键：必须用 bg_db 重新 fetch cluster，
                # 否则 cluster.mined = True 写到旧 session 上，commit 不到 DB
                bg_cluster = (await bg_db.execute(
                    select(InfoCluster).where(InfoCluster.id == cluster_id)
                )).scalar_one_or_none()
                if not bg_cluster:
                    raise RuntimeError(f"cluster {cluster_id} 已不存在")

                stats = await _mine_cluster_inner(bg_db, bg_cluster, user_id, progress_callback=_progress_cb)
                await bg_db.commit()
                await progress_store.push(run_id, {
                    "event": "result",
                    "data": {"cluster_id": cluster_id, **stats},
                })
            except Exception as e:
                await bg_db.rollback()
                logger.exception(f"挖掘 cluster {cluster_id} 失败")
                await progress_store.push(run_id, {
                    "event": "error",
                    "data": {"message": f"挖掘失败: {type(e).__name__}: {str(e)[:200]}"},
                })

    spawn(_run())

    return {"code": 200, "message": "挖掘任务已提交", "data": {"run_id": run_id}}


async def _run_mining_batch(db: AsyncSession, limit: int, min_heat_score: float, user_id: int) -> dict:
    """批量挖热门簇，结果归 user_id。
    ponytail: 簇筛选仍用全局 mined 标记（非用户面板入口，前端只走单簇挖掘），
    够用；要做到逐用户去重再换成 per-user EXISTS 子查询。"""
    clusters = (await db.execute(
        select(InfoCluster).where(
            (InfoCluster.mined.is_(False) | InfoCluster.needs_update.is_(True)),
            InfoCluster.info_type.is_not(None),
            InfoCluster.heat_score >= min_heat_score,
        ).order_by(InfoCluster.heat_score.desc()).limit(limit * 3)  # 多取一些，过滤后可能不够
    )).scalars().all()

    # 过滤非 AI 内容：原文 + 中文翻译都喂进去
    def _passes(c):
        title = " ".join(filter(None, [c.core_title, getattr(c, "core_title_zh", None)]))
        summary = " ".join(filter(None, [c.summary, getattr(c, "summary_zh", None)]))
        return is_ai_related(title, summary)
    clusters = [c for c in clusters if _passes(c)][:limit]

    if not clusters:
        return {"mined": 0, "message": "没有待挖掘的话题"}

    mined = 0
    total_candidates = 0
    errors = []
    for cluster in clusters:
        try:
            stats = await _mine_cluster_inner(db, cluster, user_id)
            await db.commit()
            mined += 1
            total_candidates += stats["total_candidates"]
        except Exception as e:
            await db.rollback()
            errors.append({"cluster_id": cluster.id, "error": f"{type(e).__name__}: {str(e)[:120]}"})

    return {"mined": mined, "total_candidates": total_candidates, "errors": errors}


async def _mine_cluster_inner(
    db: AsyncSession,
    cluster: InfoCluster,
    user_id: int,
    progress_callback=None,
) -> dict:
    """挖单个簇的核心逻辑：Agent A → Agent B → 写库（不 commit，调用方决定）。
    候选归 user_id。重新挖掘只清理「该用户」在此簇下的旧候选，不动别人的。"""

    # 重新挖掘时：先删除当前用户在此簇下的旧候选选题
    old_cand_ids = [c.id for c in (await db.execute(
        select(TopicCandidate.id).where(
            TopicCandidate.info_cluster_id == cluster.id,
            TopicCandidate.user_id == user_id,
        )
    )).scalars().all()]
    if old_cand_ids:
        from sqlalchemy import delete
        await db.execute(delete(PersonaReview).where(PersonaReview.candidate_id.in_(old_cand_ids)))
        await db.execute(delete(CandidateScore).where(CandidateScore.candidate_id.in_(old_cand_ids)))
        await db.execute(delete(TopicCandidate).where(TopicCandidate.id.in_(old_cand_ids)))
        await db.flush()

    async def _emit(event):
        if progress_callback:
            await progress_callback(event)

    info_input = InfoClusterInput(
        cluster_id=cluster.id,
        core_title=cluster.core_title,
        # 优先用 enricher 基于正文生成的事实摘要，回退到原始种子摘要
        summary=cluster.summary_zh or cluster.summary,
        info_type=cluster.info_type or "资讯型",
        direction=cluster.direction,
        elements=cluster.elements or {},
        freshness=cluster.freshness,
        heat_score=cluster.heat_score or 0.0,
        low_fan_hit=cluster.low_fan_hit or False,
        source_urls=cluster.source_urls or [],
    )

    # Agent A
    await _emit({"event": "step_start", "data": {"step": 1, "agent": "沈知远 · 选题衍生员", "action": "正在衍生候选选题...", "avatar": "/agents/agent-a.png"}})
    candidates_a = await derive_candidates(info_input)
    await _emit({"event": "step_done", "data": {"step": 1, "agent": "沈知远 · 选题衍生员"}})

    # Agent A2: 可写性审计
    await _emit({"event": "step_start", "data": {"step": 2, "agent": "叶知秋 · 可写性审计员", "action": "正在联网搜索验证选题可写性...", "avatar": "/agents/agent-a2.png"}})
    a2_input = AgentA2Input(
        cluster_id=cluster.id,
        core_title=cluster.core_title,
        info_type=cluster.info_type or "资讯型",
        freshness=cluster.freshness,
        summary=cluster.summary_zh or cluster.summary,
        source_urls=cluster.source_urls or [],
        candidates=candidates_a,
    )
    result_a2 = await audit_feasibility(a2_input)
    feasibility_map = {c.candidate_id: c for c in result_a2.candidates}
    candidates_for_b = [c for c in candidates_a if feasibility_map.get(c.candidate_id) and feasibility_map[c.candidate_id].verdict != "fail"]
    if not candidates_for_b:
        candidates_for_b = candidates_a
    await _emit({"event": "step_done", "data": {"step": 2, "agent": "叶知秋 · 可写性审计员"}})

    # Agent B
    await _emit({"event": "step_start", "data": {"step": 3, "agent": "白景明 · 选题评分员", "action": "正在评分评估候选选题...", "avatar": "/agents/agent-b.png"}})
    b_input = AgentBInput(
        cluster_id=cluster.id,
        core_title=cluster.core_title,
        info_type=cluster.info_type or "资讯型",
        freshness=cluster.freshness,
        candidates=candidates_for_b,
    )
    result_b = await score_candidates(b_input)
    await _emit({"event": "step_done", "data": {"step": 3, "agent": "白景明 · 选题评分员"}})

    total_candidates = 0
    for scored in result_b.candidates:
        fb = feasibility_map.get(scored.candidate_id)
        tc = TopicCandidate(
            user_id=user_id,
            info_cluster_id=cluster.id,
            title=scored.title,
            summary=fb.enriched_summary if fb and fb.enriched_summary else scored.summary,
            direction=scored.direction,
            routine=scored.routine,
            dimension_combo=scored.dimension_combo,
            value_promise=scored.value_promise,
            angle_note=scored.angle_note,
            persona_divergence=scored.persona_divergence,
            persona_divergence_flag=scored.persona_divergence_flag,
            veto_passed=scored.veto_passed,
            veto_reasons=scored.veto_reasons,
            business_sensitive=scored.business_sensitive,
            weighted_score=scored.weighted_score,
            verdict=scored.verdict,
            enriched_summary=fb.enriched_summary if fb else None,
            feasibility_score=fb.feasibility_score if fb else None,
            feasibility_passed=fb.feasibility_passed if fb else True,
            feasibility_verdict=fb.verdict if fb else None,
            feasibility_evidence=[e.model_dump() for e in fb.evidence] if fb else [],
            feasibility_reasoning=fb.reasoning if fb else None,
            feasibility_rewrite_suggestion=fb.rewrite_suggestion if fb else None,
        )
        db.add(tc)
        await db.flush()   # ← 关键修复：必须 await，否则 tc.id 还是 None

        for pr in scored.persona_reviews:
            db.add(PersonaReview(
                candidate_id=tc.id,
                persona=pr.persona,
                score=pr.score,
                rationale=pr.rationale,
            ))
        db.add(CandidateScore(
            candidate_id=tc.id,
            pain_point=scored.pain_point.score,
            value_density=scored.value_density.score,
            propagation=scored.propagation.score,
            differentiation=scored.differentiation.score,
            freshness=scored.freshness.score,
            audience_fit=scored.audience_fit.score,
            evidence={
                "pain_point": scored.pain_point.evidence,
                "value_density": scored.value_density.evidence,
                "propagation": scored.propagation.evidence,
                "differentiation": scored.differentiation.evidence,
                "freshness": scored.freshness.evidence,
                "audience_fit": scored.audience_fit.evidence,
            },
        ))
        total_candidates += 1

    cluster.mined = True
    cluster.needs_update = False
    return {"total_candidates": total_candidates, **result_b.stats}


@router.get("", response_model=dict)
async def get_topic_candidates(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    verdict: Optional[str] = Query(None),
    direction: Optional[str] = Query(None),
    min_score: Optional[float] = Query(None, ge=0, le=10),
    keyword: Optional[str] = Query(None),
    sort_by: str = Query("weighted_score"),
    sort_order: str = Query("desc"),
) -> Any:
    skip = (page - 1) * page_size

    # 构建查询（只看自己挖掘/创建的候选）
    query = select(TopicCandidate).options(
        joinedload(TopicCandidate.persona_reviews),
        joinedload(TopicCandidate.score),
    ).where(TopicCandidate.user_id == current_user.id)

    # 筛选
    if verdict:
        query = query.where(TopicCandidate.verdict == verdict)
    if direction:
        query = query.where(TopicCandidate.direction == direction)
    if min_score is not None:
        query = query.where(TopicCandidate.weighted_score >= min_score)
    if keyword:
        query = query.where(TopicCandidate.title.ilike(f"%{keyword}%"))

    # 总数
    count_query = select(func.count(TopicCandidate.id)).where(TopicCandidate.user_id == current_user.id)
    if verdict:
        count_query = count_query.where(TopicCandidate.verdict == verdict)
    if direction:
        count_query = count_query.where(TopicCandidate.direction == direction)
    if min_score is not None:
        count_query = count_query.where(TopicCandidate.weighted_score >= min_score)
    if keyword:
        count_query = count_query.where(TopicCandidate.title.ilike(f"%{keyword}%"))
    total_result = await db.execute(count_query)
    total = total_result.scalar()

    # 排序
    order_col = getattr(TopicCandidate, sort_by, TopicCandidate.weighted_score)
    if sort_order == "desc":
        query = query.order_by(desc(order_col))
    else:
        query = query.order_by(order_col)

    query = query.offset(skip).limit(page_size)
    result = await db.execute(query)
    candidates = result.scalars().unique().all()

    return {
        "code": 200,
        "message": "获取候选选题成功",
        "data": {
            "items": [_candidate_to_dict(c) for c in candidates],
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": (total + page_size - 1) // page_size,
        },
    }


@router.get("/stats/overview", response_model=dict)
async def get_stats_overview(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    mine = TopicCandidate.user_id == current_user.id
    total = (await db.execute(select(func.count(TopicCandidate.id)).where(mine))).scalar()
    selected = (await db.execute(
        select(func.count(TopicCandidate.id)).where(mine, TopicCandidate.verdict == "selected")
    )).scalar()
    backup = (await db.execute(
        select(func.count(TopicCandidate.id)).where(mine, TopicCandidate.verdict == "backup")
    )).scalar()
    rejected = (await db.execute(
        select(func.count(TopicCandidate.id)).where(mine, TopicCandidate.verdict == "rejected")
    )).scalar()
    vetoed = (await db.execute(
        select(func.count(TopicCandidate.id)).where(mine, TopicCandidate.verdict == "vetoed")
    )).scalar()

    direction_result = await db.execute(
        select(TopicCandidate.direction, func.count(TopicCandidate.id)).where(mine).group_by(TopicCandidate.direction)
    )
    direction_stats = {d: c for d, c in direction_result.all()}

    return {
        "code": 200,
        "message": "获取统计成功",
        "data": {
            "total": total or 0,
            "selected": selected or 0,
            "backup": backup or 0,
            "rejected": rejected or 0,
            "vetoed": vetoed or 0,
            "by_direction": direction_stats,
        },
    }


@router.post("/custom", response_model=dict)
async def create_custom_topic(
    body: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    """创建自定义选题。

    用户手动输入选题标题、方向和参考资料，创建一条 TopicCandidate 记录，
    然后可以复用现有的创作工作流（角度体检 → 大纲 → 标题 → 正文）。

    body 格式：
    {
        "title": "选题标题",
        "direction": "资讯型",     # 6 大内容方向之一
        "reference": "参考资料"    # 可选
    }
    """
    title = body.get("title", "").strip()
    direction = body.get("direction", "").strip()
    reference = body.get("reference", "").strip() if body.get("reference") else None

    if not title:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="选题标题不能为空",
        )
    if not direction:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="请选择内容方向",
        )

    valid_directions = ["资讯型", "观点型", "故事型", "干货型", "情感型", "趣味型"]
    if direction not in valid_directions:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"无效的内容方向，可选：{', '.join(valid_directions)}",
        )

    candidate = TopicCandidate(
        user_id=current_user.id,
        title=title,
        direction=direction,
        angle_note=reference,
        info_cluster_id=None,
        verdict="selected",
        veto_passed=True,
    )
    db.add(candidate)
    await db.commit()
    await db.refresh(candidate)

    return {
        "code": 200,
        "message": "自定义选题创建成功",
        "data": {
            "id": candidate.id,
            "title": candidate.title,
            "direction": candidate.direction,
        },
    }


@router.get("/{candidate_id}", response_model=dict)
async def get_topic_candidate(
    candidate_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    result = await db.execute(
        select(TopicCandidate)
        .options(
            joinedload(TopicCandidate.persona_reviews),
            joinedload(TopicCandidate.score),
            joinedload(TopicCandidate.info_cluster),
        )
        .where(
            TopicCandidate.id == candidate_id,
            TopicCandidate.user_id == current_user.id,
        )
    )
    candidate = result.unique().scalar_one_or_none()

    if not candidate:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="候选选题不存在")

    data = _candidate_to_dict(candidate)
    if candidate.info_cluster:
        data["cluster"] = {
            "id": candidate.info_cluster.id,
            "core_title": candidate.info_cluster.core_title,
            "info_type": candidate.info_cluster.info_type,
        }

    return {"code": 200, "message": "获取候选选题详情成功", "data": data}


def _candidate_to_dict(c: TopicCandidate) -> dict:
    persona_reviews = [
        {"persona": pr.persona, "score": pr.score, "rationale": pr.rationale}
        for pr in c.persona_reviews
    ]

    score_data = None
    if c.score:
        score_data = {
            "pain_point": c.score.pain_point,
            "value_density": c.score.value_density,
            "propagation": c.score.propagation,
            "differentiation": c.score.differentiation,
            "freshness": c.score.freshness,
            "audience_fit": c.score.audience_fit,
            "evidence": c.score.evidence,
        }

    return {
        "id": c.id,
        "info_cluster_id": c.info_cluster_id,
        "title": c.title,
        "summary": c.summary,
        "direction": c.direction,
        "routine": c.routine,
        "dimension_combo": c.dimension_combo,
        "value_promise": c.value_promise,
        "angle_note": c.angle_note,
        "persona_divergence": c.persona_divergence,
        "persona_divergence_flag": c.persona_divergence_flag,
        "veto_passed": c.veto_passed,
        "veto_reasons": c.veto_reasons,
        "weighted_score": c.weighted_score,
        "verdict": c.verdict,
        "persona_reviews": persona_reviews,
        "score": score_data,
        "created_at": c.created_at.isoformat() if c.created_at else None,
    }
