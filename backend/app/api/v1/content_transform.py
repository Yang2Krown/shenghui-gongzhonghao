"""内容转写 API 路由。"""

import logging
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from typing import Optional

from app.core.security import get_current_user
from app.models.user import User
from app.services.content_generation.content_transform_service import transform_content
from app.services.credit_service import CreditService
from app.db.session import AsyncSessionLocal

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
async def transform(
    req: ContentTransformRequest,
    current_user: User = Depends(get_current_user),
):
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
    # 检查积分
    async with AsyncSessionLocal() as credit_db:
        credit_service = CreditService(credit_db)
        balance_check = await credit_service.check_balance(current_user.id, "content_transform")
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
        
        # 成功后扣减积分
        try:
            async with AsyncSessionLocal() as credit_db:
                credit_svc = CreditService(credit_db)
                await credit_svc.deduct_credits(
                    user_id=current_user.id,
                    operation="content_transform",
                )
                await credit_db.commit()
        except Exception as credit_err:
            logger.warning(f"积分扣费失败: {credit_err}")
        
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
