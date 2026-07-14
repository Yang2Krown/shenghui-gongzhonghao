"""积分守卫：检查余额、扣费、退款的装饰器和依赖注入。"""
import logging
from functools import wraps
from typing import Optional, Callable, Any

from fastapi import HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db, AsyncSessionLocal
from app.core.security import get_current_user
from app.models.user import User
from app.services.credit_service import CreditService
from app.core.credit_config import get_operation_credits

logger = logging.getLogger(__name__)


async def get_credit_service(db: AsyncSession = Depends(get_db)) -> CreditService:
    """获取积分服务实例"""
    return CreditService(db)


async def check_credits(
    operation: str,
    current_user: User = Depends(get_current_user),
    credit_service: CreditService = Depends(get_credit_service),
) -> dict:
    """FastAPI 依赖：检查用户积分是否足够
    
    Returns:
        dict: {"user": User, "credit_service": CreditService, "balance": int, "required": int}
    """
    result = await credit_service.check_balance(current_user.id, operation)

    if not result["sufficient"]:
        raise HTTPException(
            status_code=402,  # Payment Required
            detail={
                "code": "INSUFFICIENT_CREDITS",
                "message": f"积分不足，需要 {result['required']} 积分，当前余额 {result['balance']} 积分",
                "balance": result["balance"],
                "required": result["required"],
                "operation": operation,
                "operation_desc": result["operation_desc"],
            },
        )

    return {
        "user": current_user,
        "credit_service": credit_service,
        "balance": result["balance"],
        "required": result["required"],
    }


async def ensure_credits_or_402(user_id: int, operation: str, multiplier: int = 1) -> None:
    """检查余额，不足则抛 402。

    供 spawn / background_task 型端点在创建任务前调用——这类端点会立即返回 run_id，
    若不在此处拦截，积分不足就无法以 402 形式传回前端，只会静默生成或超时。
    """
    async with AsyncSessionLocal() as db:
        result = await CreditService(db).check_balance(user_id, operation, multiplier=multiplier)

    if not result["sufficient"]:
        raise HTTPException(
            status_code=402,
            detail={
                "code": "INSUFFICIENT_CREDITS",
                "message": f"积分不足，需要 {result['required']} 积分，当前余额 {result['balance']} 积分",
                "balance": result["balance"],
                "required": result["required"],
                "operation": operation,
                "operation_desc": result["operation_desc"],
            },
        )


def require_credits(operation: str):
    """装饰器：为路由添加积分检查
    
    Usage:
        @router.post("/generate")
        @require_credits("content_generation")
        async def generate(
            credit_info: dict = Depends(lambda: credit_info),  # 装饰器会注入
            ...
        ):
            # 业务逻辑
            ...
            # 成功后扣费
            await credit_info["credit_service"].deduct_credits(
                user_id=credit_info["user"].id,
                operation="content_generation",
                operation_id=task_id,
            )
    """
    # 返回一个依赖函数
    async def credit_dependency(
        current_user: User = Depends(get_current_user),
        credit_service: CreditService = Depends(get_credit_service),
    ) -> dict:
        return await check_credits(operation, current_user, credit_service)

    return credit_dependency


# ====== 预定义的积分检查依赖 ======
# 在路由中直接使用：credit_info: dict = Depends(check_content_generation_credits)

async def check_topic_mining_credits(
    current_user: User = Depends(get_current_user),
    credit_service: CreditService = Depends(get_credit_service),
) -> dict:
    """检查选题挖掘积分"""
    return await check_credits("topic_mining", current_user, credit_service)


async def check_outline_generation_credits(
    current_user: User = Depends(get_current_user),
    credit_service: CreditService = Depends(get_credit_service),
) -> dict:
    """检查大纲生成积分"""
    return await check_credits("outline_generation", current_user, credit_service)


async def check_content_generation_credits(
    current_user: User = Depends(get_current_user),
    credit_service: CreditService = Depends(get_credit_service),
) -> dict:
    """检查正文生成积分"""
    return await check_credits("content_generation", current_user, credit_service)


async def check_content_polish_credits(
    current_user: User = Depends(get_current_user),
    credit_service: CreditService = Depends(get_credit_service),
) -> dict:
    """检查文案润色积分"""
    return await check_credits("content_polish", current_user, credit_service)


async def check_title_generation_credits(
    current_user: User = Depends(get_current_user),
    credit_service: CreditService = Depends(get_credit_service),
) -> dict:
    """检查标题生成积分"""
    return await check_credits("title_generation", current_user, credit_service)


async def check_content_continuation_credits(
    current_user: User = Depends(get_current_user),
    credit_service: CreditService = Depends(get_credit_service),
) -> dict:
    """检查正文续写积分"""
    return await check_credits("content_continuation", current_user, credit_service)


async def check_content_transform_credits(
    current_user: User = Depends(get_current_user),
    credit_service: CreditService = Depends(get_credit_service),
) -> dict:
    """检查内容转写积分"""
    return await check_credits("content_transform", current_user, credit_service)


async def check_content_imitate_credits(
    current_user: User = Depends(get_current_user),
    credit_service: CreditService = Depends(get_credit_service),
) -> dict:
    """检查内容仿写积分"""
    return await check_credits("content_imitate", current_user, credit_service)


# ====== 业务辅助函数 ======

async def deduct_credits_safe(
    user_id: int,
    operation: str,
    operation_id: Optional[str] = None,
    multiplier: int = 1,
) -> None:
    """成功后扣费：开独立 session、提交、失败只记日志不影响用户。

    供 spawn / background_task 型端点在生成成功后调用（这类端点用 ensure_credits_or_402
    做前置拦截，这里负责事后扣减）。
    """
    try:
        async with AsyncSessionLocal() as db:
            await CreditService(db).deduct_credits(
                user_id=user_id,
                operation=operation,
                operation_id=operation_id,
                multiplier=multiplier,
            )
            await db.commit()
    except Exception as e:
        logger.warning(f"积分扣费失败 (operation={operation}, user={user_id}): {e}")


async def deduct_after_success(
    credit_service: CreditService,
    user_id: int,
    operation: str,
    operation_id: Optional[str] = None,
    token_usage: Optional[dict] = None,
):
    """操作成功后扣减积分
    
    在业务逻辑的 try 块末尾调用：
        try:
            result = await do_something()
            await deduct_after_success(credit_service, user_id, "content_generation", task_id)
            return result
        except Exception:
            raise  # 失败不扣费
    """
    try:
        await credit_service.deduct_credits(
            user_id=user_id,
            operation=operation,
            operation_id=operation_id,
            token_usage=token_usage,
        )
    except Exception as e:
        logger.error(f"积分扣费失败: {e}")
        # 扣费失败不应该影响用户体验，记录日志即可
        # 后续可以通过定时任务补偿
