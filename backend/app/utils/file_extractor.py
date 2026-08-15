"""
从上传的文件中提取纯文本，供风格分析使用。
支持：PDF / DOCX / TXT / MD / 图片 / 扫描版 PDF(dashscope qwen-vl 视觉 OCR)。
"""
import base64
import io
import logging
import re
import unicodedata
import zipfile
from xml.etree import ElementTree
from pathlib import Path
from typing import Optional

from app.core.config import settings

logger = logging.getLogger(__name__)

TEXT_EXTS = {".txt", ".md", ".markdown"}
PDF_EXTS = {".pdf"}
DOCX_EXTS = {".docx"}
DOC_EXTS = {".doc"}  # 老版 Word，单独处理给出明确提示
IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp"}

SUPPORTED_EXTS = TEXT_EXTS | PDF_EXTS | DOCX_EXTS | IMAGE_EXTS

_EXTRACTION_CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]+")
_PRESERVED_CJK_PUNCTUATION = frozenset("，。；：！？、（）【】《》“”‘’—…")
_SENTENCE_END_RE = re.compile(r"(?:[\u3002\uff01\uff1f!?\u2026]+|[.!?\u2026][\u201c\u201d\u2018\u2019\'\"\u300d\u300f\u3011\uff09)]*)$")
_SOFT_BREAK_LABEL_RE = re.compile(
    r"^(?:发布时间|封面|标题|作者|摘要|导语|备注|正文|全文|文档类型|稿件类型)\s*[:：]"
)
_SOFT_BREAK_STRUCTURE_RE = re.compile(
    r"^(?:"
    r"[#＃]{1,6}\s*\S|"
    r"[一二三四五六七八九十]+[、.：:]|"
    r"\d{1,2}[.)、．](?!\d)|"
    r"[（(]\d+[）)]|"
    r"第.{1,8}[章节部分]"
    r")"
)
_VERSION_NOISE_RE = re.compile(
    r"^(?:v|ver|version)?\d+(?:\.\d+){1,3}$",
    re.IGNORECASE,
)


class UnsupportedFileType(Exception):
    pass


def _normalize_compatibility_text(text: str) -> str:
    """执行 NFKC，但保留中文正文中有展示意义的全角标点。"""

    pieces: list[str] = []
    pending: list[str] = []
    for char in text:
        if char in _PRESERVED_CJK_PUNCTUATION:
            if pending:
                pieces.append(unicodedata.normalize("NFKC", "".join(pending)))
                pending.clear()
            pieces.append(char)
        else:
            pending.append(char)
    if pending:
        pieces.append(unicodedata.normalize("NFKC", "".join(pending)))
    return "".join(pieces)


def _is_cjk_char(char: str) -> bool:
    if not char:
        return False
    code = ord(char)
    return (
        0x4E00 <= code <= 0x9FFF
        or 0x3400 <= code <= 0x4DBF
        or 0xF900 <= code <= 0xFAFF
        or char in "“”‘’（）【】《》「」『』、"
    )


def _line_join_glue(left: str, right: str) -> str:
    """把 PDF 软换行两侧粘回一句，并在中英文边界补空格。"""

    if not left:
        return right
    if not right:
        return left
    left_ch = left[-1]
    right_ch = right[0]
    if left_ch.isspace() or right_ch.isspace():
        return left + right
    if _is_cjk_char(left_ch) and _is_cjk_char(right_ch):
        return left + right
    if right_ch in "，。！？、；：,.!?;:)]｝》」』”’":
        return left + right
    if left_ch in "（([【《「『“‘":
        return left + right
    if (left_ch.isalnum() or _is_cjk_char(left_ch)) and (
        right_ch.isalnum() or _is_cjk_char(right_ch)
    ):
        return left + " " + right
    return left + right


