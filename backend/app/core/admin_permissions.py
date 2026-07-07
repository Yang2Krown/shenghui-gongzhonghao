"""Role-based permissions for admin backoffice actions."""
from typing import Iterable, Set

from fastapi import Depends, HTTPException, status

from app.core.security import get_current_user
from app.models.user import User


ROLE_SUPER_ADMIN = "super_admin"
ROLE_ADMIN = "admin"
ROLE_OPS = "ops"
ROLE_SUPPORT = "support"
ROLE_FINANCE = "finance"
ROLE_AUDITOR = "auditor"

ADMIN_ROLES = {
    ROLE_ADMIN,
    ROLE_OPS,
    ROLE_SUPPORT,
    ROLE_FINANCE,
    ROLE_AUDITOR,
}

PERMISSIONS = {
    "monitoring:read": {ROLE_ADMIN, ROLE_OPS, ROLE_SUPPORT, ROLE_FINANCE, ROLE_AUDITOR},
    "alerts:write": {ROLE_ADMIN, ROLE_OPS, ROLE_SUPPORT},
    "users:read": {ROLE_ADMIN, ROLE_OPS, ROLE_SUPPORT, ROLE_FINANCE},
    "users:status": {ROLE_ADMIN, ROLE_OPS, ROLE_SUPPORT},
    "credits:gift": {ROLE_ADMIN, ROLE_FINANCE},
    "payments:read": {ROLE_ADMIN, ROLE_FINANCE},
    "pricing:write": {ROLE_ADMIN, ROLE_FINANCE},
    "audit:read": {ROLE_ADMIN, ROLE_AUDITOR},
    "admin:manage": {ROLE_ADMIN},
}


def normalize_admin_role(user: User) -> str:
    if user.is_superuser:
        return ROLE_SUPER_ADMIN
    return (user.role or "user").strip().lower()


def has_permission(user: User, permission: str) -> bool:
    if user.is_superuser:
        return True
    role = normalize_admin_role(user)
    return role in PERMISSIONS.get(permission, set())


def require_admin_permission(permission: str):
    async def dependency(current_user: User = Depends(get_current_user)) -> User:
        if not has_permission(current_user, permission):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="权限不足",
            )
        return current_user

    return dependency


def is_backoffice_user(user: User) -> bool:
    return user.is_superuser or normalize_admin_role(user) in ADMIN_ROLES


def allowed_roles_text(roles: Iterable[str] = ADMIN_ROLES) -> str:
    return ", ".join(sorted(set(roles)))
