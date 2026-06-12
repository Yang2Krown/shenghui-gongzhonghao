"""积分购买 API（模拟，后期接入真实支付）。"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.services.credit_service import CreditService
from app.core.credit_config import CREDIT_PACKAGES

router = APIRouter()


@router.post("/purchase", response_model=dict)
async def purchase_credits(
    package_name: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """购买积分套餐（模拟，直接到账）"""
    # 查找套餐
    package = None
    for pkg in CREDIT_PACKAGES:
        if pkg["name"] == package_name:
            package = pkg
            break

    if not package:
        raise HTTPException(status_code=400, detail=f"未知套餐: {package_name}")

    credit_service = CreditService(db)

    # 直接赠送积分（模拟支付成功）
    transaction = await credit_service.purchase_credits(
        user_id=current_user.id,
        package_name=package_name,
        payment_amount_yuan=package["price_yuan"],
        payment_method="demo",  # 模拟支付
    )
    await db.commit()

    # 获取最新余额
    balance = await credit_service.get_balance(current_user.id)

    return {
        "code": 200,
        "message": f"购买成功，获得 {package['credits']} 积分",
        "data": {
            "package": package_name,
            "credits_added": package["credits"],
            "balance": balance,
        },
    }