def _line_looks_incomplete(text: str) -> bool:
    """上一行是否像句中被截断，而不是独立标题/完整短句。"""

    value = (text or "").strip()
    if not value:
        return False
    if re.search(r"[，、；,;]$", value):
        return True
    # 单字/双字中文碎片：发 / 布 / 明 天
    if len(value) <= 2 and re.fullmatch(r"[\u4e00-\u9fff]+", value):
        return True
    # “检索 2024” 这类中英混排以数字结尾，下一行常是“年以来…”
    if re.search(r"[\u4e00-\u9fff].*\d{2,4}$", value):
        return True
    # 常见未完成谓语/介词：三、我用 / 我直接把 / 继续核对
    if re.search(
        r"(?:用|把|将|被|让|从|在|对|向|为|给|与|和|及|或|而|并|"
        r"以及|包括|通过|关于|由于|因为|所以|但是|如果|虽然|"
        r"继续|开始|进行|核对|检索|整理|说明|看到|发现|告诉|交给)$",
        value,
    ):
        return True
    # “题目、发” 这类顿号后只剩半个词
    if re.search(r"[、，,][\u4e00-\u9fffA-Za-z0-9]{1,2}$", value):
        return True
    return False


def _looks_like_independent_title(text: str) -> bool:
    """短品牌行/产品名/独立小标题，不应和邻行硬拼。"""

    value = (text or "").strip()
    if not value or len(value) > 22:
        return False
    if _line_looks_incomplete(value):
        return False
    if re.search(r"[，。！？；,:：]", value):
        return False
    # 纯英文产品名：latent VLA / ScienceOne / PPT
    if re.fullmatch(r"[A-Za-z][A-Za-z0-9._/-]*(?:[ -][A-Za-z][A-Za-z0-9._/-]*)*", value):
        return True
    # 中文品牌/稿头短行：中科闻歌、公众号推文-初稿
    if len(value) <= 16 and not re.search(
        r"[跑走做写看说问找给把用将让被从在对]",
        value,
    ):
        return True
    # 编号标题备选
    if re.match(r"^\d{1,2}[.)、．]", value):
        return True
    return False


def _should_reflow_soft_break(previous: str, current: str) -> bool:
    """判断单换行是否只是 PDF 视觉折行，而不是段落/结构边界。"""

    prev = (previous or "").strip()
    curr = (current or "").strip()
    if not prev or not curr:
        return False
    if _VERSION_NOISE_RE.fullmatch(re.sub(r"\s+", "", prev)):
        return False
    if _VERSION_NOISE_RE.fullmatch(re.sub(r"\s+", "", curr)):
        return False
    if _SENTENCE_END_RE.search(prev):
        return False
    if _SOFT_BREAK_LABEL_RE.match(prev) or _SOFT_BREAK_LABEL_RE.match(curr):
        return False
    if re.search(r"[:：]$", prev) and len(re.sub(r"\s+", "", prev)) <= 16:
        return False
    # 下一行是新章节/列表时保留换行
    if _SOFT_BREAK_STRUCTURE_RE.match(curr):
        return False
    # 上一行是完整小标题（如“第一步，检索文献”）时保留；
    # 但“三、我用 / 三、我用 latent VLA”这种标题写到一半应继续合并。
    if _SOFT_BREAK_STRUCTURE_RE.match(prev) and not _line_looks_incomplete(prev):
        # 结构编号后的内容若以英文/数字收尾，下一行又是中文叙述，仍是折行。
        if re.search(r"[A-Za-z0-9]$", prev) and re.match(r"^[\u4e00-\u9fff]", curr):
            return True
        return False
    # 上一行以逗号/顿号等收尾，几乎一定是折行。
    if re.search(r"[，、；,;]$", prev):
        return True
    # 两侧都像独立短标题/品牌行时不合并，避免稿头被拼成一行。
    if _looks_like_independent_title(prev) and _looks_like_independent_title(curr):
        return False
    # 默认：未结束的上一行 + 以中英文开头的下一行 = PDF 软换行
    if re.search(r"[\u4e00-\u9fffA-Za-z0-9]$", prev) and re.search(
        r"^[\u4e00-\u9fffA-Za-z0-9]",
        curr,
    ):
        return True
    return False


