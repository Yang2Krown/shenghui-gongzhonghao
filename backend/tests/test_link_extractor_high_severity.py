"""链接提取高危修复的回归测试（审计 wf_894c7211 确认的 6 个 HIGH）

覆盖：
- extract_url_from_text 剥离 URL 尾部中文/全角字符（修 #1）
- _parse_xhs_html 兜底取 og:description 而非 viewport/keywords（修 #2）
- 抖音整体时间预算 wait_for 超时取消（修 #3）
- 知乎登录墙/风控页识别 _zhihu_is_blocked_page（修 #4）
- _extract_via_api 非 HTTPStatusError 异常降级不短路兜底（修 #5）
"""

import asyncio

import pytest

from app.services.scraping import link_extractor
from app.services.scraping.link_extractor import (
    extract_url_from_text,
    _parse_xhs_html,
    _zhihu_is_blocked_page,
    _extract_via_api,
    extract_link_content,
)


# ── #1 URL 尾部中文/全角剥离 ─────────────────────────────
@pytest.mark.parametrize("raw,expected", [
    ("看这个 https://xhslink.com/a/AbC12）", "https://xhslink.com/a/AbC12"),
    ("好物 https://v.douyin.com/iABC12/，快看", "https://v.douyin.com/iABC12/"),
    ("文章 https://mp.weixin.qq.com/s/abc123）", "https://mp.weixin.qq.com/s/abc123"),
    ("https://www.zhihu.com/question/1/answer/2 分享", "https://www.zhihu.com/question/1/answer/2"),
    ("https://example.com/p?a=1&b=2#frag。", "https://example.com/p?a=1&b=2#frag"),
    ("复制 5.43 https://v.douyin.com/iABC12/ 打开", "https://v.douyin.com/iABC12/"),
])
def test_url_tail_chinese_stripped(raw, expected):
    assert extract_url_from_text(raw) == expected


# ── #2 小红书兜底取 og:description 而非 viewport/keywords ──
def test_xhs_fallback_uses_og_description_not_viewport():
    html = (
        '<html><head>'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '<meta name="keywords" content="穿搭,早春">'
        '<meta property="og:description" content="真正的笔记正文">'
        '<title>t - 小红书</title>'
        '</head><body></body></html>'
    )
    r = _parse_xhs_html(html, "https://www.xiaohongshu.com/explore/abc123")
    assert r["content"] == "真正的笔记正文"


# ── #3 抖音整体时间预算超时取消 ──────────────────────────
def test_douyin_timeout_budget(monkeypatch):
    # 预算 monkeypatch 成 0.1s,避免测试真等 45s
    monkeypatch.setattr(link_extractor, "DOUYIN_EXTRACT_BUDGET_SECONDS", 0.1)

    async def slow(url, cookie=None):
        await asyncio.sleep(999)
    monkeypatch.setattr(link_extractor, "extract_douyin", slow)
    r = asyncio.run(extract_link_content("https://v.douyin.com/iABC12/"))
    assert r["platform"] == "douyin"
    assert "超时" in r["content"]


# ── #4 知乎登录墙/风控识别 ───────────────────────────────
@pytest.mark.parametrize("html,blocked", [
    ('<html><body>安全验证，请拖动滑块</body></html>', True),
    ('<html><title>知乎 - 有问题，就会有答案</title></html>', True),
    ('<html><body>请登录后查看</body></html>', True),
    ('<html><body><h1 class="QuestionHeader-title">正常问题</h1></body></html>', False),
])
def test_zhihu_blocked_page_detected(html, blocked):
    assert _zhihu_is_blocked_page(html) is blocked


# ── #5 知乎主路径异常降级不短路兜底 ──────────────────────
def test_zhihu_api_network_error_returns_failure_not_raise(monkeypatch):
    import httpx

    async def boom(*a, **k):
        raise httpx.ConnectError("dns failed")
    # 让 _extract_zhihu_ids 可用,但网络层抛 ConnectError
    monkeypatch.setattr(link_extractor, "_get_with_checked_redirects", boom)
    r = asyncio.run(_extract_via_api("https://www.zhihu.com/question/1/answer/2"))
    # 应返回含"请求失败"的失败结构(供 extract_zhihu 降级),而不是抛异常直达路由 500
    assert "请求失败" in r["content"]
    assert r["platform"] == "zhihu"
