"""积分系统模型：用户积分账户、交易记录、积分套餐。"""
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Text, Numeric, JSON
from sqlalchemy.orm import relationship
from app.db.base import BaseModel, JSONField
from app.core.timezone import utcnow


class UserCredit(BaseModel):
    """用户积分账户"""
    __tablename__ = "user_credits"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False, index=True)
    balance = Column(Integer, nullable=False, default=0, comment="当前余额")
    total_purchased = Column(Integer, nullable=False, default=0, comment="累计购买")
    total_consumed = Column(Integer, nullable=False, default=0, comment="累计消耗")
    total_gifted = Column(Integer, nullable=False, default=0, comment="累计赠送")

    # 时间戳
    created_at = Column(DateTime, default=utcnow, nullable=False)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)

    # 关系
    user = relationship("User", backref="credit_account")
    transactions = relationship("CreditTransaction", back_populates="credit_account", order_by="CreditTransaction.created_at.desc()")

    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "balance": self.balance,
            "total_purchased": self.total_purchased,
            "total_consumed": self.total_consumed,
            "total_gifted": self.total_gifted,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class CreditTransaction(BaseModel):
    """积分交易记录"""
    __tablename__ = "credit_transactions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    credit_account_id = Column(Integer, ForeignKey("user_credits.id"), nullable=False, index=True)

    # 交易类型：purchase(购买) / consume(消耗) / gift(赠送) / refund(退款)
    type = Column(String(20), nullable=False, index=True)
    amount = Column(Integer, nullable=False, comment="正数=入账，负数=消耗")
    balance_after = Column(Integer, nullable=True, comment="操作后余额")

    # 关联信息
    operation = Column(String(50), nullable=True, index=True, comment="操作类型: content_generation/title_generation等")
    operation_id = Column(String(100), nullable=True, comment="关联的任务ID")

    # 成本追踪
    token_usage = Column(JSONField, nullable=True, comment="{prompt_tokens, completion_tokens, provider, model}")
    cost_yuan = Column(Numeric(10, 4), nullable=True, comment="实际LLM成本（人民币）")

    # 支付信息（仅购买类型）
    payment_amount_yuan = Column(Numeric(10, 2), nullable=True, comment="支付金额（人民币）")
    payment_method = Column(String(30), nullable=True, comment="支付方式: wechat/alipay/balance")
    payment_order_id = Column(String(100), nullable=True, comment="支付订单号")

    description = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utcnow, nullable=False)

    # 关系
    credit_account = relationship("UserCredit", back_populates="transactions")
    user = relationship("User", backref="credit_transactions")

    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "type": self.type,
            "amount": self.amount,
            "balance_after": self.balance_after,
            "operation": self.operation,
            "operation_id": self.operation_id,
            "token_usage": self.token_usage,
            "cost_yuan": float(self.cost_yuan) if self.cost_yuan else None,
            "payment_amount_yuan": float(self.payment_amount_yuan) if self.payment_amount_yuan else None,
            "payment_method": self.payment_method,
            "description": self.description,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class CreditPackage(BaseModel):
    """积分套餐定义"""
    __tablename__ = "credit_packages"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(50), nullable=False, comment="套餐名称")
    credits = Column(Integer, nullable=False, comment="积分数量")
    price_yuan = Column(Numeric(10, 2), nullable=False, comment="价格（人民币）")
    original_price_yuan = Column(Numeric(10, 2), nullable=True, comment="原价（划线价）")
    description = Column(String(200), nullable=True, comment="套餐描述")
    badge = Column(String(50), nullable=True, comment="角标: 推荐/热卖/限时等")
    is_active = Column(Boolean, default=True, comment="是否上架")
    sort_order = Column(Integer, default=0, comment="排序权重")

    created_at = Column(DateTime, default=utcnow, nullable=False)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "credits": self.credits,
            "price_yuan": float(self.price_yuan),
            "original_price_yuan": float(self.original_price_yuan) if self.original_price_yuan else None,
            "unit_price": round(float(self.price_yuan) / self.credits, 4) if self.credits > 0 else 0,
            "description": self.description,
            "badge": self.badge,
            "is_active": self.is_active,
            "sort_order": self.sort_order,
        }