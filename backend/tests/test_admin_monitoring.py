"""管理员后台权限与监测规则测试。"""

import pytest
from fastapi import HTTPException

from app.api.deps import get_current_admin_user, get_current_super_admin_user
from app.core.admin_permissions import has_permission, is_backoffice_user, require_admin_permission
from app.core.config import settings
from app.core.logging_security import mask_sensitive_data
from app.core.product_access import PRODUCT_CREATION_TOOL, PRODUCT_POTENTIAL_COMMERCIAL, effective_product_access, grant_product_access, has_product_access
from app.core.security import get_current_super_admin_user as get_core_current_super_admin_user
from app.core.timezone import utcnow
from app.main import _apply_security_headers
from app.models.admin_audit import AdminAuditLog
from app.models.api_request_log import ApiRequestLog
from app.models.llm_monitoring import LlmCallLog, LlmModelPricing
from app.models.monitoring import MonitoringAlert
from app.models.user import User
from app.services.monitoring.checks import build_alert_specs
from app.services.llm.monitoring import calculate_cost_yuan
from app.services.llm.cost_guard import _mask_phone, _provider_state
from app.services.monitoring.modules import _safe_time
from app.services.monitoring.security_health import collect_security_health


@pytest.mark.asyncio
async def test_admin_dependency_accepts_admin_role():
    user = User(id=1, username="admin", role="admin", is_superuser=False, is_active=True)
    assert await get_current_admin_user(user) is user


@pytest.mark.asyncio
async def test_admin_dependency_accepts_superuser():
    user = User(id=1, username="root", role="user", is_superuser=True, is_active=True)
    assert await get_current_admin_user(user) is user


@pytest.mark.asyncio
async def test_admin_dependency_rejects_normal_user():
    user = User(id=1, username="normal", role="user", is_superuser=False, is_active=True)
    with pytest.raises(HTTPException) as exc:
        await get_current_admin_user(user)
    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_super_admin_dependency_requires_superuser():
    admin = User(id=1, username="admin", role="admin", is_superuser=False, is_active=True)
    with pytest.raises(HTTPException) as exc:
        await get_current_super_admin_user(admin)
    assert exc.value.status_code == 403

    root = User(id=2, username="root", phone=settings.SUPER_ADMIN_PHONE, role="admin", is_superuser=True, is_active=True)
    assert await get_current_super_admin_user(root) is root


@pytest.mark.asyncio
async def test_core_super_admin_dependency_requires_superuser():
    admin = User(id=1, username="admin", role="admin", is_superuser=False, is_active=True)
    with pytest.raises(HTTPException) as exc:
        await get_core_current_super_admin_user(admin)
    assert exc.value.status_code == 403

    root = User(id=2, username="root", phone=settings.SUPER_ADMIN_PHONE, role="admin", is_superuser=True, is_active=True)
    assert await get_core_current_super_admin_user(root) is root


def test_super_admin_phone_default():
    assert settings.SUPER_ADMIN_PHONE == "18021751281"


def test_admin_role_permissions_are_scoped():
    admin = User(id=1, username="admin", role="admin", is_superuser=False, is_active=True)
    support = User(id=2, username="support", role="support", is_superuser=False, is_active=True)
    root = User(id=4, username="root", role="user", is_superuser=True, is_active=True)

    assert has_permission(admin, "monitoring:read") is True
    assert has_permission(admin, "users:read") is True
    assert has_permission(admin, "pricing:write") is False
    assert has_permission(admin, "alerts:write") is False
    assert has_permission(support, "monitoring:read") is False
    assert has_permission(root, "pricing:write") is True
    assert is_backoffice_user(admin) is True
    assert is_backoffice_user(support) is False


@pytest.mark.asyncio
async def test_permission_dependency_rejects_wrong_role():
    dependency = require_admin_permission("monitoring:read")
    support = User(id=2, username="support", role="support", is_superuser=False, is_active=True)

    with pytest.raises(HTTPException) as exc:
        await dependency(support)

    assert exc.value.status_code == 403


def test_product_access_allows_multi_product_and_admin_all_access():
    user = User(id=1, username="u", role="user", is_superuser=False, product_access=[])
    assert has_product_access(user, PRODUCT_CREATION_TOOL) is False
    assert grant_product_access(user, PRODUCT_CREATION_TOOL) is True
    assert grant_product_access(user, PRODUCT_POTENTIAL_COMMERCIAL) is True
    assert has_product_access(user, PRODUCT_CREATION_TOOL) is True
    assert has_product_access(user, PRODUCT_POTENTIAL_COMMERCIAL) is True

    admin = User(id=2, username="admin", role="admin", is_superuser=False, product_access=[])
    assert set(effective_product_access(admin)) >= {PRODUCT_CREATION_TOOL, PRODUCT_POTENTIAL_COMMERCIAL}


def test_build_alert_specs_for_unhealthy_pipeline():
    payload = {
        "content_pipeline": {
            "raw_infos_2h": 0,
            "clusters_24h": 0,
            "pending_raw_infos": 900,
        },
        "tasks": {"failed_24h": 6},
        "users": {"low_credit_users": 11},
    }
    alerts = build_alert_specs(payload)
    keys = {a["key"] for a in alerts}

    assert "data_freshness.raw_infos_2h_zero" in keys
    assert "preprocess.pending_raw_high" in keys
    assert "pipeline.clusters_24h_zero" in keys
    assert "tasks.failed_24h_nonzero" in keys
    assert "users.low_credit_many" in keys
    assert any(a["level"] == "critical" for a in alerts)


def test_build_alert_specs_for_healthy_pipeline():
    payload = {
        "content_pipeline": {
            "raw_infos_2h": 12,
            "clusters_24h": 5,
            "pending_raw_infos": 20,
        },
        "tasks": {"failed_24h": 0},
        "users": {"low_credit_users": 1},
    }
    assert build_alert_specs(payload) == []


