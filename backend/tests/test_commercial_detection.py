import pytest

from app.services.commercial_detection import (
    COMMERCIAL_LEVEL_LIKELY,
    COMMERCIAL_LEVEL_NONE,
    COMMERCIAL_LEVEL_SUSPECTED,
    DETECTION_CONFIG,
    detect_commercial_article,
)
from app.services.commercial_classification import (
    classify_by_rules,
    normalize_commercial_label,
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


@pytest.mark.parametrize("placeholder", ["无法判断", "未识别", "未知", "其他", "unknown"])
def test_commercial_placeholders_are_normalized_to_empty(placeholder):
    assert normalize_commercial_label(placeholder) == ""


@pytest.mark.parametrize(
    ("title", "expected_brand"),
    [
        ("腾讯 Marvis，让操作瞬间丝滑！", "腾讯"),
        ("腾讯首款设计Agent-Miora把网站动效的天捅破了！", "腾讯"),
        ("讯飞星辰 MaaS 平台六折购买 Token", "科大讯飞"),
    ],
)
def test_title_rules_recognize_known_product_owners(title, expected_brand):
    result = classify_by_rules(title=title, content="")
    assert result.brand == expected_brand


def test_commercial_llm_has_enough_output_budget_for_reasoning_json():
    assert DETECTION_CONFIG["llm"]["max_tokens"] == 2048
