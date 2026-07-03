"""文章HTML快照API。

前端"阅读原文"链接指向此接口，用户点击后直接展示存下来的HTML快照，
不再依赖会过期的微信临时链接。
"""

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.raw_info import RawInfo

router = APIRouter()


@router.get("/{raw_info_id}")
async def get_article_snapshot(
    raw_info_id: int,
    db: AsyncSession = Depends(get_db),
):
    """返回文章的HTML快照（自包含HTML，图片base64嵌入）。

    Content-Type: text/html，浏览器直接渲染。
    """
    result = await db.execute(
        select(RawInfo.content_html).where(RawInfo.id == raw_info_id)
    )
    content_html = result.scalar()
    if not content_html:
        raise HTTPException(status_code=404, detail="该文章暂无HTML快照")

    return Response(
        content=content_html,
        media_type="text/html",
        headers={"Cache-Control": "public, max-age=86400"},
    )
