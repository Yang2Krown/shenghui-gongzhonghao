"""管理员后台权限与监测规则测试。"""

import pytest
from fastapi import HTTPException

from app.api.deps import get_current_admin_user, get_current_super_admin_user
from app.core.config import settings
from app.core.security import get_current_super_admin_user as get_core_current_super_admin_user
from app.models.admin_audit import AdminAuditLog
from app.models.monitoring import MonitoringAlert
from app.models.user import User
from app.services.monitoring.checks import build_alert_specs


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
