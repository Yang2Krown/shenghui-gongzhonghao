"""内容仿写 API 路由。"""

import logging
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from typing import Optional

from app.core.security import get_current_user
from app.models.user import User
from app.services.content_generation.content_imitate_service import imitate_content
from app.services.credit_service import CreditService
from app.db.session import AsyncSessionLocal

logger = logging.getLogger(__name__)
router = APIRouter()


class ContentImitateRequest(BaseModel):
    """内容仿写请求"""
    content: str = Field(..., min_length=1, description="参考内容")
    title: Optional[str] = Field(None, description="参考内容标题")
    extra_requirements: Optional[str] = Field(None, description="额外要求")


@router.post("/imitate")
async def imitate(
    req: ContentImitateRequest,
    current_user: User = Depends(get_current_user),
):
    """
    学习参考内容的风格，创作原创内容

    仿写功能会分析参考内容的结构、语言风格、情感表达等特点，
    然后基于这些特点创作一篇全新的原创内容。
    """
    # 检查积分
    async with AsyncSessionLocal() as credit_db:
        credit_service = CreditService(credit_db)
        balance_check = await credit_service.check_balance(current_user.id, "content_imitate")
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
        result = await imitate_content(
            reference_content=req.content,
            reference_title=req.title,
            extra_requirements=req.extra_requirements,
        )

        if not result.get("success"):
            raise HTTPException(status_code=400, detail=result.get("error", "仿写失败"))

        data = result.get("data", {})
        
        # 成功后扣减积分
        try:
            async with AsyncSessionLocal() as credit_db:
                credit_svc = CreditService(credit_db)
                await credit_svc.deduct_credits(
                    user_id=current_user.id,
                    operation="content_imitate",
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
        logger.error(f"内容仿写失败: {e}")
        raise HTTPException(status_code=500, detail=f"仿写失败: {str(e)}")
