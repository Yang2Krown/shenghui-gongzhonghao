"""Product entitlement checks for normal users."""
from typing import Iterable, Sequence

from fastapi import Depends, HTTPException, status

from app.core.security import get_current_user
from app.models.user import User


PRODUCT_CREATION_TOOL = "creation_tool"
PRODUCT_POTENTIAL_COMMERCIAL = "potential_commercial"
PRODUCT_PRACTICAL_CAMP = "practical_camp"
PRODUCT_XHS_TOPIC = "xhs_topic"

ALL_PRODUCTS = {
    PRODUCT_CREATION_TOOL,
    PRODUCT_POTENTIAL_COMMERCIAL,
    PRODUCT_PRACTICAL_CAMP,
    PRODUCT_XHS_TOPIC,
}

PRODUCT_LABELS = {
    PRODUCT_CREATION_TOOL: "创作工具",
    PRODUCT_POTENTIAL_COMMERCIAL: "潜在商单",
    PRODUCT_PRACTICAL_CAMP: "实战营",
    PRODUCT_XHS_TOPIC: "小红书选题",
}

ADMIN_ROLES = {"admin"}
# 员工与管理员一样默认拥有全部产品权限；区别仅在后台管理（由 admin_permissions 守门）。
EMPLOYEE_ROLES = {"employee"}


def normalize_product_access(value: object) -> list[str]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        return []
    seen: set[str] = set()
    result: list[str] = []
    for item in value:
        product = str(item).strip()
        if product in ALL_PRODUCTS and product not in seen:
            seen.add(product)
            result.append(product)
    return result


def is_admin_user(user: User) -> bool:
    return bool(user.is_superuser) or (user.role or "").strip().lower() in ADMIN_ROLES


def is_employee_user(user: User) -> bool:
    return bool(user.is_superuser) or (user.role or "").strip().lower() in EMPLOYEE_ROLES


def effective_product_access(user: User) -> list[str]:
    if is_admin_user(user) or is_employee_user(user):
        return sorted(ALL_PRODUCTS)
    return normalize_product_access(user.product_access)


def has_product_access(user: User, product: str) -> bool:
    return product in effective_product_access(user)


def has_any_product_access(user: User, products: Iterable[str]) -> bool:
    current = set(effective_product_access(user))
    return any(product in current for product in products)


def grant_product_access(user: User, product: str) -> bool:
    if product not in ALL_PRODUCTS:
        raise ValueError(f"unknown product: {product}")
    current = normalize_product_access(user.product_access)
    if product in current:
        return False
    user.product_access = [*current, product]
    return True


def require_product_access(product: str):
    async def dependency(current_user: User = Depends(get_current_user)) -> User:
        if not has_product_access(current_user, product):
            label = PRODUCT_LABELS.get(product, product)
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"请先开通{label}后再使用",
            )
        return current_user

    return dependency