def _reflow_soft_line_breaks(text: str) -> str:
    """合并 PDF 提取时的句内软换行，保留空行作为段落边界。"""

    if not text or "\n" not in text:
        return text
    lines = text.split("\n")
    merged: list[str] = []
    for line in lines:
        if not merged:
            merged.append(line)
            continue
        previous = merged[-1]
        # 空行始终保留，作为真实段落边界。
        if not previous.strip() or not line.strip():
            merged.append(line)
            continue
        if _should_reflow_soft_break(previous, line):
            merged[-1] = _line_join_glue(previous.rstrip(), line.lstrip())
            continue
        merged.append(line)
    return "\n".join(merged)


def normalize_extracted_text(text: str) -> str:
    """清理 PDF/Word 提取噪声，同时保留可读的行结构。

    pypdf 会把视觉文本框边界输出成 ``\x01`` 等控制字符；这些字符既不是
    正文，也不是可靠的语义边界。先转成换行后，版本号等独立噪声才能被后续
    规则识别。NFKC 还会把 PDF 中常见的兼容汉字/全角字符归一化，但不会
    改写中文正文中的逗号、冒号等展示标点。

    另外，PDF 常把同一句拆成多行（甚至把“明天”拆成“明\\n天”）。这里只
    合并单换行上的软折行，双换行仍视为段落边界。
    """

    value = _normalize_compatibility_text(text or "")
    value = value.replace("\r\n", "\n").replace("\r", "\n")
    value = _EXTRACTION_CONTROL_RE.sub("\n", value)
    value = re.sub(r"[\u200b\u200c\u200d\ufeff]", "", value)
    value = value.replace("\u00a0", " ").replace("\u3000", " ")
    value = re.sub(r"[^\S\n]+", " ", value)
    value = re.sub(r" *\n *", "\n", value)
    value = re.sub(r"\n{3,}", "\n\n", value)
    value = _reflow_soft_line_breaks(value)
    value = re.sub(r"\n{3,}", "\n\n", value)
    return value.strip()


def _ext(filename: str) -> str:
    if not filename or "." not in filename:
        return ""
    return "." + filename.rsplit(".", 1)[-1].lower()


def _extract_pdf(data: bytes) -> str:
    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(data))
    if reader.is_encrypted:
        try:
            reader.decrypt("")
        except Exception as e:
            logger.warning(f"PDF 解密失败（可能加密）: {e}")

    pages = []
    for idx, page in enumerate(reader.pages):
        try:
            text = page.extract_text() or ""
            pages.append(text)
            logger.info(f"PDF 第 {idx+1} 页提取字符数: {len(text)}")
        except Exception as e:
            logger.warning(f"PDF 第 {idx+1} 页提取失败: {e}")
    result = "\n".join(p for p in pages if p).strip()
    logger.info(f"PDF 共 {len(reader.pages)} 页，合计提取 {len(result)} 字符")
    return result


async def _ocr_pdf_via_vision(data: bytes) -> str:
    """扫描版 PDF 兜底：用 PyMuPDF 逐页转图片走视觉 OCR(qwen-vl)。"""
    if not _vision_api_key():
        logger.warning("未配置 dashscope key(TONGYI/EMBEDDING)，跳过 PDF OCR 兜底")
        return ""
    try:
        import fitz  # PyMuPDF
    except ImportError:
        logger.warning("未安装 PyMuPDF，无法对扫描 PDF 做 OCR。pip install PyMuPDF")
        return ""

    try:
        doc = fitz.open(stream=data, filetype="pdf")
    except Exception as e:
        logger.error(f"扫描 PDF 打开失败: {e}")
        return ""

    pieces = []
    for idx in range(min(len(doc), 20)):  # 限 20 页，防超额
        try:
            png = doc[idx].get_pixmap(dpi=150).tobytes("png")
        except Exception as e:
            logger.warning(f"PDF 第 {idx+1} 页转图失败: {e}")
            continue
        text = await _extract_image_via_vision(png, "image/png")
        logger.info(f"PDF OCR 第 {idx+1} 页字符数: {len(text)}")
        if text:
            pieces.append(text)
    return "\n".join(pieces).strip()


