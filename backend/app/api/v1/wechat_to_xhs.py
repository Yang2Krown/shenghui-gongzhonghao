"""
公众号转小红书 - API 路由
"""
import uuid
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.core.security import get_current_user
from app.models.user import User
from app.services.wechat_to_xhs_service import generate_xhs_content
from app.services.link_extractor import extract_wechat
from app.services.generation_tracker import track_start, track_complete, track_fail

router = APIRouter()


class ContentConvertRequest(BaseModel):
    """粘贴内容转换请求"""
    content: str = Field(..., min_length=10, description="公众号文章内容")
    original_title: Optional[str] = Field(None, description="原文章标题")


class LinkConvertRequest(BaseModel):
    """链接提取转换请求"""
    url: str = Field(..., description="公众号文章链接")


@router.post("/convert-content")
async def convert_content(
    request: ContentConvertRequest,
    current_user: User = Depends(get_current_user),
):
    """
    将粘贴的公众号内容转换为小红书风格
    """
    if not request.content or len(request.content.strip()) < 10:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="内容太短，请提供至少10个字符的内容"
        )

    run_id = f"xhs-{uuid.uuid4().hex[:12]}"
    await track_start(
        user_id=current_user.id,
        type="xhs_convert",
        run_id=run_id,
        input_snapshot={"content_length": len(request.content), "original_title": request.original_title},
        display_title=f"转小红书 · {(request.original_title or request.content[:20])}",
        resume_context={"route": "/wechat-to-xhs", "query": {}},
    )

    result = await generate_xhs_content(
        content=request.content,
        original_title=request.original_title
    )

    if not result.get("success"):
        await track_fail(run_id, result.get("error", "未知错误"))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"生成失败: {result.get('error', '未知错误')}"
        )

    await track_complete(run_id, result["data"])

    return {
        "code": 200,
        "message": "转换成功",
        "data": result["data"]
    }


@router.post("/convert-link")
async def convert_link(
    request: LinkConvertRequest,
    current_user: User = Depends(get_current_user),
):
    """
    从公众号链接提取内容并转换为小红书风格
    """
    if not request.url or not request.url.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="请输入公众号链接"
        )

    url = request.url.strip()
    if 'mp.weixin.qq.com' not in url and 'weixin.qq.com' not in url:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="请输入有效的微信公众号链接（mp.weixin.qq.com）"
        )

    run_id = f"xhs-link-{uuid.uuid4().hex[:12]}"
    await track_start(
        user_id=current_user.id,
        type="xhs_convert",
        run_id=run_id,
        input_snapshot={"url": url},
        display_title=f"转小红书(链接) · {url[:30]}",
        resume_context={"route": "/wechat-to-xhs", "query": {}},
    )

    try:
        extracted = await extract_wechat(url)
    except Exception as e:
        await track_fail(run_id, str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"提取公众号内容失败: {str(e)}"
        )

    if not extracted.get("content"):
        error_msg = extracted.get("content", "无法提取文章内容")
        await track_fail(run_id, error_msg)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_msg
        )

    result = await generate_xhs_content(
        content=extracted["content"],
        original_title=extracted.get("title")
    )

    if not result.get("success"):
        await track_fail(run_id, result.get("error", "未知错误"))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"生成失败: {result.get('error', '未知错误')}"
        )

    response_data = {
        **result["data"],
        "original_title": extracted.get("title"),
        "original_author": extracted.get("author")
    }
    await track_complete(run_id, response_data, display_title=f"转小红书 · {extracted.get('title', '')[:30]}")

    return {
        "code": 200,
        "message": "转换成功",
        "data": response_data
    }
