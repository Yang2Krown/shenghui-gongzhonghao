import io

import pytest
from PIL import Image

from app.core.upload_security import (
    UploadSecurityError,
    validate_document_upload,
    validate_image_upload,
)


def _image_bytes(fmt: str) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (8, 8), color=(20, 80, 140)).save(buf, format=fmt)
    return buf.getvalue()


def test_validate_image_upload_accepts_real_png_and_randomizes_name():
    data = _image_bytes("PNG")

    safe = validate_image_upload(
        filename="avatar.png",
        data=data,
        max_size=1024 * 1024,
        allowed_types={"png"},
        reencode=True,
    )

    assert safe.content_type == "image/png"
    assert safe.ext == ".png"
    assert safe.filename.endswith(".png")
    assert safe.filename != "avatar.png"
    assert safe.size > 0


def test_validate_image_upload_rejects_html_disguised_as_jpg():
    with pytest.raises(UploadSecurityError, match="SVG/HTML"):
        validate_image_upload(
            filename="avatar.jpg",
            data=b"<!doctype html><script>alert(1)</script>",
            max_size=1024 * 1024,
        )


def test_validate_image_upload_rejects_extension_mismatch():
    with pytest.raises(UploadSecurityError, match="扩展名与真实格式不一致"):
        validate_image_upload(
            filename="avatar.png",
            data=_image_bytes("JPEG"),
            max_size=1024 * 1024,
        )


def test_validate_document_upload_accepts_pdf_magic():
    safe = validate_document_upload(
        filename="brief.pdf",
        data=b"%PDF-1.7\n1 0 obj\n<<>>\nendobj\n",
        max_size=1024 * 1024,
    )

    assert safe.content_type == "application/pdf"
    assert safe.ext == ".pdf"


def test_validate_document_upload_rejects_html_text_file():
    with pytest.raises(UploadSecurityError, match="SVG/HTML"):
        validate_document_upload(
            filename="brief.txt",
            data=b"<html><body>not plain text</body></html>",
            max_size=1024 * 1024,
        )


def test_validate_document_upload_rejects_pdf_extension_with_text_body():
    with pytest.raises(UploadSecurityError, match="扩展名与真实类型不一致"):
        validate_document_upload(
            filename="brief.pdf",
            data="这是一段普通文本".encode("utf-8"),
            max_size=1024 * 1024,
        )
