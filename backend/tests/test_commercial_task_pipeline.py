import pytest

from app.services.commercial_detection import CommercialDetectionResult
from app.services.scraping.wechat_fulltext import ExtractedWechatArticle
from app.tasks import commercial_tasks
from app.services.scraping import wechat_fulltext


@pytest.mark.asyncio
async def test_dajiala_detection_hydrates_fulltext_first(monkeypatch):
    raw = {
        "id": 42,
        "title": "腾讯 Marvis，让操作瞬间丝滑！",
        "summary": "",
        "content": "",
        "url": "https://mp.weixin.qq.com/s/example",
        "source_platform": "sogou_wechat_cases",
        "source_type": "dajiala_wechat",
    }
    persisted = {}
    detected = {}

    monkeypatch.setattr(commercial_tasks, "_load_raw_context", lambda raw_id: raw.copy())

    def fake_save_fulltext(raw_id, *, content, author=""):
        persisted.update(raw_id=raw_id, content=content, author=author)

    monkeypatch.setattr(commercial_tasks, "_save_extracted_fulltext", fake_save_fulltext)

    async def fake_extract(url):
        return ExtractedWechatArticle(
            title=raw["title"],
            content="Marvis 是腾讯推出的个人 AI 助手。",
            author="软件科技汇",
        )

    monkeypatch.setattr(wechat_fulltext, "extract_wechat_article", fake_extract)

    async def fake_detect(*, title, summary, content, force_llm):
        detected.update(content=content, force_llm=force_llm)
        return CommercialDetectionResult(
            level="likely",
            brand="腾讯",
            product="Marvis",
            category="办公效率",
        )

    monkeypatch.setattr(commercial_tasks, "detect_commercial_article", fake_detect)
    monkeypatch.setattr(
        commercial_tasks,
        "_save_detection_result",
        lambda raw_id, **kwargs: {"raw_info_id": raw_id, "status": "ok", **kwargs},
    )

    result = await commercial_tasks._detect_one(42)

    assert persisted["content"].startswith("Marvis")
    assert persisted["author"] == "软件科技汇"
    assert detected["content"] == persisted["content"]
    assert detected["force_llm"] is True
    assert result["brand"] == "腾讯"