async def _ocr_pdf_path_via_vision(path: Path) -> str:
    """从文件路径逐页 OCR，避免扫描 PDF 为 OCR 再整体复制一份 bytes。"""

    if not _vision_api_key():
        logger.warning("未配置 dashscope key(TONGYI/EMBEDDING)，跳过 PDF OCR 兜底")
        return ""
    try:
        import fitz
    except ImportError:
        logger.warning("未安装 PyMuPDF，无法对扫描 PDF 做 OCR。pip install PyMuPDF")
        return ""
    try:
        document = fitz.open(str(path))
    except Exception as exc:
        logger.error("扫描 PDF 打开失败: %s", exc)
        return ""
    pieces = []
    try:
        for index in range(min(len(document), 20)):
            try:
                png = document[index].get_pixmap(dpi=150).tobytes("png")
            except Exception as exc:
                logger.warning("PDF 第 %s 页转图失败: %s", index + 1, exc)
                continue
            text = await _extract_image_via_vision(png, "image/png")
            if text:
                pieces.append(text)
    finally:
        document.close()
    return "\n".join(pieces).strip()


def _extract_docx(data: bytes) -> str:
    try:
        from docx import Document
    except ImportError as e:
        logger.error(f"python-docx 未安装: {e}")
        raise

    try:
        doc = Document(io.BytesIO(data))
    except Exception as e:
        logger.error(f"DOCX 打开失败（可能不是合法 .docx，或文件被加密）: {e}")
        raise

    parts = [p.text for p in doc.paragraphs if p.text]
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                if cell.text:
                    parts.append(cell.text)
    result = "\n".join(parts).strip()
    logger.info(f"DOCX 提取段落 {len(parts)} 段，合计 {len(result)} 字符")
    return result


def _extract_docx_path(path: Path) -> str:
    """只流式读取 DOCX 文字 XML，跳过可能占几十 MB 的图片媒体部件。"""

    parts: list[str] = []
    with zipfile.ZipFile(path) as archive:
        names = set(archive.namelist())
        xml_names = ["word/document.xml"]
        xml_names.extend(sorted(
            name for name in names
            if re.fullmatch(r"word/(?:header|footer)\d+\.xml", name)
        ))
        xml_names.extend(
            name for name in ("word/footnotes.xml", "word/endnotes.xml")
            if name in names
        )
        for name in xml_names:
            if name not in names:
                continue
            paragraph_text: list[str] = []
            with archive.open(name) as source:
                for _event, element in ElementTree.iterparse(source, events=("end",)):
                    tag = element.tag.rsplit("}", 1)[-1]
                    if tag == "t" and element.text:
                        paragraph_text.append(element.text)
                    elif tag == "tab":
                        paragraph_text.append("\t")
                    elif tag in {"br", "cr"}:
                        paragraph_text.append("\n")
                    elif tag == "p":
                        value = "".join(paragraph_text).strip()
                        if value:
                            parts.append(value)
                        paragraph_text.clear()
                    element.clear()
    result = "\n".join(parts).strip()
    logger.info("DOCX 路径解析段落 %s 段，合计 %s 字符", len(parts), len(result))
    return result


def _extract_text(data: bytes) -> str:
    for encoding in ("utf-8", "gbk", "gb18030", "latin-1"):
        try:
            return data.decode(encoding).strip()
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="ignore").strip()


def _vision_api_key() -> Optional[str]:
    """视觉 OCR 用的 dashscope key:优先 TONGYI,回退到 embedding 的 dashscope key。"""
    return settings.TONGYI_API_KEY or settings.EMBEDDING_API_KEY


