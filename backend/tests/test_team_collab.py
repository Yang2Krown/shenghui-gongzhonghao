"""P0 团队协作底座测试：员工全产品权限 / 角色赋予校验。"""

import pytest
from pydantic import ValidationError

from app.core.product_access import (
    PRODUCT_CREATION_TOOL,
    PRODUCT_POTENTIAL_COMMERCIAL,
    PRODUCT_PRACTICAL_CAMP,
    PRODUCT_XHS_TOPIC,
    effective_product_access,
    has_product_access,
    is_employee_user,
)
from app.schemas.team import RoleUpdateRequest
from app.models.user import User


def _user(role: str, superuser: bool = False) -> User:
    return User(id=1, username=f"u_{role}", role=role, is_superuser=superuser, is_active=True)


def test_employee_gets_all_product_access():
    user = _user("employee")
    assert effective_product_access(user) == [
        PRODUCT_CREATION_TOOL,
        PRODUCT_POTENTIAL_COMMERCIAL,
        PRODUCT_PRACTICAL_CAMP,
        PRODUCT_XHS_TOPIC,
    ]
    assert is_employee_user(user)


def test_employee_has_any_product():
    user = _user("employee")
    assert has_product_access(user, PRODUCT_CREATION_TOOL)
    assert has_product_access(user, PRODUCT_XHS_TOPIC)


def test_normal_user_product_access_unchanged():
    user = User(id=2, username="normal", role="user", is_active=True, product_access=[PRODUCT_PRACTICAL_CAMP])
    assert not is_employee_user(user)
    assert effective_product_access(user) == [PRODUCT_PRACTICAL_CAMP]
    assert not has_product_access(user, PRODUCT_CREATION_TOOL)


def test_admin_still_all_products():
    user = _user("admin")
    assert effective_product_access(user) == [
        PRODUCT_CREATION_TOOL,
        PRODUCT_POTENTIAL_COMMERCIAL,
        PRODUCT_PRACTICAL_CAMP,
        PRODUCT_XHS_TOPIC,
    ]


def test_role_update_request_accepts_employee_and_user():
    assert RoleUpdateRequest(role="employee").role == "employee"
    assert RoleUpdateRequest(role="user").role == "user"
    assert RoleUpdateRequest(role="USER").role == "user"


def test_role_update_request_rejects_legacy_roles():
    for legacy in ("admin", "ops", "support", "finance", "auditor", "editor"):
        with pytest.raises(ValidationError):
            RoleUpdateRequest(role=legacy)
