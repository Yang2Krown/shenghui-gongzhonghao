import pytest

from app.services.commercial_detection import (
    COMMERCIAL_LEVEL_LIKELY,
    COMMERCIAL_LEVEL_NONE,
    COMMERCIAL_LEVEL_SUSPECTED,
    detect_commercial_article,
)


@pytest.mark.asyncio
async def test_detects_code_cta_even_in_short_text():
    result = await detect_commercial_article(
        title="某工具体验",
        content="免费领取 Pro 会员，点击下方链接立即注册，邀请码 ABC123。",
    )

    assert result.level == COMMERCIAL_LEVEL_LIKELY
    assert result.signals["layer"] == "hard_rule"


@pytest.mark.asyncio
async def test_detects_external_url_as_suspected():
    result = await detect_commercial_article(
        title="一次效率工具体验",
        content=(
            "这是一篇正常长度的体验记录，先介绍使用背景和测试方式。"
            "更多信息见 https://example-product.com/signup ，文章后半段继续讨论优缺点。"
            "整体体验有亮点也有局限，适合需要自动化处理的人参考。"
        ),
    )

    assert result.level == COMMERCIAL_LEVEL_SUSPECTED
    assert result.signals["external_url_count"] == 1


@pytest.mark.asyncio
async def test_short_non_commercial_text_is_none():
    result = await detect_commercial_article(
        title="普通新闻",
        content="今天发布了一个新版本。",
    )

    assert result.level == COMMERCIAL_LEVEL_NONE