async def _extract_image_via_vision(data: bytes, mime: str) -> str:
    """用 dashscope qwen-vl 对图片 OCR / 内容描述(OpenAI 兼容端点)。"""
    api_key = _vision_api_key()
    if not api_key:
        logger.warning("未配置 dashscope key(TONGYI/EMBEDDING)，跳过图片 OCR")
        return ""

    try:
        import openai

        client = openai.AsyncOpenAI(
            api_key=api_key,
            base_url=settings.VISION_API_BASE,
        )
        b64 = base64.b64encode(data).decode()
        data_url = f"data:{mime or 'image/png'};base64,{b64}"

        resp = await client.chat.completions.create(
            model=settings.VISION_MODEL,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": "请提取图片中的全部文字内容，按原文排版输出，不要添加任何解释。如果图片不含文字，请简要描述图片所表达的主题与风格特征。",
                        },
                        {"type": "image_url", "image_url": {"url": data_url}},
                    ],
                }
            ],
            temperature=0,
            max_tokens=settings.VISION_MAX_TOKENS,
        )
        return (resp.choices[0].message.content or "").strip()
    except Exception as e:
        logger.error(f"图片 OCR 失败: {e}")
        return ""


async def extract_text(
    *,
    filename: str,
    data: bytes,
    content_type: Optional[str] = None,
) -> str:
    """
    根据文件名后缀分发到对应解析器。返回提取到的纯文本。
    """
    ext = _ext(filename)
    result = ""
    if ext in TEXT_EXTS:
        result = _extract_text(data)
    elif ext in PDF_EXTS:
        text = _extract_pdf(data)
        # 文本层只要有内容就保留。短 PDF（封面、单句说明、短经验卡）
        # 仍然是合法的可复制文档，不能因为字符数少而被 OCR 结果覆盖；
        # OCR 只针对真正没有文本层的扫描版 PDF。
        if not text:
            logger.warning("PDF 没有可复制文本，尝试 OCR 兜底")
            ocr_text = await _ocr_pdf_via_vision(data)
            if ocr_text:
                text = ocr_text
        result = text
    elif ext in DOCX_EXTS:
        result = _extract_docx(data)
    elif ext in IMAGE_EXTS:
        result = await _extract_image_via_vision(data, content_type or "image/png")
    elif ext in DOC_EXTS:
        raise UnsupportedFileType(
            "不支持老版 .doc 格式，请用 Word/WPS 另存为 .docx 后再上传"
        )
    else:
        raise UnsupportedFileType(f"不支持的文件类型: {ext or filename}")
    return normalize_extracted_text(result)


async def extract_text_from_path(
    *,
    filename: str,
    path: Path,
    content_type: Optional[str] = None,
) -> str:
    """从暂存路径解析大文档，避免再次把带图片的 Word/PDF 整份复制到内存。"""

    ext = _ext(filename)
    if ext in TEXT_EXTS:
        result = _extract_text(path.read_bytes())
    elif ext in PDF_EXTS:
        from pypdf import PdfReader

        reader = PdfReader(str(path))
        if reader.is_encrypted:
            try:
                reader.decrypt("")
            except Exception as exc:
                logger.warning("PDF 解密失败（可能加密）: %s", exc)
        pages = []
        for index, page in enumerate(reader.pages):
            try:
                pages.append(page.extract_text() or "")
            except Exception as exc:
                logger.warning("PDF 第 %s 页提取失败: %s", index + 1, exc)
        result = "\n".join(page for page in pages if page).strip()
        if not result:
            result = await _ocr_pdf_path_via_vision(path)
    elif ext in DOCX_EXTS:
        result = _extract_docx_path(path)
    elif ext in IMAGE_EXTS:
        result = await _extract_image_via_vision(path.read_bytes(), content_type or "image/png")
    elif ext in DOC_EXTS:
        raise UnsupportedFileType("不支持老版 .doc 格式，请用 Word/WPS 另存为 .docx 后再上传")
    else:
        raise UnsupportedFileType(f"不支持的文件类型: {ext or filename}")
    return normalize_extracted_text(result)
