"""创作工具文件上传和链接提取路由。"""

import logging
from fastapi import APIRouter, File, UploadFile, HTTPException
from pydantic import BaseModel

from app.utils.file_extractor import extract_text, UnsupportedFileType
from app.services.link_extractor import extract_link_content

logger = logging.getLogger(__name__)
router = APIRouter()

MAX_FILE_SIZE = 20 * 1024 * 1024  # 20MB


class LinkExtractRequest(BaseModel):
    url: str


@router.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    """上传文件并提取文本内容。支持 PDF / DOCX / TXT / MD。"""
    if not file.filename:
        raise HTTPException(status_code=400, detail="文件名不能为空")

    data = await file.read()
    if len(data) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="文件大小不能超过 20MB")

    try:
        text = await extract_text(
            filename=file.filename,
            data=data,
            content_type=file.content_type,
        )
    except UnsupportedFileType as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"文件提取失败: {e}")
        raise HTTPException(status_code=500, detail=f"文件提取失败: {e}")

    return {
        "filename": file.filename,
        "text": text,
        "char_count": len(text),
    }


@router.post("/extract-link")
async def extract_link(req: LinkExtractRequest):
    """提取链接内容（公众号/小红书/抖音等平台文章）。"""
    if not req.url.strip():
        raise HTTPException(status_code=400, detail="链接不能为空")

    try:
        result = await extract_link_content(req.url)
        return {
            "title": result.get("title", ""),
            "content": result.get("content", ""),
            "author": result.get("author", ""),
            "platform": result.get("platform", "unknown"),
            "tags": result.get("tags", []),
        }
    except Exception as e:
        logger.error(f"链接提取失败: {e}")
        raise HTTPException(status_code=500, detail=f"链接提取失败: {str(e)}")
