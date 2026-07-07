"""Shared upload validation helpers.

These checks do not trust client-provided filename extensions or Content-Type
headers. They inspect file signatures before public storage or text extraction.
"""
import io
import secrets
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Set

from PIL import Image, UnidentifiedImageError


class UploadSecurityError(ValueError):
    """Raised when an uploaded file violates the upload security policy."""


@dataclass(frozen=True)
class SafeUpload:
    filename: str
    content_type: str
    data: bytes
    size: int
    ext: str


IMAGE_TYPES = {
    "jpeg": ("image/jpeg", ".jpg"),
    "png": ("image/png", ".png"),
    "gif": ("image/gif", ".gif"),
    "webp": ("image/webp", ".webp"),
}
DOCUMENT_EXTS = {".pdf", ".docx", ".txt", ".md", ".markdown"}
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".gif", ".webp"}
TEXT_EXTS = {".txt", ".md", ".markdown"}


def _extension(filename: Optional[str]) -> str:
    return Path(filename or "").suffix.lower()


def _random_filename(ext: str) -> str:
    return f"{secrets.token_urlsafe(18)}{ext}"


def _is_probably_html_or_svg(data: bytes) -> bool:
    prefix = data[:512].lstrip().lower()
    return (
        prefix.startswith(b"<!doctype html")
        or prefix.startswith(b"<html")
        or prefix.startswith(b"<script")
        or prefix.startswith(b"<svg")
    )


def _looks_like_text(data: bytes) -> bool:
    if b"\x00" in data[:4096]:
        return False
    try:
        data[:4096].decode("utf-8")
        return True
    except UnicodeDecodeError:
        try:
            data[:4096].decode("gb18030")
            return True
        except UnicodeDecodeError:
            return False


def detect_image_type(data: bytes) -> Optional[str]:
    if data.startswith(b"\xff\xd8\xff"):
        return "jpeg"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if data.startswith((b"GIF87a", b"GIF89a")):
        return "gif"
    if len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "webp"
    return None


def _is_docx(data: bytes) -> bool:
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            names = set(zf.namelist())
            return "[Content_Types].xml" in names and any(name.startswith("word/") for name in names)
    except zipfile.BadZipFile:
        return False


def detect_document_type(data: bytes) -> Optional[str]:
    if data.startswith(b"%PDF-"):
        return ".pdf"
    if _is_docx(data):
        return ".docx"
    image_type = detect_image_type(data)
    if image_type:
        return IMAGE_TYPES[image_type][1]
    if _looks_like_text(data) and not _is_probably_html_or_svg(data):
        return ".txt"
    return None


def _verify_image(data: bytes, image_type: str) -> None:
    try:
        with Image.open(io.BytesIO(data)) as img:
            img.verify()
            if img.format and img.format.lower() == "svg":
                raise UploadSecurityError("不支持 SVG 图片")
            expected = "jpeg" if img.format == "JPEG" else (img.format or "").lower()
            if expected and expected != image_type:
                raise UploadSecurityError("图片真实格式与文件头不一致")
    except UploadSecurityError:
        raise
    except (UnidentifiedImageError, OSError) as exc:
        raise UploadSecurityError("图片文件已损坏或格式不受支持") from exc


def _reencode_image(data: bytes, image_type: str) -> bytes:
    if image_type == "gif":
        return data
    try:
        with Image.open(io.BytesIO(data)) as img:
            img.load()
            out = io.BytesIO()
            if image_type == "jpeg":
                img.convert("RGB").save(out, format="JPEG", quality=92, optimize=True)
            elif image_type == "png":
                img.save(out, format="PNG", optimize=True)
            elif image_type == "webp":
                img.save(out, format="WEBP", quality=92, method=6)
            else:
                return data
            return out.getvalue()
    except Exception as exc:
        raise UploadSecurityError("图片重编码失败") from exc


def validate_image_upload(
    *,
    filename: Optional[str],
    data: bytes,
    max_size: int,
    allowed_types: Optional[Set[str]] = None,
    reencode: bool = True,
) -> SafeUpload:
    if not data:
        raise UploadSecurityError("上传文件不能为空")
    if len(data) > max_size:
        raise UploadSecurityError(f"文件大小不能超过 {max_size // 1024 // 1024}MB")
    if _is_probably_html_or_svg(data):
        raise UploadSecurityError("不支持 SVG/HTML 文件")

    image_type = detect_image_type(data)
    if not image_type:
        raise UploadSecurityError("只支持 JPEG、PNG、GIF、WebP 图片")
    if allowed_types and image_type not in allowed_types:
        raise UploadSecurityError("图片格式不受支持")

    ext = _extension(filename)
    if ext not in IMAGE_EXTS:
        raise UploadSecurityError("图片扩展名不受支持")
    canonical_ext = IMAGE_TYPES[image_type][1]
    if ext == ".jpeg":
        ext = ".jpg"
    if ext != canonical_ext:
        raise UploadSecurityError("图片扩展名与真实格式不一致")

    _verify_image(data, image_type)
    safe_data = _reencode_image(data, image_type) if reencode else data
    return SafeUpload(
        filename=_random_filename(canonical_ext),
        content_type=IMAGE_TYPES[image_type][0],
        data=safe_data,
        size=len(safe_data),
        ext=canonical_ext,
    )


def validate_document_upload(
    *,
    filename: Optional[str],
    data: bytes,
    max_size: int,
) -> SafeUpload:
    if not data:
        raise UploadSecurityError("上传文件不能为空")
    if len(data) > max_size:
        raise UploadSecurityError(f"文件大小不能超过 {max_size // 1024 // 1024}MB")
    if _is_probably_html_or_svg(data):
        raise UploadSecurityError("不支持 SVG/HTML 文件")

    ext = _extension(filename)
    if ext not in DOCUMENT_EXTS and ext not in IMAGE_EXTS:
        raise UploadSecurityError("文件扩展名不受支持")

    detected_ext = detect_document_type(data)
    if not detected_ext:
        raise UploadSecurityError("无法识别文件真实类型")
    if detected_ext in IMAGE_EXTS:
        image_type = detect_image_type(data)
        if not image_type:
            raise UploadSecurityError("无法识别图片真实类型")
        _verify_image(data, image_type)
        detected_ext = IMAGE_TYPES[image_type][1]

    normalized_ext = ".jpg" if ext == ".jpeg" else ext
    normalized_detected = ".jpg" if detected_ext == ".jpeg" else detected_ext
    if normalized_ext in TEXT_EXTS and detected_ext == ".txt":
        normalized_detected = normalized_ext
    if normalized_ext != normalized_detected:
        raise UploadSecurityError("文件扩展名与真实类型不一致")

    content_type = {
        ".pdf": "application/pdf",
        ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ".txt": "text/plain",
        ".md": "text/markdown",
        ".markdown": "text/markdown",
        ".jpg": "image/jpeg",
        ".png": "image/png",
        ".gif": "image/gif",
        ".webp": "image/webp",
    }.get(normalized_ext, "application/octet-stream")
    return SafeUpload(
        filename=_random_filename(normalized_ext),
        content_type=content_type,
        data=data,
        size=len(data),
        ext=normalized_ext,
    )
