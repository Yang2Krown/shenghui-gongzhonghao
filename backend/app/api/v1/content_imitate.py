"""内容仿写 API 路由。"""

import logging
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Optional

from app.services.content_imitate_service import imitate_content

logger = logging.getLogger(__name__)
router = APIRouter()


class ContentImitateRequest(BaseModel):
    """内容仿写请求"""
    content: str = Field(..., min_length=1, description="参考内容")
    title: Optional[str] = Field(None, description="参考内容标题")
    extra_requirements: Optional[str] = Field(None, description="额外要求")


@router.post("/imitate")
async def imitate(req: ContentImitateRequest):
    """
    学习参考内容的风格，创作原创内容

    仿写功能会分析参考内容的结构、语言风格、情感表达等特点，
    然后基于这些特点创作一篇全新的原创内容。
    """
    try:
        result = await imitate_content(
            reference_content=req.content,
            reference_title=req.title,
            extra_requirements=req.extra_requirements,
        )

        if not result.get("success"):
            raise HTTPException(status_code=400, detail=result.get("error", "仿写失败"))

        data = result.get("data", {})
        return {
            "title": data.get("title", ""),
            "content": data.get("content", ""),
            "tags": data.get("tags", []),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"内容仿写失败: {e}")
        raise HTTPException(status_code=500, detail=f"仿写失败: {str(e)}")
