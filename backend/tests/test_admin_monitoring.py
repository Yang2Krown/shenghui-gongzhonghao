"""管理员后台权限与监测规则测试。"""

import pytest
from fastapi import HTTPException

from app.api.deps import get_current_admin_user, get_current_super_admin_user
from app.core.admin_permissions import has_permission, is_backoffice_user, require_admin_permission
from app.core.config import settings
from app.core.security import get_current_super_admin_user as get_core_current_super_admin_user
from app.models.admin_audit import AdminAuditLog
from app.models.api_request_log import ApiRequestLog
from app.models.llm_monitoring import LlmCallLog, LlmModelPricing
from app.models.monitoring import MonitoringAlert
from app.models.user import User
from app.services.monitoring.checks import build_alert_specs
from app.services.llm.monitoring import calculate_cost_yuan
from app.services.monitoring.modules import _safe_time


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

    root = User(id=2, username="root", role="admin", is_superuser=True, is_active=True)
    assert await get_current_super_admin_user(root) is root


@pytest.mark.asyncio
async def test_core_super_admin_dependency_requires_superuser():
    admin = User(id=1, username="admin", role="admin", is_superuser=False, is_active=True)
    with pytest.raises(HTTPException) as exc:
        await get_core_current_super_admin_user(admin)
    assert exc.value.status_code == 403

    root = User(id=2, username="root", role="admin", is_superuser=True, is_active=True)
    assert await get_core_current_super_admin_user(root) is root


def test_super_admin_phone_default():
    assert settings.SUPER_ADMIN_PHONE == "18021751281"


def test_admin_role_permissions_are_scoped():
    finance = User(id=1, username="finance", role="finance", is_superuser=False, is_active=True)
    support = User(id=2, username="support", role="support", is_superuser=False, is_active=True)
    auditor = User(id=3, username="auditor", role="auditor", is_superuser=False, is_active=True)
    root = User(id=4, username="root", role="user", is_superuser=True, is_active=True)

    assert has_permission(finance, "credits:gift") is True
    assert has_permission(finance, "pricing:write") is True
    assert has_permission(support, "credits:gift") is False
    assert has_permission(support, "alerts:write") is True
    assert has_permission(auditor, "audit:read") is True
    assert has_permission(auditor, "pricing:write") is False
    assert has_permission(root, "pricing:write") is True
    assert is_backoffice_user(finance) is True


@pytest.mark.asyncio
async def test_permission_dependency_rejects_wrong_role():
    dependency = require_admin_permission("credits:gift")
    support = User(id=2, username="support", role="support", is_superuser=False, is_active=True)

    with pytest.raises(HTTPException) as exc:
        await dependency(support)

    assert exc.value.status_code == 403


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
