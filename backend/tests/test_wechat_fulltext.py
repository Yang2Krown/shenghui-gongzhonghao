import pytest

from app.services.scraping import wechat_fulltext


@pytest.mark.asyncio
async def test_extract_wechat_article_reuses_creation_extractor(monkeypatch):
    async def fake_extract(url):
        return {
            "title": "腾讯 Marvis",
            "content": "正文内容" * 100,
            "author": "软件科技汇",
            "platform": "gzh",
        }

    monkeypatch.setattr(wechat_fulltext, "extract_link_content", fake_extract)

    result = await wechat_fulltext.extract_wechat_article(
        "https://mp.weixin.qq.com/s/example"
    )

    assert result is not None
    assert result.title == "腾讯 Marvis"
    assert result.author == "软件科技汇"
    assert result.content.startswith("正文内容")


@pytest.mark.asyncio
async def test_extract_wechat_article_rejects_error_text(monkeypatch):
    async def fake_extract(url):
        return {
            "title": "",
            "content": "请求失败，状态码: 403",
            "author": "",
            "platform": "gzh",
        }

    monkeypatch.setattr(wechat_fulltext, "extract_link_content", fake_extract)

    result = await wechat_fulltext.extract_wechat_article(
        "https://mp.weixin.qq.com/s/example"
    )

    assert result is None
