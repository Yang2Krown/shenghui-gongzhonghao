"""微信链接解析 + 正文抽取的离线自检（不连网、不连库、不调 LLM）。

运行：cd backend && .venv/bin/python -m tests.test_wechat_link_resolve

守的是最易碎的两段正则逻辑：
  1. 搜狗中转链 /link?url= → 真实 mp 链（JS 分段拼接 + 去防爬的 @）
  2. mp 文章 HTML → 正文纯文本（太短判没抓到）
  3. resolve_wechat_permalink 的三态：永久链不抓页 / 临时链抓正文 / 已过期兜底
"""

import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class _FakeResp:
    def __init__(self, text, url):
        self.text = text
        self.url = url


class _FakeClient:
    def __init__(self, resp):
        self._r = resp

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    async def get(self, url, headers=None):
        return self._r


async def test_sogou_link_to_wechat():
    from app.services.scraping.adapters.sogou_wechat_adapter import _sogou_link_to_wechat

    # JS 分段拼接 + 掺 @ 防爬（含无空格的 url+=）
    html = ("<script>url += 'http://mp.we@ixin.qq.com';"
            "url += '/s?src=11@&timestamp=1';url+='&signature=abc';</script>")
    r = await _sogou_link_to_wechat("https://weixin.sogou.com/link?url=xyz", _FakeClient(_FakeResp(html, "https://weixin.sogou.com/link?url=xyz")))
    assert r == "http://mp.weixin.qq.com/s?src=11&timestamp=1&signature=abc", r

    # 直接 302 到 mp 文章页
    r2 = await _sogou_link_to_wechat("https://weixin.sogou.com/link?url=xyz", _FakeClient(_FakeResp("<html/>", "https://mp.weixin.qq.com/s/AbC123")))
    assert r2 == "https://mp.weixin.qq.com/s/AbC123", r2

    # 非搜狗链原样返回
    r3 = await _sogou_link_to_wechat("https://mp.weixin.qq.com/s/Keep", _FakeClient(_FakeResp("", "")))
    assert r3 == "https://mp.weixin.qq.com/s/Keep", r3

    # 解析失败兜底保原链
    bad = "https://weixin.sogou.com/link?url=bad"
    r4 = await _sogou_link_to_wechat(bad, _FakeClient(_FakeResp("no url here", bad)))
    assert r4 == bad, r4
    print("✅ _sogou_link_to_wechat 4 用例")


async def test_extract_body():
    from app.services.scraping.adapters.exa_wechat_adapter import _extract_wechat_article_body

    long_html = '<div id="js_content"><p>' + ("微信公众号正文内容，足够长。" * 20) + "</p></div><div class=\"rich_media_tool\"></div>"
    body = _extract_wechat_article_body(long_html)
    assert body and len(body) >= 100, body
    # 太短（多半只剩 meta）→ None
    assert _extract_wechat_article_body('<div id="js_content"><p>短</p></div><script>') is None
    print("✅ _extract_wechat_article_body 长抽到/短判 None")


async def test_resolve_permalink():
    import app.services.scraping.adapters.exa_wechat_adapter as exa
    from app.services.scraping.adapters.exa_wechat_adapter import resolve_wechat_permalink

    def patch(resp):
        exa.httpx.AsyncClient = lambda *a, **k: _FakeClient(resp)

    # 永久链：不抓页面，content=None
    u, c = await resolve_wechat_permalink("https://mp.weixin.qq.com/s/AbC")
    assert (u, c) == ("https://mp.weixin.qq.com/s/AbC", None), (u, c)

    # 临时链 + 302 落地永久链 + 正文页：永久链 + 抽到正文
    art = ('<div id="js_content"><p>' + ("正文段落很长。" * 30) + "</p></div><div class=\"rich_media_tool\">")
    patch(_FakeResp(art, "https://mp.weixin.qq.com/s/Final123"))
    u, c = await resolve_wechat_permalink("https://mp.weixin.qq.com/s?src=11&timestamp=1&signature=sig")
    assert u == "https://mp.weixin.qq.com/s/Final123", u
    assert c and len(c) >= 100, c

    # 临时链已过期：content=None，保留原链
    patch(_FakeResp("页面已过期，请重新打开", "https://mp.weixin.qq.com/s?signature=sig"))
    orig = "https://mp.weixin.qq.com/s?src=11&signature=sig"
    u, c = await resolve_wechat_permalink(orig)
    assert u == orig and c is None, (u, c)
    print("✅ resolve_wechat_permalink 永久链不抓/临时链抓正文/过期兜底")


async def main():
    await test_sogou_link_to_wechat()
    await test_extract_body()
    await test_resolve_permalink()
    print("\n所有微信链接解析自检通过 ✅")


if __name__ == "__main__":
    asyncio.run(main())
