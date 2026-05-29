"""
小红书长文发布 API
通过 CDP 驱动 Chrome 完成长文排版和发布
"""
import asyncio
import logging
import os
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.core.security import get_current_user
from app.models.user import User

logger = logging.getLogger(__name__)
router = APIRouter()

_publisher = None
_pending_blocks = None


def _get_publisher():
    global _publisher
    if _publisher is None:
        from app.services.xhs_publisher import XiaohongshuPublisher
        _publisher = XiaohongshuPublisher()
    return _publisher


def _ensure_connected(publisher, target_url_prefix: str = ""):
    if publisher.ws is None:
        publisher.connect(target_url_prefix=target_url_prefix)


class BlockItem(BaseModel):
    type: str = Field(..., description="块类型: text 或 image")
    content: Optional[str] = Field(None, description="文本内容")
    url: Optional[str] = Field(None, description="图片URL")
    local_path: Optional[str] = Field(None, description="本地图片路径")
    alt: Optional[str] = Field(None, description="图片alt")


class StartLongArticleRequest(BaseModel):
    title: str = Field(..., description="文章标题")
    content: str = Field(default="", description="文章正文（纯文本回退）")
    blocks: Optional[List[BlockItem]] = Field(None, description="结构化图文blocks")
    image_paths: Optional[List[str]] = Field(None, description="本地图片路径列表")
    account: Optional[str] = Field(None, description="账号名称")


class SelectTemplateRequest(BaseModel):
    name: str = Field(..., description="模板名称")


class ClickNextStepRequest(BaseModel):
    content: str = Field(default="", description="发布页正文描述")


@router.post("/start-long-article")
async def start_long_article(
    request: StartLongArticleRequest,
    current_user: User = Depends(get_current_user),
):
    """启动长文发布流程：启动 Chrome → 检查登录 → 填写长文 → 一键排版 → 返回模板列表"""
    from app.services.xhs_publisher import ensure_chrome, CDPError

    def _run():
        global _pending_blocks
        if not ensure_chrome(headless=False, account=request.account):
            raise CDPError("无法启动 Chrome 浏览器")

        publisher = _get_publisher()
        try:
            publisher.connect()
        except CDPError:
            publisher.disconnect()
            publisher.connect()

        logged_in = publisher.check_login()
        if not logged_in:
            publisher.open_login_page()
            return {"status": "need_login", "templates": []}

        blocks_raw = None
        if request.blocks:
            blocks_raw = [b.dict() for b in request.blocks]

        # 调试日志：检查 blocks 中的图片
        if blocks_raw:
            img_count = sum(1 for b in blocks_raw if b.get("type") == "image")
            img_urls = [b.get("url", "") for b in blocks_raw if b.get("type") == "image"]
            logger.info(f"[XHS] 收到 {len(blocks_raw)} 个 blocks，其中 {img_count} 个图片")
            for i, u in enumerate(img_urls):
                logger.info(f"[XHS] 图片 {i+1} URL: {u}")

        _pending_blocks = blocks_raw

        templates = publisher.publish_long_article(
            title=request.title,
            content=request.content,
            image_paths=request.image_paths,
            blocks=blocks_raw,
        )
        return {"status": "template_selection", "templates": templates}

    try:
        result = await asyncio.to_thread(_run)
        return {"code": 200, "data": result}
    except Exception as e:
        logger.error(f"长文发布启动失败: {e}")
        raise HTTPException(status_code=500, detail=f"长文发布启动失败: {str(e)[:200]}")


@router.post("/select-template")
async def select_template(
    request: SelectTemplateRequest,
    current_user: User = Depends(get_current_user),
):
    """选择排版模板"""
    from app.services.xhs_publisher import CDPError

    def _run():
        global _pending_blocks
        publisher = _get_publisher()
        _ensure_connected(publisher, target_url_prefix="https://creator.xiaohongshu.com/publish")
        success = publisher.select_template(request.name)
        if not success:
            raise CDPError(f"模板 '{request.name}' 未找到")

        # 图片已在 start-long-article 阶段、一键排版之前插入完成，这里无需再处理
        _pending_blocks = None

        return {"status": "template_selected", "name": request.name}

    try:
        result = await asyncio.to_thread(_run)
        return {"code": 200, "data": result}
    except Exception as e:
        logger.error(f"选择模板失败: {e}")
        raise HTTPException(status_code=500, detail=str(e)[:200])


@router.post("/click-next-step")
async def click_next_step(
    request: ClickNextStepRequest,
    current_user: User = Depends(get_current_user),
):
    """点击下一步并填写发布页描述"""

    def _run():
        publisher = _get_publisher()
        _ensure_connected(publisher, target_url_prefix="https://creator.xiaohongshu.com/publish")
        publisher.click_next_and_prepare_publish(content=request.content)
        return {"status": "ready_to_publish"}

    try:
        result = await asyncio.to_thread(_run)
        return {"code": 200, "data": result}
    except Exception as e:
        logger.error(f"下一步失败: {e}")
        raise HTTPException(status_code=500, detail=str(e)[:200])


@router.post("/click-publish")
async def click_publish(
    current_user: User = Depends(get_current_user),
):
    """点击发布按钮"""
    from app.services.xhs_publisher import CDPError

    def _run():
        publisher = _get_publisher()
        _ensure_connected(publisher, target_url_prefix="https://creator.xiaohongshu.com/publish")
        publisher._click_publish()
        return {"status": "published"}

    try:
        result = await asyncio.to_thread(_run)
        return {"code": 200, "data": result}
    except Exception as e:
        logger.error(f"发布失败: {e}")
        raise HTTPException(status_code=500, detail=str(e)[:200])


@router.get("/login")
async def open_login(
    account: Optional[str] = None,
    current_user: User = Depends(get_current_user),
):
    """打开小红书登录页面供扫码"""
    from app.services.xhs_publisher import ensure_chrome, restart_chrome

    def _run():
        restart_chrome(headless=False, account=account)
        publisher = _get_publisher()
        publisher.disconnect()
        publisher.connect()
        publisher.open_login_page()
        return {"status": "login_ready"}

    try:
        result = await asyncio.to_thread(_run)
        return {"code": 200, "data": result}
    except Exception as e:
        logger.error(f"打开登录页失败: {e}")
        raise HTTPException(status_code=500, detail=str(e)[:200])


@router.post("/check-login")
async def check_login(
    current_user: User = Depends(get_current_user),
):
    """检查登录状态"""
    from app.services.xhs_publisher import ensure_chrome

    def _run():
        if not ensure_chrome(headless=False):
            return {"logged_in": False}
        publisher = _get_publisher()
        try:
            publisher.connect()
        except Exception:
            publisher.disconnect()
            publisher.connect()
        return {"logged_in": publisher.check_login()}

    try:
        result = await asyncio.to_thread(_run)
        return {"code": 200, "data": result}
    except Exception as e:
        logger.error(f"检查登录状态失败: {e}")
        raise HTTPException(status_code=500, detail=str(e)[:200])
