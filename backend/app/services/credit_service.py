"""积分服务：余额查询、扣费、充值、交易记录。"""
import logging
from decimal import Decimal
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any

from sqlalchemy import select, update, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.credit import UserCredit, CreditTransaction, CreditPackage
from app.core.timezone import utcnow
from app.core.credit_config import (
    OPERATION_COSTS,
    CREDIT_PACKAGES,
    NEW_USER_GIFT_CREDITS,
    get_operation_credits,
)

logger = logging.getLogger(__name__)


def add_one_month(dt: datetime) -> datetime:
    """在给定时间上加一个自然月（跨月/跨年安全，落到月末则取该月最后一天）。"""
    year = dt.year + (dt.month // 12)
    month = dt.month % 12 + 1
    # 处理目标月天数不足（如 1/31 + 1 月 → 2/28）
    if month == 12:
        next_month_first = dt.replace(year=year + 1, month=1, day=1)
    else:
        next_month_first = dt.replace(year=year, month=month + 1, day=1)
    last_day = (next_month_first - timedelta(days=1)).day
    day = min(dt.day, last_day)
    return dt.replace(year=year, month=month, day=day)


class CreditService:
    """积分服务"""

    def __init__(self, db: AsyncSession):
        self.db = db

    # ====== 账户管理 ======

    async def get_or_create_account(self, user_id: int) -> UserCredit:
        """获取或创建用户积分账户"""
        stmt = select(UserCredit).where(UserCredit.user_id == user_id)
        result = await self.db.execute(stmt)
        account = result.scalar_one_or_none()

        if not account:
            account = UserCredit(
                user_id=user_id,
                balance=0,
                total_purchased=0,
                total_consumed=0,
                total_gifted=0,
            )
            self.db.add(account)
            await self.db.flush()
            logger.info(f"为用户 {user_id} 创建积分账户")

        return account

    async def get_balance(self, user_id: int) -> int:
        """查询用户积分余额"""
        account = await self.get_or_create_account(user_id)
        return account.balance

    async def get_account_info(self, user_id: int) -> Dict[str, Any]:
        """获取用户积分账户详情（含订阅到期信息）"""
        account = await self.get_or_create_account(user_id)
        info = account.to_dict()
        info.update(self._subscription_status(account))
        return info

    def _subscription_status(self, account: UserCredit) -> Dict[str, Any]:
        """根据到期时间计算订阅状态，供前端展示"积分还有多久过期"。"""
        expires_at = account.subscription_expires_at
        if not expires_at:
            return {
                "is_subscription_active": False,
                "subscription_expires_at": None,
                "days_until_expire": None,
            }
        now = utcnow()
        remaining = expires_at - now
        days = remaining.days + (1 if remaining.seconds > 0 else 0) if remaining.total_seconds() > 0 else 0
        return {
            "is_subscription_active": expires_at > now,
            "subscription_expires_at": expires_at.isoformat(),
            "days_until_expire": max(days, 0),
        }

    async def activate_subscription(
        self,
        user_id: int,
        gift_amount: int,
        description: str = "创作工具订阅赠送积分",
    ) -> UserCredit:
        """开通/续订创作工具：延长一个月到期时间，并发放本期赠送积分。

        - 未过期续订：在原到期时间基础上 +1 个月（不损失剩余天数）
        - 已过期或首次：从当前时间 +1 个月
        赠送积分累加到余额，并记一条 gift 流水。
        """
        account = await self.get_or_create_account(user_id)
        now = utcnow()

        base = account.subscription_expires_at
        if base and base > now:
            account.subscription_expires_at = add_one_month(base)
        else:
            account.subscription_expires_at = add_one_month(now)

        account.gift_credits_at = now

        # 发放本期赠送积分
        account.balance += gift_amount
        account.total_gifted += gift_amount
        transaction = CreditTransaction(
            user_id=user_id,
            credit_account_id=account.id,
            type="gift",
            amount=gift_amount,
            balance_after=account.balance,
            description=description,
        )
        self.db.add(transaction)
        await self.db.flush()

        logger.info(
            f"用户 {user_id} 订阅开通/续订成功，赠送 {gift_amount} 积分，"
            f"到期 {account.subscription_expires_at}，余额 {account.balance}"
        )
        return account

    async def expire_and_reset(self, user_id: int, reason: str = "订阅到期，积分清零") -> Optional[CreditTransaction]:
        """订阅到期：把余额整体清零为 0，记一条 expire 负数流水。"""
        account = await self.get_or_create_account(user_id)
        if account.balance <= 0:
            account.balance = 0
            return None

        cleared = account.balance
        account.balance = 0
        transaction = CreditTransaction(
            user_id=user_id,
            credit_account_id=account.id,
            type="expire",
            amount=-cleared,
            balance_after=0,
            description=reason,
        )
        self.db.add(transaction)
        await self.db.flush()
        logger.info(f"用户 {user_id} 订阅到期清零 {cleared} 积分，余额归 0")
        return transaction

    # ====== 积分操作 ======

    async def gift_credits(self, user_id: int, amount: int, description: str = "赠送积分") -> CreditTransaction:
        """赠送积分（新用户注册等场景）"""
        account = await self.get_or_create_account(user_id)

        # 更新账户
        account.balance += amount
        account.total_gifted += amount

        # 创建交易记录
        transaction = CreditTransaction(
            user_id=user_id,
            credit_account_id=account.id,
            type="gift",
            amount=amount,
            balance_after=account.balance,
            description=description,
        )
        self.db.add(transaction)
        await self.db.flush()

        logger.info(f"用户 {user_id} 获赠 {amount} 积分，余额: {account.balance}")
        return transaction

    async def welcome_gift(self, user_id: int) -> Optional[CreditTransaction]:
        """新用户注册赠送积分（仅赠送一次）"""
        account = await self.get_or_create_account(user_id)

        # 检查是否已经赠送过
        if account.total_gifted > 0:
            logger.info(f"用户 {user_id} 已领取过新用户赠送，跳过")
            return None

        return await self.gift_credits(
            user_id=user_id,
            amount=NEW_USER_GIFT_CREDITS,
            description=f"新用户注册赠送 {NEW_USER_GIFT_CREDITS} 积分",
        )

    async def check_balance(self, user_id: int, operation: str) -> Dict[str, Any]:
        """检查余额是否足够执行某操作"""
        required = get_operation_credits(operation)
        balance = await self.get_balance(user_id)

        return {
            "sufficient": balance >= required,
            "balance": balance,
            "required": required,
            "operation": operation,
            "operation_desc": OPERATION_COSTS[operation]["description"],
        }

    async def deduct_credits(
        self,
        user_id: int,
        operation: str,
        operation_id: Optional[str] = None,
        token_usage: Optional[Dict] = None,
        description: Optional[str] = None,
    ) -> CreditTransaction:
        """扣减积分（操作成功后调用）"""
        amount = get_operation_credits(operation)
        account = await self.get_or_create_account(user_id)

        # 检查余额
        if account.balance < amount:
            raise ValueError(f"积分不足: 需要 {amount}，当前余额 {account.balance}")

        # 计算实际LLM成本（用于统计分析）
        cost_yuan = None
        if token_usage and "total_tokens" in token_usage:
            # DeepSeek 定价: input ¥2/百万, output ¥8/百万, 平均 ¥5/百万
            total_tokens = token_usage.get("total_tokens", 0)
            cost_yuan = Decimal(str(total_tokens * 5 / 1_000_000))

        # 更新账户
        account.balance -= amount
        account.total_consumed += amount

        # 创建交易记录
        op_desc = OPERATION_COSTS[operation]["description"]
        transaction = CreditTransaction(
            user_id=user_id,
            credit_account_id=account.id,
            type="consume",
            amount=-amount,
            balance_after=account.balance,
            operation=operation,
            operation_id=operation_id,
            token_usage=token_usage,
            cost_yuan=cost_yuan,
            description=description or f"{op_desc} 消耗 {amount} 积分",
        )
        self.db.add(transaction)
        await self.db.flush()

        logger.info(f"用户 {user_id} 消耗 {amount} 积分({op_desc})，余额: {account.balance}")
        return transaction

    async def refund_credits(
        self,
        user_id: int,
        operation: str,
        operation_id: Optional[str] = None,
        reason: str = "操作失败退款",
    ) -> CreditTransaction:
        """退还积分（操作失败时调用）"""
        amount = get_operation_credits(operation)
        account = await self.get_or_create_account(user_id)

        # 更新账户
        account.balance += amount
        account.total_consumed -= amount

        # 创建交易记录
        transaction = CreditTransaction(
            user_id=user_id,
            credit_account_id=account.id,
            type="refund",
            amount=amount,
            balance_after=account.balance,
            operation=operation,
            operation_id=operation_id,
            description=reason,
        )
        self.db.add(transaction)
        await self.db.flush()

        logger.info(f"用户 {user_id} 退还 {amount} 积分({reason})，余额: {account.balance}")
        return transaction

    async def purchase_credits(
        self,
        user_id: int,
        package_name: str,
        payment_amount_yuan: float,
        payment_method: str = "wechat",
        payment_order_id: Optional[str] = None,
    ) -> CreditTransaction:
        """购买积分套餐"""
        # 查找套餐
        package = None
        for pkg in CREDIT_PACKAGES:
            if pkg["name"] == package_name:
                package = pkg
                break

        if not package:
            raise ValueError(f"未知套餐: {package_name}")

        account = await self.get_or_create_account(user_id)

        # 更新账户
        amount = package["credits"]
        account.balance += amount
        account.total_purchased += amount

        # 创建交易记录
        transaction = CreditTransaction(
            user_id=user_id,
            credit_account_id=account.id,
            type="purchase",
            amount=amount,
            balance_after=account.balance,
            payment_amount_yuan=Decimal(str(payment_amount_yuan)),
            payment_method=payment_method,
            payment_order_id=payment_order_id,
            description=f"购买{package_name} +{amount}积分",
        )
        self.db.add(transaction)
        await self.db.flush()

        logger.info(f"用户 {user_id} 购买 {package_name}({amount}积分)，余额: {account.balance}")
        return transaction

    # ====== 交易记录查询 ======

    async def get_transactions(
        self,
        user_id: int,
        type: Optional[str] = None,
        operation: Optional[str] = None,
        limit: int = 20,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """查询交易记录"""
        stmt = (
            select(CreditTransaction)
            .where(CreditTransaction.user_id == user_id)
            .order_by(CreditTransaction.created_at.desc())
        )

        if type:
            stmt = stmt.where(CreditTransaction.type == type)
        if operation:
            stmt = stmt.where(CreditTransaction.operation == operation)

        stmt = stmt.offset(offset).limit(limit)
        result = await self.db.execute(stmt)
        transactions = result.scalars().all()

        return [t.to_dict() for t in transactions]

    async def get_transaction_count(
        self,
        user_id: int,
        type: Optional[str] = None,
    ) -> int:
        """查询交易记录总数"""
        stmt = select(func.count(CreditTransaction.id)).where(
            CreditTransaction.user_id == user_id
        )
        if type:
            stmt = stmt.where(CreditTransaction.type == type)

        result = await self.db.execute(stmt)
        return result.scalar() or 0

    async def get_consumption_stats(
        self,
        user_id: int,
    ) -> Dict[str, Any]:
        """获取消耗统计"""
        # 按操作类型统计
        stmt = (
            select(
                CreditTransaction.operation,
                func.count(CreditTransaction.id).label("count"),
                func.sum(func.abs(CreditTransaction.amount)).label("total_credits"),
            )
            .where(
                CreditTransaction.user_id == user_id,
                CreditTransaction.type == "consume",
            )
            .group_by(CreditTransaction.operation)
        )
        result = await self.db.execute(stmt)
        rows = result.all()

        by_operation = {}
        total_credits = 0
        total_count = 0
        for row in rows:
            op = row.operation or "unknown"
            op_desc = OPERATION_COSTS.get(op, {}).get("description", op)
            by_operation[op] = {
                "description": op_desc,
                "count": row.count,
                "total_credits": row.total_credits or 0,
            }
            total_credits += row.total_credits or 0
            total_count += row.count

        return {
            "total_consumed": total_credits,
            "total_count": total_count,
            "by_operation": by_operation,
        }


# ====== 套餐查询 ======

async def get_available_packages() -> List[Dict[str, Any]]:
    """获取可用的积分套餐列表"""
    return CREDIT_PACKAGES


def get_operation_costs() -> Dict[str, Any]:
    """获取所有操作的积分成本配置"""
    return OPERATION_COSTS