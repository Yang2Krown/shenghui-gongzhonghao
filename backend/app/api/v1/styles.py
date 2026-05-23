import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

from app.core.security import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.models.style import StyleProfile
from app.schemas.style import (
    StyleProfileCreate,
    StyleProfileUpdate,
    StyleProfileResponse,
    StyleSourceCreate,
    StyleSourceResponse,
    StyleProfileWithSources,
    TrainStyleRequest,
    TrainStyleResponse,
    PreviewStyleRequest,
    PreviewStyleResponse,
    StyleAnalysisRequest,
    StyleAnalysisResponse,
)
from app.crud.style import style as style_crud, style_source as source_crud
from app.services.style_service import style_service
from app.utils.file_extractor import (
    SUPPORTED_EXTS,
    UnsupportedFileType,
    extract_text,
)

MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
MAX_FILES = 10
MAX_TOTAL_CHARS = 60000

router = APIRouter()


# ===== 风格档案 CRUD =====

@router.get("", response_model=List[StyleProfileResponse])
async def get_styles(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    skip: int = 0,
    limit: int = 100
):
    """获取用户的风格档案列表"""
    styles = await style_crud.get_by_user(
        db=db,
        user_id=current_user.id,
        skip=skip,
        limit=limit
    )
    return styles


@router.get("/profile", response_model=StyleProfileWithSources)
async def get_style_profile(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取风格档案（含素材列表）"""
    # 获取用户的第一个风格档案
    styles = await style_crud.get_by_user(
        db=db,
        user_id=current_user.id,
        limit=1
    )
    profile = styles[0] if styles else None

    # 获取素材列表
    sources = await source_crud.get_by_user(
        db=db,
        user_id=current_user.id
    )

    return StyleProfileWithSources(
        profile=profile.to_dict() if profile else None,
        sources=[s.to_dict() for s in sources]
    )


@router.get("/{style_id}", response_model=StyleProfileResponse)
async def get_style(
    style_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取风格档案详情"""
    style = await style_crud.get(db=db, id=style_id)
    if not style:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="风格档案不存在"
        )

    # 检查权限
    if style.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="没有权限访问此风格档案"
        )

    return style


@router.post("", response_model=StyleProfileResponse)
async def create_style(
    style_in: StyleProfileCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """创建风格档案"""
    style = await style_crud.create(
        db=db,
        obj_in=style_in,
        user_id=current_user.id
    )
    return style


@router.put("/{style_id}", response_model=StyleProfileResponse)
async def update_style(
    style_id: int,
    style_in: StyleProfileUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """更新风格档案"""
    style = await style_crud.get(db=db, id=style_id)
    if not style:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="风格档案不存在"
        )

    # 检查权限
    if style.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="没有权限修改此风格档案"
        )

    style = await style_crud.update(
        db=db,
        db_obj=style,
        obj_in=style_in
    )
    return style


@router.delete("/{style_id}", response_model=StyleProfileResponse)
async def delete_style(
    style_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """删除风格档案"""
    style = await style_crud.get(db=db, id=style_id)
    if not style:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="风格档案不存在"
        )

    # 检查权限
    if style.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="没有权限删除此风格档案"
        )

    style = await style_crud.remove(db=db, id=style_id)
    return style


# ===== 训练素材管理 =====

