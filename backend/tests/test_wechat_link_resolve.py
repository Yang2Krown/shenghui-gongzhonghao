"""微信链接解析 + 正文抽取的离线自检（不连网、不连库、不调 LLM）。

运行：cd backend && .venv/bin/python -m tests.test_wechat_link_resolve

守住公众号临时链接的处理边界：
  1. 仅临时微信链 / 搜狗中转链调用极致了转链 API
  2. 永久链不发请求
  3. API 失败时保留原链接，不抓取公众号 HTML
"""

import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class _FakeResp:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError("unexpected HTTP status")


class _FakeClient:
    def __init__(self, responses):
        self._responses = iter(responses)
        self.posts = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    async def post(self, url, json):
        self.posts.append((url, json))
        return next(self._responses)


async def test_resolve_permalink():
    import app.services.scraping.adapters.exa_wechat_adapter as exa
    from app.services.scraping.adapters.exa_wechat_adapter import resolve_wechat_permalink

    original_client = exa.httpx.AsyncClient
    original_key = exa.settings.DAJIALA_API_KEY
    exa.settings.DAJIALA_API_KEY = "test-key"

    fake_client = _FakeClient([_FakeResp({
        "code": 0,
        "data": {"permanent_link": "https://mp.weixin.qq.com/s?__biz=abc&mid=1&idx=1&sn=xyz"},
    })])
    exa.httpx.AsyncClient = lambda *a, **k: fake_client

    # 永久链：不调用转链 API。
    u, c, _ = await resolve_wechat_permalink("https://mp.weixin.qq.com/s/AbC")
    assert (u, c) == ("https://mp.weixin.qq.com/s/AbC", None), (u, c)
    assert not fake_client.posts

    # 临时签名链：只调用极致了 API，直接存 API 返回的永久链。
    u, c, _ = await resolve_wechat_permalink("https://mp.weixin.qq.com/s?src=11&timestamp=1&signature=sig")
    assert u == "https://mp.weixin.qq.com/s?__biz=abc&mid=1&idx=1&sn=xyz", u
    assert c is None
    assert fake_client.posts[0][1]["url"].startswith("https://mp.weixin.qq.com/s?src=11")

    # API 明确失败：保留原链。
    exa.httpx.AsyncClient = lambda *a, **k: _FakeClient([_FakeResp({"code": 104, "msg": "文章已删除"})])
    orig = "https://mp.weixin.qq.com/s?src=11&signature=sig"
    u, c, _ = await resolve_wechat_permalink(orig)
    assert u == orig and c is None, (u, c)
    exa.httpx.AsyncClient = original_client
    exa.settings.DAJIALA_API_KEY = original_key
    print("✅ 极致了转永久链、永久链跳过、失败保留原链")


async def main():
    await test_resolve_permalink()
    print("\n所有微信链接解析自检通过 ✅")


if __name__ == "__main__":
    asyncio.run(main())
