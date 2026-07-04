"""LLM 调用成本监测模型。"""

from sqlalchemy import Boolean, Column, Float, Integer, Numeric, String, Text, UniqueConstraint

from app.db.base import BaseModel, JSONField


class LlmModelPricing(BaseModel):
    """可在后台维护的模型单价配置。"""

    __tablename__ = "llm_model_pricing"

    provider = Column(String(50), nullable=False, index=True)
    model = Column(String(120), nullable=False, index=True)
    display_name = Column(String(160), nullable=True)
    input_price_per_million = Column(Numeric(12, 6), nullable=False, default=0)
    output_price_per_million = Column(Numeric(12, 6), nullable=False, default=0)
    currency = Column(String(10), nullable=False, default="CNY")
    enabled = Column(Boolean, nullable=False, default=True, index=True)
    note = Column(Text, nullable=True)

    __table_args__ = (
        UniqueConstraint("provider", "model", name="uq_llm_model_pricing_provider_model"),
    )


class LlmCallLog(BaseModel):
    """每次 LLM 调用的 token、耗时、成本和状态。"""

    __tablename__ = "llm_call_logs"

    provider = Column(String(50), nullable=False, index=True)
    model = Column(String(120), nullable=False, index=True)
    operation = Column(String(80), nullable=True, index=True)
    operation_id = Column(String(120), nullable=True, index=True)
    user_id = Column(Integer, nullable=True, index=True)
    status = Column(String(20), nullable=False, default="success", index=True)
    prompt_tokens = Column(Integer, nullable=False, default=0)
    completion_tokens = Column(Integer, nullable=False, default=0)
    total_tokens = Column(Integer, nullable=False, default=0)
    cost_yuan = Column(Numeric(12, 6), nullable=False, default=0)
    duration_ms = Column(Float, nullable=False, default=0)
    finish_reason = Column(String(80), nullable=True)
    error_message = Column(Text, nullable=True)
    pricing_snapshot = Column(JSONField, default=dict)
    metadata_json = Column(JSONField, default=dict)
