"""通用进度查询（轮询）。

任何用 progress_store 的功能（挖掘 / 大纲 / 正文 / 标题 …）都可以用同一个
run_id 查这里，前端每隔 1-2 秒查一次即可。
"""

from typing import Any

from fastapi import APIRouter, Depends

from app.core.security import get_current_user
from app.core.progress import progress_store
from app.models.user import User

router = APIRouter()


@router.get("/progress/{run_id}", response_model=dict)
async def get_progress(
    run_id: str,
    current_user: User = Depends(get_current_user),
) -> Any:
    snap = progress_store.snapshot(run_id, user_id=current_user.id)
    if snap is None:
        return {"code": 404, "message": "run 不存在或已过期", "data": {"exists": False}}
    return {"code": 200, "message": "ok", "data": snap}
