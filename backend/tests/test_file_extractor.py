"""extract_text 真实解析回归测试。

覆盖 2026-07-31 文件上传审计发现的边界:
- 扫描版/空白 PDF 文本层为空 → 走 qwen-vl OCR 兜底(此处 mock,不真打 API)
- 带表格 DOCX 的段落+单元格
- UTF-8 / GBK 中文 TXT
- 空文件 → 空串(由路由层转 400,不在此处)
- 老版 .doc → 明确 UnsupportedFileType

OCR 相关用例 mock _extract_image_via_vision,保证离线可跑、不烧 token。
"""
import io

import pytest
from pypdf import PdfWriter
from docx import Document
from PIL import Image

from app.utils import file_extractor
from app.utils.file_extractor import (
    UnsupportedFileType,
    extract_text,
    extract_text_from_path,
    normalize_extracted_text,
)


def _blank_pdf() -> bytes:
    w = PdfWriter()
    w.add_blank_page(width=612, height=792)
    buf = io.BytesIO()
    w.write(buf)
    return buf.getvalue()


def _short_text_pdf() -> bytes:
    import fitz

    document = fitz.open()
    page = document.new_page()
    page.insert_text((72, 72), "short PDF text")
    return document.tobytes()


def _table_docx() -> bytes:
    d = Document()
    d.add_paragraph("产品:测试面霜")
    t = d.add_table(rows=1, cols=2)
    t.cell(0, 0).text = "必须提及"
    t.cell(0, 1).text = "烟酰胺"
    buf = io.BytesIO()
    d.save(buf)
    return buf.getvalue()


def _png_bytes() -> bytes:
    img = Image.new("RGB", (40, 40), (255, 255, 255))
    b = io.BytesIO()
    img.save(b, "PNG")
    return b.getvalue()


# ── 文档类(不走 OCR,纯本地解析)────────────────────────

async def test_docx_extracts_paragraphs_and_table_cells():
    text = await extract_text(filename="brief.docx", data=_table_docx())
    assert "测试面霜" in text
    assert "必须提及" in text and "烟酰胺" in text  # 表格单元格也要被提到


async def test_docx_path_extracts_text_without_loading_media_parts(tmp_path):
    path = tmp_path / "brief.docx"
    path.write_bytes(_table_docx())

    text = await extract_text_from_path(filename=path.name, path=path)

    assert "测试面霜" in text
    assert "必须提及" in text and "烟酰胺" in text


async def test_txt_utf8_and_gbk():
    utf8 = await extract_text(filename="b.txt", data="商单要求口语化。".encode("utf-8"))
    assert "口语化" in utf8
    gbk = await extract_text(filename="b.txt", data="GBK编码的内容。".encode("gbk"))
    assert "编码" in gbk


def test_normalize_extracted_text_splits_pdf_control_noise():
    assert normalize_extracted_text("1.0\x01AI短剧正文。") == "1.0\nAI短剧正文。"


def test_normalize_extracted_text_preserves_chinese_punctuation():
    source = "上传的经验正文：先写冲突，再给案例。"

    assert normalize_extracted_text(source) == source


def test_normalize_extracted_text_reflows_pdf_soft_line_breaks():
    source = (
        "事情是这样的。\n\n"
        "组会前一晚，导师突然问我：最近\n"
        "latent\n"
        "VLA\n"
        "这个方向有没有新论文？能不能快速整理一份综述，明\n"
        "天做个\n"
        "PPT\n"
        "讲一下？"
    )

    text = normalize_extracted_text(source)

    assert "事情是这样的。\n\n组会前一晚" in text
    assert "最近 latent VLA 这个方向" in text
    assert "明天做个 PPT 讲一下？" in text


def test_normalize_extracted_text_reflows_mid_sentence_and_heading_breaks():
    source = (
        "三、我用\n"
        "latent VLA\n"
        "跑了一遍科研全流程\n\n"
        "第一步，检索文献\n\n"
        "我直接把 latent VLA\n"
        "这个方向交给磐石，让它检索 2024\n"
        "年以来的代表工作，并继续核对论文题目、发\n"
        "布时间、代码、数据集和原始来源。"
    )

    text = normalize_extracted_text(source)

    assert "三、我用 latent VLA 跑了一遍科研全流程" in text
    assert "第一步，检索文献" in text
    assert (
        "我直接把 latent VLA 这个方向交给磐石，让它检索 2024 年以来的代表工作，"
        "并继续核对论文题目、发布时间、代码、数据集和原始来源。"
    ) in text
    assert "全流程\n\n第一步" in text
    assert "检索文献\n\n我直接把" in text


def test_normalize_extracted_text_keeps_short_brand_header_lines():
    source = "中科闻歌\n磐石ScienceOne\n公众号推文-初稿"

    assert normalize_extracted_text(source) == source


async def test_old_doc_raises_unsupported():
    with pytest.raises(UnsupportedFileType):
        await extract_text(filename="old.doc", data=b"\xd0\xcf\x11\xe0 fake doc")


async def test_empty_txt_returns_empty_string():
    # 空文本文件解出空串;路由层负责把它转成 400
    text = await extract_text(filename="empty.txt", data=b"")
    assert text == ""


# ── 扫描版 PDF / 图片(走 OCR,这里 mock)────────────────

async def test_scanned_pdf_falls_back_to_ocr(monkeypatch):
    """文本层为空的 PDF 必须走视觉 OCR 兜底,而不是静默返回空。"""
    called = {}

    async def fake_pdf_ocr(data):
        called["hit"] = True
        return "扫描件里的文字"

    monkeypatch.setattr(file_extractor, "_ocr_pdf_via_vision", fake_pdf_ocr)
    text = await extract_text(filename="scan.pdf", data=_blank_pdf())
    assert called.get("hit"), "空白 PDF 未触发 OCR 兜底"
    assert text == "扫描件里的文字"


async def test_scanned_pdf_path_falls_back_without_reading_whole_file(tmp_path, monkeypatch):
    path = tmp_path / "scan.pdf"
    path.write_bytes(_blank_pdf())

    async def fake_path_ocr(received_path):
        assert received_path == path
        return "路径扫描件文字"

    monkeypatch.setattr(file_extractor, "_ocr_pdf_path_via_vision", fake_path_ocr)
    text = await extract_text_from_path(filename=path.name, path=path)
    assert text == "路径扫描件文字"


async def test_short_text_pdf_is_kept_without_ocr(monkeypatch):
    async def fail_if_called(data):
        raise AssertionError("有文本层的短 PDF 不应触发 OCR")

    monkeypatch.setattr(file_extractor, "_ocr_pdf_via_vision", fail_if_called)
    text = await extract_text(filename="short.pdf", data=_short_text_pdf())
    assert "short PDF text" in text


async def test_image_upload_routes_to_vision(monkeypatch):
    async def fake_vision(data, mime):
        return "图片中的文字"

    monkeypatch.setattr(file_extractor, "_extract_image_via_vision", fake_vision)
    text = await extract_text(filename="shot.png", data=_png_bytes(), content_type="image/png")
    assert text == "图片中的文字"


async def test_scanned_pdf_returns_empty_when_no_ocr_key(monkeypatch):
    """没配 OCR key 时兜底返回空串(不抛异常),由路由层转成友好 400。"""
    monkeypatch.setattr(file_extractor, "_vision_api_key", lambda: None)
    text = await extract_text(filename="scan.pdf", data=_blank_pdf())
    assert text == ""