@router.post("/sources", response_model=StyleSourceResponse)
async def add_source(
    source_in: StyleSourceCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """添加训练素材（文字/链接）"""
    # 获取用户的风格档案
    styles = await style_crud.get_by_user(db=db, user_id=current_user.id, limit=1)
    profile_id = styles[0].id if styles else None

    # 处理链接类型
    raw_text = source_in.raw_text
    url = source_in.url
    content_type = source_in.content_type or "text"
    preview = None
    title = source_in.title

    if content_type == "link" and url:
        # 自动提取链接内容
        try:
            from app.services.link_extractor import extract_link_content, detect_platform
            logger.info(f"开始提取链接内容: {url[:100]}")
            extracted = await extract_link_content(url)
            logger.info(f"提取结果: platform={extracted.get('platform')}, content_len={len(extracted.get('content', ''))}")

            platform = detect_platform(url) or extracted.get("platform", "link")
            content_type = platform  # xhs, gzh, douyin

            # 使用提取到的内容
            extracted_content = extracted.get("content", "")
            if extracted_content and len(extracted_content) > 10:
                raw_text = extracted_content
                preview = extracted_content[:200].replace("\n", " ")
            else:
                # 提取失败或内容太短
                logger.warning(f"提取内容为空或太短: {extracted}")
                preview = f"链接提取未获取到内容: {url[:100]}"

            # 如果没有标题，使用提取到的标题
            if not title and extracted.get("title"):
                title = extracted["title"]

        except Exception as e:
            logger.error(f"链接内容提取失败: {e}", exc_info=True)
            preview = f"链接提取失败，请使用「粘贴文字」方式添加"

    if raw_text:
        # 生成预览（如果没有的话）
        if not preview:
            preview = raw_text[:200].replace("\n", " ")
        word_count = len(raw_text)
    else:
        word_count = 0

    # 更新 source_in 的 title
    if title:
        source_in.title = title

    source = await source_crud.create(
        db=db,
        obj_in=source_in,
        user_id=current_user.id,
        profile_id=profile_id,
        preview=preview,
        word_count=word_count,
        url=url
    )
    return source


@router.post("/sources/upload", response_model=StyleSourceResponse)
async def upload_source_file(
    file: UploadFile = File(...),
    title: Optional[str] = Form(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """上传文件素材"""
    # 获取用户的风格档案
    styles = await style_crud.get_by_user(db=db, user_id=current_user.id, limit=1)
    profile_id = styles[0].id if styles else None

    # 读取文件
    data = await file.read()
    if len(data) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"文件 {file.filename} 超过 10MB 限制"
        )

    # 提取文本
    try:
        extracted = await extract_text(
            filename=file.filename or "",
            data=data,
            content_type=file.content_type,
        )
    except UnsupportedFileType as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e) + f"。支持的类型: {', '.join(sorted(SUPPORTED_EXTS))}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"解析 {file.filename} 失败: {e}"
        )

    logger.info(
        f"上传文件 {file.filename} 大小 {len(data)} 字节，提取文本字符数 {len(extracted or '')}"
    )

    if not extracted or not extracted.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="未能从文件中提取到文本内容（可能是扫描版 PDF 或加密文件）"
        )

    # 限制长度
    if len(extracted) > MAX_TOTAL_CHARS:
        extracted = extracted[:MAX_TOTAL_CHARS]

    # 判断文件类型
    filename_lower = (file.filename or "").lower()
    if filename_lower.endswith(".pdf"):
        content_type = "file"
    elif filename_lower.endswith(".docx"):
        content_type = "file"
    else:
        content_type = "file"

    # 创建素材
    source = await source_crud.create(
        db=db,
        obj_in=StyleSourceCreate(
            title=title or file.filename,
            content_type=content_type,
            raw_text=extracted
        ),
        user_id=current_user.id,
        profile_id=profile_id,
        preview=extracted[:200].replace("\n", " "),
        word_count=len(extracted)
    )
    return source


@router.delete("/sources/{source_id}")
async def delete_source(
    source_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """删除训练素材"""
    source = await source_crud.get(db=db, id=source_id)
    if not source:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="素材不存在"
        )

    # 检查权限
    if source.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="没有权限删除此素材"
        )

    try:
        await source_crud.remove(db=db, id=source_id)
    except Exception as e:
        logger.error(f"删除素材 {source_id} 失败", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"删除失败: {e}"
        )
    return {"success": True}


# ===== 风格训练 =====

@router.post("/train", response_model=TrainStyleResponse)
async def train_style_endpoint(
    request: TrainStyleRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """训练风格"""
    # 获取用户的所有素材
    sources = await source_crud.get_by_user(db=db, user_id=current_user.id)

    if not sources:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="请先添加至少一篇素材"
        )

    # 汇总所有素材文本
    corpus_parts = []
    total_words = 0
    for i, s in enumerate(sources):
        if s.raw_text:
            corpus_parts.append(f"[{i+1}] {s.raw_text}")
            total_words += s.word_count or 0

    if not corpus_parts:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="素材中没有可分析的文本内容"
        )

    combined_corpus = "\n\n---\n\n".join(corpus_parts)

    # 调用 AI 分析风格
    try:
        result = await style_service.train_style(
            corpus=combined_corpus,
            model=request.model
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"训练失败: {e}"
        )

    # 获取或创建风格档案
    styles = await style_crud.get_by_user(db=db, user_id=current_user.id, limit=1)
    if styles:
        profile = styles[0]
    else:
        profile = await style_crud.create(
            db=db,
            obj_in=StyleProfileCreate(name="我的风格"),
            user_id=current_user.id
        )

    # 更新训练结果
    profile = await style_crud.update_training_result(
        db=db,
        db_obj=profile,
        signature=result["signature"],
        radar=result["radar"],
        traits=result["traits"],
        source_count=len(sources),
        total_words=total_words
    )

    return TrainStyleResponse(
        version=profile.version,
        signature=profile.signature,
        radar=profile.radar,
        traits=profile.traits,
        source_count=profile.source_count,
        total_words=profile.total_words
    )


