"""
芒格版标题生成与评分 API 端点
"""

import logging
from fastapi import APIRouter, HTTPException

from app.schemas.title_munger import (
    MungerGenerationRequest,
    MungerGenerationResponse,
    ScorerRequest,
    ScorerResponse,
)
from app.services.title_munger_generation.service import MungerTitleGenerationService
from app.services.title_scorer.service import TitleScorerService

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/munger-generate", response_model=MungerGenerationResponse)
async def munger_title_generate(request: MungerGenerationRequest):
    """
    芒格版标题生成

    基于文章内容，通过6 Agent协作 + 回环机制生成标题（≤20字）。

    流程:
    1. 策划 Agent → 定位语提取
    2. 缺口/锚点/冲突 Agent → 三维度并行生成
    3. 增强 Agent → 芒格倾向叠加
    4. 审判 Agent → 拇指测试+红线审查
    5. 回环：全部淘汰则重试（≤3轮）
    """
    try:
        service = MungerTitleGenerationService()
        result = await service.generate(request.content)

        return MungerGenerationResponse(
            success=result.get("success", False),
            positioning=result.get("positioning", ""),
            all_titles=[{"title": t.get("title", ""), "dimension": t.get("dimension", "")} for t in result.get("all_titles", [])],
            top5=[{"title": t.get("title", ""), "dimension": t.get("dimension", ""), "enhancement": t.get("enhancement", "")} for t in result.get("top5", [])],
            verdicts=[{"title": v.get("title", ""), "thumb": v.get("thumb", ""), "redline": v.get("redline", ""), "word_count": v.get("word_count", 0), "final_verdict": v.get("final_verdict", "淘汰")} for v in result.get("verdicts", [])],
            final_pick=result.get("final_pick", ""),
            loop_count=result.get("loop_count", 0),
            failure_reasons=result.get("failure_reasons", []),
            duration_seconds=result.get("duration_seconds", 0),
            message=result.get("message", ""),
        )
    except Exception as e:
        logger.error(f"芒格版标题生成失败: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"标题生成失败: {str(e)}")


@router.post("/munger-score", response_model=ScorerResponse)
async def munger_title_score(request: ScorerRequest):
    """
    芒格版标题评分

    对已有标题进行多维度评分、诊断并给出改写建议。

    流程:
    1. 拆解 Agent → 结构化解读
    2. 缺口/锚点/冲突评审 → 三维度评分
    3. 增强评审 → 芒格倾向评分
    4. 红线 Agent → 合规审查
    5. 改写 Agent → 综合诊断 + 改写建议
    """
    try:
        service = TitleScorerService()
        result = await service.score(request.title, request.summary)

        return ScorerResponse(
            success=result.get("success", False),
            title=result.get("title", ""),
            analysis=result.get("analysis", {}),
            scores=result.get("scores", {}),
            redlines=result.get("redlines", {}),
            total_score=result.get("total_score", 0),
            grade=result.get("grade", ""),
            grade_label=result.get("grade_label", ""),
            diagnosis=result.get("diagnosis", {}),
            rewrites=[{"title": r.get("title", ""), "fix": r.get("fix", ""), "keep": r.get("keep", "")} for r in result.get("rewrites", [])],
            duration_seconds=result.get("duration_seconds", 0),
            error=result.get("error"),
        )
    except Exception as e:
        logger.error(f"芒格版标题评分失败: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"标题评分失败: {str(e)}")
