"""内容转写 API 路由。"""

import logging
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Optional

from app.services.content_transform_service import transform_content

logger = logging.getLogger(__name__)
router = APIRouter()


class ContentTransformRequest(BaseModel):
    """内容转写请求"""
    content: str = Field(..., min_length=1, description="原文内容")
    source_platform: str = Field(..., description="源平台 (wechat/xhs/douyin/zhihu)")
    target_platform: str = Field(..., description="目标平台 (wechat/xhs)")
    original_title: Optional[str] = Field(None, description="原文章标题")
    extra_requirements: Optional[str] = Field(None, description="额外要求")


@router.post("/transform")
async def transform(req: ContentTransformRequest):
    """
    将内容从一个平台转写成另一个平台的风格

    支持的平台组合（8种）：
    - 公众号 → 小红书
    - 小红书 → 公众号
    - 抖音 → 小红书
    - 抖音 → 公众号
    - 知乎 → 小红书
    - 知乎 → 公众号
    - 公众号 → 抖音
    - 公众号 → 知乎
    """
    try:
        result = await transform_content(
            content=req.content,
            source_platform=req.source_platform,
            target_platform=req.target_platform,
            original_title=req.original_title,
            extra_requirements=req.extra_requirements,
        )

        if not result.get("success"):
            raise HTTPException(status_code=400, detail=result.get("error", "转写失败"))

        data = result.get("data", {})
        return {
            "title": data.get("title", ""),
            "content": data.get("content", ""),
            "tags": data.get("tags", []),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"内容转写失败: {e}")
        raise HTTPException(status_code=500, detail=f"转写失败: {str(e)}")
