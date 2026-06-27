"""创作工具文件上传和链接提取路由。"""

import logging
from fastapi import APIRouter, File, UploadFile, HTTPException
from pydantic import BaseModel, Field
from typing import Optional
from openai import AsyncOpenAI
from app.core.config import settings

from app.utils.file_extractor import extract_text, UnsupportedFileType
from app.services.scraping.link_extractor import extract_link_content

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


# ──────────────────────────────────────────────
# 智能换行：发布前由 LLM 对正文做段落拆分
# ──────────────────────────────────────────────
class FormatParagraphsRequest(BaseModel):
    content: str = Field(..., description="纯文本或 markdown 正文")


_FORMAT_SYSTEM = """你是一个排版助手。你的唯一任务是在输入文本中合适的位置插入段落换行（\\n\\n）。

严格遵守：
1. 绝对不能修改、删减、增加、重排任何文字内容，包括标点符号、用词、语序。
2. 保留所有原有的格式标记（如 ## 标题、### 小标题、- 列表等），不要添加任何新标记。
3. 目标：每个段落在手机屏幕上不超过 4 行（约 70-80 个汉字）。
4. 大约每 1~2 句话就应该分段。如果两句话都很短（各不超过 15 字）且语义紧密相连，可以不拆。
5. 标题行（## 开头的行）前后保留空行，但不要在标题内部插入额外换行。
6. 只输出修改后的完整文本，不要输出任何解释、前缀、后缀。
7. 绝对不要在数字中间断行！特别是小数点（如 88.4%、3.14、100.5）必须保持完整，不能把数字拆成两行。
"""


@router.post("/format-paragraphs")
async def format_paragraphs(req: FormatParagraphsRequest):
    """调用 LLM 对正文做智能换行，保证原文内容不变。"""
    content = req.content.strip()
    if not content:
        return {"content": ""}
    # 短文不需要换行处理
    if len(content) < 120:
        return {"content": content}
    try:
        client = AsyncOpenAI(
            api_key=settings.DEEPSEEK_API_KEY,
            base_url=settings.DEEPSEEK_API_BASE,
        )
        resp = await client.chat.completions.create(
            model=settings.DEEPSEEK_MODEL,
            messages=[
                {"role": "system", "content": _FORMAT_SYSTEM},
                {"role": "user", "content": content},
            ],
            temperature=0.2,
            max_tokens=8192,
        )
        result = resp.choices[0].message.content or ""
        return {"content": result.strip()}
    except Exception as e:
        logger.error(f"[format-paragraphs] LLM 调用失败: {e}", exc_info=True)
        # 降级：返回原文不处理
        return {"content": content}
