"""积分系统 API 路由。"""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.core.security import get_current_super_admin_user, get_current_user
from app.core.timezone import utcnow
from app.models.admin_audit import AdminAuditLog
from app.models.user import User
from app.services.credit_service import CreditService, get_available_packages, get_operation_costs
from app.core.credit_config import estimate_monthly_cost, FULL_CREATION_FLOW
from app.core.product_access import is_admin_user

router = APIRouter()


async def get_credit_service(db: AsyncSession = Depends(get_db)) -> CreditService:
    return CreditService(db)


# ====== 账户信息 ======

@router.get("/balance", response_model=dict)
async def get_balance(
    current_user: User = Depends(get_current_user),
    credit_service: CreditService = Depends(get_credit_service),
):
    """查询积分余额"""
    balance = await credit_service.get_balance(current_user.id)
    return {
        "code": 200,
        "message": "success",
        "data": {
            "balance": balance,
            "user_id": current_user.id,
        },
    }


@router.get("/account", response_model=dict)
async def get_account_info(
    current_user: User = Depends(get_current_user),
    credit_service: CreditService = Depends(get_credit_service),
):
    """获取积分账户详情"""
    info = await credit_service.get_account_info(current_user.id)
    # 管理员在产品权限层天然拥有创作工具权限，不应因没有普通订阅到期日而被前端误标为不可用。
    if is_admin_user(current_user):
        info.update({
            "is_subscription_active": True,
            "subscription_access": "admin",
            "credit_expiry_policy": "never",
        })
    return {
        "code": 200,
        "message": "success",
        "data": info,
    }


# ====== 积分检查 ======

@router.post("/check", response_model=dict)
async def check_credits(
    operation: str,
    current_user: User = Depends(get_current_user),
    credit_service: CreditService = Depends(get_credit_service),
):
    """检查积分是否足够执行某操作"""
    try:
        result = await credit_service.check_balance(current_user.id, operation)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return {
        "code": 200,
        "message": "success",
        "data": result,
    }


# ====== 交易记录 ======

@router.get("/transactions", response_model=dict)
async def get_transactions(
    type: Optional[str] = Query(None, description="交易类型: purchase/consume/gift/refund"),
    operation: Optional[str] = Query(None, description="操作类型: content_generation/title_generation等"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    credit_service: CreditService = Depends(get_credit_service),
):
    """查询交易记录"""
    offset = (page - 1) * page_size
    transactions = await credit_service.get_transactions(
        user_id=current_user.id,
        type=type,
        operation=operation,
        limit=page_size,
        offset=offset,
    )
    total = await credit_service.get_transaction_count(
        user_id=current_user.id,
        type=type,
    )

    return {
        "code": 200,
        "message": "success",
        "data": {
            "items": transactions,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": (total + page_size - 1) // page_size,
        },
    }


@router.get("/consumption-stats", response_model=dict)
async def get_consumption_stats(
    current_user: User = Depends(get_current_user),
    credit_service: CreditService = Depends(get_credit_service),
):
    """获取消耗统计"""
    stats = await credit_service.get_consumption_stats(current_user.id)
    return {
        "code": 200,
        "message": "success",
        "data": stats,
    }


# ====== 套餐和定价 ======

@router.get("/packages", response_model=dict)
async def list_packages():
    """获取积分套餐列表"""
    packages = await get_available_packages()
    return {
        "code": 200,
        "message": "success",
        "data": {
            "packages": packages,
        },
    }


@router.get("/operation-costs", response_model=dict)
async def list_operation_costs():
    """获取各操作的积分成本配置"""
    costs = get_operation_costs()
    return {
        "code": 200,
        "message": "success",
        "data": {
            "operations": costs,
            "full_creation_flow": FULL_CREATION_FLOW,
        },
    }


@router.get("/estimate", response_model=dict)
async def estimate_cost(
    articles_per_month: int = Query(10, ge=1, le=1000),
):
    """估算月度积分成本"""
    result = estimate_monthly_cost(articles_per_month)
    return {
        "code": 200,
        "message": "success",
        "data": result,
    }


# ====== 管理接口（仅限管理员） ======

@router.post("/admin/gift", response_model=dict)
async def admin_gift_credits(
    user_id: int,
    amount: int,
    request: Request,
    description: str = "管理员赠送",
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_super_admin_user),
    credit_service: CreditService = Depends(get_credit_service),
):
    """管理员赠送积分"""
    if amount <= 0:
        raise HTTPException(status_code=400, detail="赠送积分必须大于0")

    transaction = await credit_service.gift_credits(
        user_id=user_id,
        amount=amount,
        description=description,
    )
    db.add(AdminAuditLog(
        actor_user_id=current_user.id,
        action="credits.gift",
        target_type="user",
        target_id=str(user_id),
        summary=f"赠送积分 {amount} 给用户 {user_id}",
        detail=description,
        metadata_json={
            "target_user_id": user_id,
            "amount": amount,
            "transaction_id": transaction.id,
            "ip": (request.headers.get("x-forwarded-for") or "").split(",", 1)[0].strip()
            or (request.client.host if request.client else None),
            "user_agent": request.headers.get("user-agent"),
        },
        occurred_at=utcnow(),
    ))
    await db.commit()
    await db.refresh(transaction)

    return {
        "code": 200,
        "message": f"成功赠送 {amount} 积分给用户 {user_id}",
        "data": transaction.to_dict(),
    }