# ===== 风格预览 =====

@router.post("/preview", response_model=PreviewStyleResponse)
async def preview_style_endpoint(
    request: PreviewStyleRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """风格预览"""
    # 获取用户的风格档案
    styles = await style_crud.get_by_user(db=db, user_id=current_user.id, limit=1)
    if not styles:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="请先训练风格"
        )

    profile = styles[0]
    if not profile.signature:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="风格档案尚未训练，请先点击训练"
        )

    # 调用 AI 生成预览
    try:
        content = await style_service.preview_style(
            profile=profile,
            topic=request.topic,
            model=request.model
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"预览生成失败: {e}"
        )

    return PreviewStyleResponse(content=content)


# ===== 旧接口（保留兼容） =====

@router.post("/analyze", response_model=StyleAnalysisResponse)
async def analyze_article_style(
    analysis_in: StyleAnalysisRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """分析文章风格"""
    try:
        result = await style_service.analyze_article_style(
            content=analysis_in.content,
            title=analysis_in.title
        )
        return result
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"风格分析失败: {str(e)}"
        )


@router.post("/analyze-upload", response_model=StyleAnalysisResponse)
async def analyze_uploaded_style(
    files: List[UploadFile] = File(default_factory=list),
    text: Optional[str] = Form(None),
    title: Optional[str] = Form(None),
    current_user: User = Depends(get_current_user),
):
    """上传文件与/或粘贴文本，分析个人写作风格"""
    files = files or []
    if not files and not (text and text.strip()):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="请至少上传一个文件或输入文本",
        )
    if len(files) > MAX_FILES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"单次最多上传 {MAX_FILES} 个文件",
        )

    chunks: List[str] = []
    sources: List[dict] = []

    if text and text.strip():
        snippet = text.strip()
        chunks.append(snippet)
        sources.append({"name": "粘贴文本", "chars": len(snippet)})

    for f in files:
        data = await f.read()
        if len(data) > MAX_FILE_SIZE:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"文件 {f.filename} 超过 10MB 限制",
            )
        try:
            extracted = await extract_text(
                filename=f.filename or "",
                data=data,
                content_type=f.content_type,
            )
        except UnsupportedFileType as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e) + f"。支持的类型: {', '.join(sorted(SUPPORTED_EXTS))}",
            )
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"解析 {f.filename} 失败: {e}",
            )

        if extracted:
            chunks.append(extracted)
            sources.append({"name": f.filename, "chars": len(extracted)})

    combined = "\n\n---\n\n".join(chunks).strip()
    if not combined:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="未能从输入中提取到任何文本内容",
        )

    if len(combined) > MAX_TOTAL_CHARS:
        combined = combined[:MAX_TOTAL_CHARS]

    try:
        result = await style_service.analyze_article_style(
            content=combined,
            title=title or (sources[0]["name"] if sources else None),
        )
        result["sources"] = sources
        return result
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"风格分析失败: {e}",
        )


@router.get("/suggestions")
async def get_style_suggestions(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取风格建议"""
    suggestions = await style_service.get_style_suggestions(
        user_id=current_user.id,
        db=db
    )
    return {"suggestions": suggestions}


@router.post("/apply")
async def apply_style_to_content(
    request: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """将风格应用到内容"""
    style_id = request.get("style_id")
    content = request.get("content")

    if not style_id or not content:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="缺少必要参数"
        )

    # 获取风格档案
    style = await style_crud.get(db=db, id=style_id)
    if not style:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="风格档案不存在"
        )

    # 检查权限
    if style.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="没有权限使用此风格档案"
        )

    try:
        result = await style_service.apply_style(
            content=content,
            style=style
        )
        return result
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"风格应用失败: {str(e)}"
        )