def test_monitoring_alert_handling_fields_exist():
    columns = MonitoringAlert.__table__.columns
    assert "handled_by_user_id" in columns
    assert "handled_at" in columns
    assert "note" in columns


def test_admin_audit_log_uses_safe_metadata_column():
    columns = AdminAuditLog.__table__.columns
    assert "metadata_json" in columns
    assert "metadata" not in columns


def test_api_request_log_fields_exist():
    columns = ApiRequestLog.__table__.columns
    assert "method" in columns
    assert "path" in columns
    assert "status_code" in columns
    assert "duration_ms" in columns
    assert "user_id" in columns


def test_source_health_accepts_string_last_fetched_at():
    assert _safe_time("2026-07-04T10:59:00") == "2026-07-04T10:59:00"


def test_llm_monitoring_fields_exist():
    pricing_columns = LlmModelPricing.__table__.columns
    assert "provider" in pricing_columns
    assert "model" in pricing_columns
    assert "input_price_per_million" in pricing_columns
    assert "output_price_per_million" in pricing_columns

    log_columns = LlmCallLog.__table__.columns
    assert "prompt_tokens" in log_columns
    assert "completion_tokens" in log_columns
    assert "cost_yuan" in log_columns
    assert "pricing_snapshot" in log_columns


def test_calculate_llm_cost_yuan():
    pricing = LlmModelPricing(
        provider="deepseek",
        model="deepseek-v4-flash",
        input_price_per_million=2,
        output_price_per_million=8,
    )
    cost = calculate_cost_yuan(
        {"prompt_tokens": 1000, "completion_tokens": 500, "total_tokens": 1500},
        pricing,
    )
    assert float(cost) == 0.006


def test_security_health_reports_p2_baseline():
    payload = collect_security_health()

    assert "overall" in payload
    assert "groups" in payload
    assert any(group["key"] == "runtime" for group in payload["groups"])
    assert any(group["key"] == "perimeter" for group in payload["groups"])
    assert any(group["key"] == "governance" for group in payload["groups"])
    assert "secret_presence" in payload


def test_security_health_warns_for_high_cost_users():
    payload = collect_security_health({
        "overall": {
            "blocked": False,
            "message": "LLM 成本防护正常",
            "cost_yuan_24h": 21.5,
            "daily_budget_yuan": 200,
        },
        "providers": [],
        "high_cost_users": [
            {"user_id": 7, "username": "heavy", "cost_yuan_24h": 20.5},
        ],
    })
    governance = next(group for group in payload["groups"] if group["key"] == "governance")
    cost_item = next(item for item in governance["items"] if item["title"] == "成本熔断")

    assert cost_item["level"] == "warn"
    assert "1 位用户" in cost_item["message"]


def test_security_health_reports_p2_remaining_items_ready():
    payload = collect_security_health({
        "overall": {"blocked": False, "message": "LLM 成本防护正常", "cost_yuan_24h": 0, "daily_budget_yuan": 200},
        "providers": [],
        "high_cost_users": [],
    })
    all_items = [item for group in payload["groups"] for item in group["items"]]
    by_title = {item["title"]: item for item in all_items}

    assert by_title["HTTPS 和反向代理安全"]["value"] == "configured"
    assert by_title["依赖安全扫描"]["value"] == "ready"


def test_sensitive_log_masking():
    text = "phone=13800138000 Authorization: Bearer abc.def token=secret-value"
    masked = mask_sensitive_data(text)

    assert "13800138000" not in masked
    assert "abc.def" not in masked
    assert "secret-value" not in masked
    assert "138****8000" in masked


def test_security_headers_are_applied():
    class DummyResponse:
        def __init__(self):
            self.headers = {}

    response = DummyResponse()
    _apply_security_headers(response)

    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["Referrer-Policy"]
    assert response.headers["X-Frame-Options"]
    assert response.headers["Content-Security-Policy"]


def test_llm_cost_guard_provider_budget_blocks(monkeypatch):
    monkeypatch.setattr(settings, "LLM_PROVIDER_DAILY_BUDGET_YUAN", 10.0)
    state = _provider_state(
        "deepseek",
        calls_24h=12,
        cost_24h=10.1,
        failure={"calls": 0, "failures": 0, "latest_at": None},
        now=utcnow(),
    )

    assert state["blocked"] is True
    assert state["reason"] == "provider_daily_budget_exceeded"


def test_llm_cost_guard_failure_breaker_blocks(monkeypatch):
    monkeypatch.setattr(settings, "LLM_PROVIDER_DAILY_BUDGET_YUAN", 0.0)
    monkeypatch.setattr(settings, "LLM_FAILURE_BREAKER_ENABLED", True)
    monkeypatch.setattr(settings, "LLM_FAILURE_BREAKER_MIN_CALLS", 5)
    monkeypatch.setattr(settings, "LLM_FAILURE_BREAKER_FAILURE_RATE", 0.6)
    monkeypatch.setattr(settings, "LLM_FAILURE_BREAKER_COOLDOWN_MINUTES", 10)
    now = utcnow()
    state = _provider_state(
        "aigocode",
        calls_24h=6,
        cost_24h=0,
        failure={"calls": 5, "failures": 3, "latest_at": now},
        now=now,
    )

    assert state["blocked"] is True
    assert state["reason"] == "provider_failure_breaker"
    assert state["retry_after_seconds"] > 0


def test_llm_cost_guard_masks_phone():
    assert _mask_phone("13800138000") == "138****8000"
    assert _mask_phone("123456") == "123456"
    assert _mask_phone(None) is None
