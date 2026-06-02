"""创作工具文件上传路由。"""

import logging
from fastapi import APIRouter, File, UploadFile, HTTPException

from app.utils.file_extractor import extract_text, UnsupportedFileType

logger = logging.getLogger(__name__)
router = APIRouter()

MAX_FILE_SIZE = 20 * 1024 * 1024  # 20MB


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
