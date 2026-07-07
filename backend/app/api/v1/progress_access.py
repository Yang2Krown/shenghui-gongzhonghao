"""Helpers for protecting progress polling and SSE streams."""

from typing import Optional

from fastapi import HTTPException, status

from app.core.progress import ProgressStore
from app.core.security import decode_token


def ensure_run_owner_from_token(
    progress_store: ProgressStore,
    run_id: str,
    token: Optional[str],
) -> int:
    """Validate EventSource query token and ensure it owns the progress run."""
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="缺少认证 token")

    payload = decode_token(token)
    if not payload or not payload.get("sub"):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="无效的 token")

    try:
        user_id = int(payload["sub"])
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="无效的 token") from exc

    if not progress_store.exists(run_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"run {run_id} 不存在或已过期",
        )
    if not progress_store.can_access(run_id, user_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"run {run_id} 不存在或已过期",
        )

    return user_id
