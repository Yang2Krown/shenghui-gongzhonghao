import pytest

from app.core.config import settings
from app.models.payment import PaymentOrder
from app.services.wechat_pay_service import WechatPayService


def _order() -> PaymentOrder:
    return PaymentOrder(
        out_trade_no="GZH20260707120000ABCDEF123456",
        user_id=1,
        package_name="starter",
        amount_fen=9900,
        credits=1000,
        status="PENDING",
        payment_method="wechat",
    )


def _transaction(**overrides):
    data = {
        "out_trade_no": "GZH20260707120000ABCDEF123456",
        "mchid": "mch_123",
        "appid": "wx_app_123",
        "trade_state": "SUCCESS",
        "transaction_id": "4200000000202607071234567890",
        "amount": {
            "total": 9900,
            "currency": "CNY",
        },
    }
    data.update(overrides)
    return data


@pytest.fixture(autouse=True)
def wxpay_settings(monkeypatch):
    monkeypatch.setattr(settings, "WXPAY_MCH_ID", "mch_123")
    monkeypatch.setattr(settings, "WXPAY_APP_ID", "wx_app_123")


def test_wechat_pay_notify_accepts_matching_order():
    service = WechatPayService(db=None)

    service._validate_transaction_matches_order(_transaction(), _order())


@pytest.mark.parametrize(
    ("override", "message"),
    [
        ({"out_trade_no": "GZH_OTHER"}, "订单号不匹配"),
        ({"mchid": "mch_other"}, "商户号不匹配"),
        ({"appid": "wx_other"}, "appid 不匹配"),
        ({"amount": {"total": 1, "currency": "CNY"}}, "支付金额不匹配"),
        ({"amount": {"total": 9900, "currency": "USD"}}, "支付币种不匹配"),
    ],
)
def test_wechat_pay_notify_rejects_mismatched_transaction(override, message):
    service = WechatPayService(db=None)

    with pytest.raises(ValueError, match=message):
        service._validate_transaction_matches_order(_transaction(**override), _order())


@pytest.mark.asyncio
async def test_handle_notify_rejects_mismatch_before_marking_paid(monkeypatch):
    order = _order()
    service = WechatPayService(db=None)
    monkeypatch.setattr(service, "require_configured", lambda: None)
    monkeypatch.setattr(service, "_verify_signature", lambda *args, **kwargs: None)
    monkeypatch.setattr(service, "_decrypt_resource", lambda resource: _transaction(amount={"total": 1, "currency": "CNY"}))

    async def fake_get_order(out_trade_no, user_id=None):
        return order

    monkeypatch.setattr(service, "get_order", fake_get_order)

    with pytest.raises(ValueError, match="支付金额不匹配"):
        await service.handle_notify(
            body='{"resource": {}}',
            timestamp="1",
            nonce="nonce",
            signature="signature",
            serial_no="serial",
        )

    assert order.status == "PENDING"
    assert order.paid_at is None
    assert order.transaction_id is None
