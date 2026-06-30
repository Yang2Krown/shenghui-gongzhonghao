"""支付订单模型。"""
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Numeric, Text
from sqlalchemy.orm import relationship

from app.core.timezone import utcnow
from app.db.base import BaseModel


class PaymentOrder(BaseModel):
    """微信支付订单"""

    __tablename__ = "payment_orders"

    out_trade_no = Column(String(32), unique=True, nullable=False, index=True, comment="商户订单号")
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    package_name = Column(String(50), nullable=False, comment="积分套餐名称")
    amount_fen = Column(Integer, nullable=False, comment="支付金额（分）")
    credits = Column(Integer, nullable=False, comment="到账积分")
    status = Column(String(20), nullable=False, default="PENDING", index=True, comment="PENDING/PAID/CLOSED")
    payment_method = Column(String(30), nullable=False, default="wechat")
    transaction_id = Column(String(100), nullable=True, comment="微信支付订单号")
    code_url = Column(Text, nullable=True, comment="Native 支付二维码链接")
    paid_at = Column(DateTime, nullable=True)
    notify_raw = Column(Text, nullable=True, comment="最近一次支付回调原文")

    user = relationship("User", backref="payment_orders")

    @property
    def amount_yuan(self) -> float:
        return round(self.amount_fen / 100, 2)

    def to_dict(self):
        return {
            "id": self.id,
            "out_trade_no": self.out_trade_no,
            "user_id": self.user_id,
            "package_name": self.package_name,
            "amount_fen": self.amount_fen,
            "amount_yuan": self.amount_yuan,
            "credits": self.credits,
            "status": self.status,
            "payment_method": self.payment_method,
            "transaction_id": self.transaction_id,
            "code_url": self.code_url,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "paid_at": self.paid_at.isoformat() if self.paid_at else None,
        }

