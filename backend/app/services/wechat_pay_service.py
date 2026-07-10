"""微信支付 v3 Native 扫码支付服务。"""
import base64
import json
import logging
import secrets
import time
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, Optional

import httpx
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.product_access import (
    ALL_PRODUCTS,
    PRODUCT_CREATION_TOOL,
    PRODUCT_LABELS,
    grant_product_access,
    has_product_access,
)
from app.core.timezone import utcnow
from app.models.payment import PaymentOrder
from app.models.user import User
from app.services.credit_service import CreditService

logger = logging.getLogger(__name__)

# 创作工具：699.00 元 = 69900 分（硬编码防篡改）
MEMBERSHIP_FEE_FEN = 69900
# 创作工具首次开通赠送积分
MEMBERSHIP_GIFT_CREDITS = 6000

# 产品价格只在服务端定义，前端展示价格不能作为下单金额来源。
PRODUCT_PLANS = {
    PRODUCT_CREATION_TOOL: {"amount_fen": 69900, "period": "月", "description": "IP罗盘 - 创作工具"},
    "potential_commercial": {"amount_fen": 29900, "period": "月", "description": "IP罗盘 - 潜在商单"},
    "practical_camp": {"amount_fen": 398000, "period": "年", "description": "IP罗盘 - AI垂类公众号实战营"},
}


