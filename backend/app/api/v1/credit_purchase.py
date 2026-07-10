"""积分购买 API：微信支付 Native 下单、回调、状态查询。"""
import logging

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.credit_config import CREDIT_PACKAGES
from app.core.rate_limit import limit_payment_order
from app.core.security import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.services.wechat_pay_service import WechatPayService

logger = logging.getLogger(__name__)
router = APIRouter()


def _find_package(package_name: str):
    for pkg in CREDIT_PACKAGES:
        if pkg["name"] == package_name:
            return pkg
    return None


@router.post("/purchase", response_model=dict)
async def purchase_credits(
    package_name: str,
    request: Request,
    current_user: User = Depends(limit_payment_order),
    db: AsyncSession = Depends(get_db),
):
    """创建微信支付订单，返回扫码支付链接。"""
    package = _find_package(package_name)
    if not package:
        raise HTTPException(status_code=400, detail=f"未知套餐: {package_name}")

    pay_service = WechatPayService(db)
    try:
        order = await pay_service.create_native_order(current_user.id, package)
        await db.commit()
    except ValueError as exc:
        await db.rollback()
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    return {
        "code": 200,
        "message": "微信支付订单创建成功",
        "data": {
            "out_trade_no": order.out_trade_no,
            "code_url": order.code_url,
            "status": order.status,
            "order_type": order.order_type,
            "package": order.package_name,
            "credits": order.credits,
            "amount_fen": order.amount_fen,
            "amount_yuan": order.amount_yuan,
            "test_mode": pay_service.configured and order.amount_fen == 1,
        },
    }


@router.post("/membership", response_model=dict)
async def purchase_membership(
    request: Request,
    current_user: User = Depends(limit_payment_order),
    db: AsyncSession = Depends(get_db),
):
    """兼容旧入口：创建创作工具支付订单。"""
    return await purchase_product("creation_tool", request, current_user, db)


@router.post("/products/{product}", response_model=dict)
async def purchase_product(
    product: str,
    request: Request,
    current_user: User = Depends(limit_payment_order),
    db: AsyncSession = Depends(get_db),
):
    """创建指定产品的微信 Native 支付订单。"""
    from app.core.product_access import ALL_PRODUCTS, PRODUCT_CREATION_TOOL, PRODUCT_LABELS, has_product_access

    if product not in ALL_PRODUCTS:
        raise HTTPException(status_code=400, detail="未知产品")
    # 创作工具为按月订阅，允许已开通用户续订；其它产品一次性开通不可重复购买。
    if product != PRODUCT_CREATION_TOOL and has_product_access(current_user, product):
        raise HTTPException(status_code=400, detail=f"您已经开通{PRODUCT_LABELS[product]}，无需重复购买")

    pay_service = WechatPayService(db)
    try:
        order = await pay_service.create_product_order(current_user.id, product)
        await db.commit()
    except ValueError as exc:
        await db.rollback()
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    return {
        "code": 200,
        "message": f"{PRODUCT_LABELS[product]}支付订单创建成功",
        "data": {
            "out_trade_no": order.out_trade_no,
            "code_url": order.code_url,
            "status": order.status,
            "order_type": order.order_type,
            "product": product,
            "amount_fen": order.amount_fen,
            "amount_yuan": order.amount_yuan,
            "test_mode": pay_service.configured and order.amount_fen == 1,
        },
    }


@router.get("/purchase/status/{out_trade_no}", response_model=dict)
async def purchase_status(
    out_trade_no: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """查询当前用户的支付订单状态，供前端轮询。"""
    pay_service = WechatPayService(db)
    order = await pay_service.get_order(out_trade_no, current_user.id)
    if not order:
        raise HTTPException(status_code=404, detail="订单不存在")

    return {
        "code": 200,
        "message": "ok",
        "data": {
            "out_trade_no": order.out_trade_no,
            "status": order.status,
            "order_type": order.order_type,
            "package": order.package_name,
            "credits": order.credits,
            "amount_yuan": order.amount_yuan,
            "paid_at": order.paid_at.isoformat() if order.paid_at else None,
        },
    }


@router.post("/pay/notify")
async def wechat_pay_notify(
    request: Request,
    wechatpay_timestamp: str = Header(..., alias="Wechatpay-Timestamp"),
    wechatpay_nonce: str = Header(..., alias="Wechatpay-Nonce"),
    wechatpay_signature: str = Header(..., alias="Wechatpay-Signature"),
    wechatpay_serial: str = Header(..., alias="Wechatpay-Serial"),
    db: AsyncSession = Depends(get_db),
):
    """微信支付异步回调。无需登录，依赖微信支付签名验真。"""
    body = (await request.body()).decode("utf-8")
    pay_service = WechatPayService(db)

    try:
        await pay_service.handle_notify(
            body=body,
            timestamp=wechatpay_timestamp,
            nonce=wechatpay_nonce,
            signature=wechatpay_signature,
            serial_no=wechatpay_serial,
        )
        await db.commit()
    except Exception as exc:
        await db.rollback()
        logger.exception("[WechatPay] 回调处理失败")
        return JSONResponse(
            status_code=500,
            content={"code": "FAIL", "message": str(exc)},
        )

    return {"code": "SUCCESS", "message": "成功"}
