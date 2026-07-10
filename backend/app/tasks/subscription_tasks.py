"""订阅到期处理 Celery 任务。

创作工具（creation_tool）按月订阅：
- 满一个月（user_credits.subscription_expires_at < 现在）后：
  1. 移除该用户的 creation_tool 产品权益
  2. is_member 置 false（仅当不再持有任何付费产品时）
  3. 积分余额整体清零为 0（记一条 type=expire 的负数流水）

只处理"有过订阅"的账户（subscription_expires_at 非空），
纯买积分包、从未订阅创作工具的用户不受影响。
"""

import asyncio
import logging

from celery import shared_task
from sqlalchemy import select

from app.db.session import AsyncSessionLocal, engine
from app.core.timezone import utcnow

logger = logging.getLogger(__name__)


async def _expire_subscriptions() -> dict:
    from app.models.credit import UserCredit
    from app.models.user import User
    from app.core.product_access import (
        PRODUCT_CREATION_TOOL,
        normalize_product_access,
        effective_product_access,
        is_admin_user,
    )
    from app.services.credit_service import CreditService

    now = utcnow()
    processed = 0
    cleared_users = 0

    try:
        async with AsyncSessionLocal() as db:
            # 找出所有已到期的订阅账户
            stmt = (
                select(UserCredit)
                .where(UserCredit.subscription_expires_at.isnot(None))
                .where(UserCredit.subscription_expires_at < now)
            )
            accounts = (await db.execute(stmt)).scalars().all()

            credit_service = CreditService(db)
            for account in accounts:
                user = (
                    await db.execute(select(User).where(User.id == account.user_id))
                ).scalar_one_or_none()
                if not user:
                    continue
                # 管理员不受订阅到期影响
                if is_admin_user(user):
                    continue

                current = normalize_product_access(user.product_access)

                # 1) 移除创作工具权限
                user.product_access = [p for p in current if p != PRODUCT_CREATION_TOOL]
                # 2) 不再持有任何付费产品则取消会员标记
                if not effective_product_access(user):
                    user.is_member = False
                db.add(user)

                # 3) 余额整体清零
                await credit_service.expire_and_reset(
                    user_id=account.user_id,
                    reason="创作工具订阅到期，积分清零",
                )
                # 停订：清空到期时间，避免重复处理
                account.subscription_expires_at = None
                db.add(account)

                processed += 1
                cleared_users += 1

            await db.commit()

        return {"processed": processed, "cleared_users": cleared_users}
    finally:
        await engine.dispose()


@shared_task(bind=True, name="subscription.expire_due", max_retries=1)
def expire_due_subscriptions(self) -> dict:
    """处理所有到期的创作工具订阅：移除权限 + 清零积分。"""
    try:
        result = asyncio.run(_expire_subscriptions())
        logger.info(f"订阅到期处理完成: {result}")
        return result
    except Exception as e:
        logger.exception(f"订阅到期处理失败: {e}")
        self.retry(exc=e, countdown=300)