class WechatPayService:
    """微信支付 v3 Native 支付。"""

    NATIVE_PREPAY_URL = "https://api.mch.weixin.qq.com/v3/pay/transactions/native"

    def __init__(self, db: AsyncSession):
        self.db = db

    @property
    def configured(self) -> bool:
        return all(
            [
                settings.WXPAY_MCH_ID,
                settings.WXPAY_APP_ID,
                settings.WXPAY_API_V3_KEY,
                settings.WXPAY_PRIVATE_KEY_PATH,
                settings.WXPAY_MCH_SERIAL_NO,
                settings.WXPAY_PUBLIC_KEY_PATH,
                settings.WXPAY_PUBLIC_KEY_ID,
                settings.WXPAY_NOTIFY_URL,
            ]
        )

    def require_configured(self) -> None:
        if not self.configured:
            raise ValueError("微信支付未配置，请补齐 WXPAY_* 环境变量")

    async def create_native_order(self, user_id: int, package: Dict[str, Any]) -> PaymentOrder:
        """创建 Native 扫码支付订单。"""
        self.require_configured()

        out_trade_no = self._generate_trade_no()
        amount_fen = 1 if settings.WXPAY_TEST_MODE else int(Decimal(str(package["price_yuan"])) * 100)

        payload = {
            "appid": settings.WXPAY_APP_ID,
            "mchid": settings.WXPAY_MCH_ID,
            "description": f"公众号智能体-{package['name']}",
            "out_trade_no": out_trade_no,
            "notify_url": settings.WXPAY_NOTIFY_URL,
            "amount": {
                "total": amount_fen,
                "currency": "CNY",
            },
        }

        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.post(
                self.NATIVE_PREPAY_URL,
                content=json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
                headers=self._wechat_headers("POST", "/v3/pay/transactions/native", payload),
            )

        if response.status_code >= 400:
            logger.error("[WechatPay] 下单失败 status=%s body=%s", response.status_code, response.text)
            raise ValueError("微信支付下单失败")

        data = response.json()
        code_url = data.get("code_url")
        if not code_url:
            raise ValueError("微信支付未返回二维码链接")

        order = PaymentOrder(
            out_trade_no=out_trade_no,
            user_id=user_id,
            order_type="credits",
            package_name=package["name"],
            amount_fen=amount_fen,
            credits=int(package["credits"]),
            status="PENDING",
            payment_method="wechat",
            code_url=code_url,
        )
        self.db.add(order)
        await self.db.flush()
        logger.info("[WechatPay] 下单成功 out_trade_no=%s user_id=%s", out_trade_no, user_id)
        return order

    async def create_membership_order(self, user_id: int) -> PaymentOrder:
        """兼容旧入口：创建创作工具订单。"""
        return await self.create_product_order(user_id, PRODUCT_CREATION_TOOL)

    async def create_product_order(self, user_id: int, product: str) -> PaymentOrder:
        """创建指定产品的 Native 扫码订单。"""
        self.require_configured()

        if product not in ALL_PRODUCTS or product not in PRODUCT_PLANS:
            raise ValueError("未知产品")
        plan = PRODUCT_PLANS[product]

        # 已拥有产品则拒绝重复下单（创作工具为订阅制，允许续订）。
        user_stmt = select(User).where(User.id == user_id)
        user = (await self.db.execute(user_stmt)).scalar_one_or_none()
        if not user:
            raise ValueError("用户不存在")
        if product != PRODUCT_CREATION_TOOL and has_product_access(user, product):
            raise ValueError(f"您已经开通{PRODUCT_LABELS[product]}，无需重复购买")

        # 复用同一产品待支付订单，防止重复刷单。
        pending_stmt = (
            select(PaymentOrder)
            .where(PaymentOrder.user_id == user_id)
            .where(PaymentOrder.order_type == "product")
            .where(PaymentOrder.package_name == product)
            .where(PaymentOrder.status == "PENDING")
            .order_by(PaymentOrder.created_at.desc())
            .limit(1)
        )
        existing = (await self.db.execute(pending_stmt)).scalar_one_or_none()
        if existing:
            logger.info("[WechatPay] 复用待支付产品订单 out_trade_no=%s product=%s", existing.out_trade_no, product)
            return existing

        # 金额硬编码防篡改；测试模式仍走 0.01 元。
        amount_fen = 1 if settings.WXPAY_TEST_MODE else plan["amount_fen"]

        out_trade_no = self._generate_trade_no()
        payload = {
            "appid": settings.WXPAY_APP_ID,
            "mchid": settings.WXPAY_MCH_ID,
            "description": plan["description"],
            "out_trade_no": out_trade_no,
            "notify_url": settings.WXPAY_NOTIFY_URL,
            "amount": {
                "total": amount_fen,
                "currency": "CNY",
            },
        }

        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.post(
                self.NATIVE_PREPAY_URL,
                content=json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
                headers=self._wechat_headers("POST", "/v3/pay/transactions/native", payload),
            )

        if response.status_code >= 400:
            logger.error("[WechatPay] 产品下单失败 status=%s body=%s", response.status_code, response.text)
            raise ValueError("微信支付下单失败")

        data = response.json()
        code_url = data.get("code_url")
        if not code_url:
            raise ValueError("微信支付未返回二维码链接")

        order = PaymentOrder(
            out_trade_no=out_trade_no,
            user_id=user_id,
            order_type="product",
            package_name=product,
            amount_fen=amount_fen,
            credits=0,
            status="PENDING",
            payment_method="wechat",
            code_url=code_url,
        )
        self.db.add(order)
        await self.db.flush()
        logger.info("[WechatPay] 产品订单创建成功 out_trade_no=%s user_id=%s product=%s", out_trade_no, user_id, product)
        return order

    async def get_order(self, out_trade_no: str, user_id: Optional[int] = None) -> Optional[PaymentOrder]:
        stmt = select(PaymentOrder).where(PaymentOrder.out_trade_no == out_trade_no)
        if user_id is not None:
            stmt = stmt.where(PaymentOrder.user_id == user_id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def handle_notify(
        self,
        body: str,
        timestamp: str,
        nonce: str,
        signature: str,
        serial_no: str,
    ) -> Optional[PaymentOrder]:
        """处理微信回调，验签、解密并幂等入账。"""
        self.require_configured()
        self._verify_signature(timestamp, nonce, body, signature, serial_no)

        payload = json.loads(body)
        resource = payload.get("resource") or {}
        transaction = self._decrypt_resource(resource)

        out_trade_no = transaction.get("out_trade_no")
        trade_state = transaction.get("trade_state")
        transaction_id = transaction.get("transaction_id")
        success_time = transaction.get("success_time")
        logger.info("[WechatPay] 回调 out_trade_no=%s trade_state=%s", out_trade_no, trade_state)

        if not out_trade_no or trade_state != "SUCCESS":
            return None

        order = await self.get_order(out_trade_no)
        if not order:
            logger.warning("[WechatPay] 回调订单不存在 out_trade_no=%s", out_trade_no)
            return None

        # 先校验外部交易数据，再进入数据库行锁；无效回调不应占用/修改订单。
        self._validate_transaction_matches_order(transaction, order)

        # 行锁：防止并发回调重复入账
        lock_stmt = select(PaymentOrder).where(PaymentOrder.id == order.id).with_for_update()
        order = (await self.db.execute(lock_stmt)).scalar_one_or_none()
        if not order:
            return None

        # 锁定后再次校验，确保并发场景中订单记录未被改写。
        self._validate_transaction_matches_order(transaction, order)
        order.notify_raw = body
        if order.status == "PAID":
            return order

        order.status = "PAID"
        order.transaction_id = transaction_id
        order.paid_at = self._parse_success_time(success_time) or utcnow()

        # 根据订单类型执行不同的入账逻辑（同一事务内完成）
        if order.order_type in {"membership", "product"}:
            # 历史 membership 订单默认是创作工具；新订单记录具体产品键。
            product = order.package_name if order.package_name in ALL_PRODUCTS else PRODUCT_CREATION_TOOL
            user_stmt = select(User).where(User.id == order.user_id)
            user = (await self.db.execute(user_stmt)).scalar_one_or_none()
            if not user:
                logger.warning("[WechatPay] 回调用户不存在 out_trade_no=%s", out_trade_no)
            elif product == PRODUCT_CREATION_TOOL:
                # 创作工具：按月订阅。开通或续订都延长一个月并发放本期赠送积分。
                grant_product_access(user, product)
                user.is_member = True
                user.member_since = user.member_since or utcnow()
                self.db.add(user)
                credit_service = CreditService(self.db)
                await credit_service.activate_subscription(
                    user_id=order.user_id,
                    gift_amount=MEMBERSHIP_GIFT_CREDITS,
                    description="创作工具订阅赠送积分",
                )
                logger.info(
                    "[WechatPay] 创作工具订阅开通/续订成功 out_trade_no=%s user_id=%s",
                    out_trade_no, order.user_id,
                )
            elif not has_product_access(user, product):
                # 其它产品（潜在商单/实战营）：一次性开通
                grant_product_access(user, product)
                user.is_member = True
                user.member_since = user.member_since or utcnow()
                self.db.add(user)
                logger.info(
                    "[WechatPay] 产品开通成功 out_trade_no=%s user_id=%s product=%s",
                    out_trade_no, order.user_id, product,
                )
            else:
                # 幂等：已经开通（可能回调重复），仅记录日志
                logger.info(
                    "[WechatPay] 用户已开通产品，跳过重复开通 out_trade_no=%s user_id=%s product=%s",
                    out_trade_no, order.user_id, product,
                )
        else:
            # 积分套餐订单：充值积分
            credit_service = CreditService(self.db)
            await credit_service.purchase_credits(
                user_id=order.user_id,
                package_name=order.package_name,
                payment_amount_yuan=order.amount_yuan,
                payment_method="wechat",
                payment_order_id=order.out_trade_no,
            )
            logger.info(
                "[WechatPay] 积分到账 out_trade_no=%s user_id=%s credits=%s",
                out_trade_no, order.user_id, order.credits,
            )

        await self.db.flush()
        return order

    def _validate_transaction_matches_order(self, transaction: Dict[str, Any], order: PaymentOrder) -> None:
        """确保微信回调交易和本地订单完全一致后再入账。"""
        amount = transaction.get("amount") or {}
        checks = [
            (transaction.get("out_trade_no") == order.out_trade_no, "订单号不匹配"),
            (transaction.get("mchid") == settings.WXPAY_MCH_ID, "商户号不匹配"),
            (transaction.get("appid") == settings.WXPAY_APP_ID, "appid 不匹配"),
            (amount.get("total") == order.amount_fen, "支付金额不匹配"),
        ]
        currency = amount.get("currency")
        if currency is not None:
            checks.append((currency == "CNY", "支付币种不匹配"))

        for ok, message in checks:
            if not ok:
                logger.warning(
                    "[WechatPay] 回调校验失败 out_trade_no=%s reason=%s transaction_id=%s",
                    order.out_trade_no,
                    message,
                    transaction.get("transaction_id"),
                )
                raise ValueError(f"微信支付回调校验失败：{message}")

    def _wechat_headers(self, method: str, url_path: str, payload: Dict[str, Any]) -> Dict[str, str]:
        timestamp = str(int(time.time()))
        nonce = secrets.token_hex(16)
        body = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
        message = f"{method}\n{url_path}\n{timestamp}\n{nonce}\n{body}\n"
        signature = self._sign(message)
        authorization = (
            'WECHATPAY2-SHA256-RSA2048 '
            f'mchid="{settings.WXPAY_MCH_ID}",'
            f'nonce_str="{nonce}",'
            f'signature="{signature}",'
            f'timestamp="{timestamp}",'
            f'serial_no="{settings.WXPAY_MCH_SERIAL_NO}"'
        )
        return {
            "Authorization": authorization,
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

    def _sign(self, message: str) -> str:
        private_key_pem = Path(settings.WXPAY_PRIVATE_KEY_PATH).read_bytes()
        private_key = serialization.load_pem_private_key(private_key_pem, password=None)
        signature = private_key.sign(message.encode("utf-8"), padding.PKCS1v15(), hashes.SHA256())
        return base64.b64encode(signature).decode("utf-8")

    def _verify_signature(self, timestamp: str, nonce: str, body: str, signature: str, serial_no: str) -> None:
        if serial_no != settings.WXPAY_PUBLIC_KEY_ID:
            logger.debug("[WechatPay] 回调平台证书/公钥序列 serial_no=%s configured_public_key_id=%s", serial_no, settings.WXPAY_PUBLIC_KEY_ID)

        public_key_pem = Path(settings.WXPAY_PUBLIC_KEY_PATH).read_bytes()
        public_key = serialization.load_pem_public_key(public_key_pem)
        message = f"{timestamp}\n{nonce}\n{body}\n".encode("utf-8")
        try:
            public_key.verify(base64.b64decode(signature), message, padding.PKCS1v15(), hashes.SHA256())
        except InvalidSignature as exc:
            raise ValueError("微信支付回调验签失败") from exc

    def _decrypt_resource(self, resource: Dict[str, str]) -> Dict[str, Any]:
        api_v3_key = settings.WXPAY_API_V3_KEY.encode("utf-8")
        nonce = resource["nonce"].encode("utf-8")
        ciphertext = base64.b64decode(resource["ciphertext"])
        associated_data = (resource.get("associated_data") or "").encode("utf-8")
        plaintext = AESGCM(api_v3_key).decrypt(nonce, ciphertext, associated_data)
        return json.loads(plaintext.decode("utf-8"))

    def _generate_trade_no(self) -> str:
        return "GZH" + datetime.now().strftime("%Y%m%d%H%M%S") + secrets.token_hex(6).upper()

    def _parse_success_time(self, value: Optional[str]):
        if not value:
            return None
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00")).replace(tzinfo=None)
        except ValueError:
            return None
