import pytest

from app.models.source_registry import SourceAccount
from app.services.scraping.adapters.dajiala_wechat_adapter import (
    API_BASE,
    HISTORY_BY_GHID_ENDPOINT,
    DajialaWechatAdapter,
    _history_by_ghid_items,
    _history_by_ghid_payload,
)


class FakeResponse:
    def __init__(self, payload, status_code=200):
        self.payload = payload
        self.status_code = status_code

    def json(self):
        return self.payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


class FakeClient:
    def __init__(self, responses):
        self.responses = iter(responses)
        self.posts = []

    async def post(self, url, json, headers):
        self.posts.append((url, json, headers))
        return next(self.responses)


def make_account():
    account = SourceAccount(display_name="测试公众号", handle=None, enabled=True)
    account.id = 83
    account.wechat_reference_url = "https://mp.weixin.qq.com/s/known-article"
    account.wechat_ghid = None
    return account


def history_response():
    return {
        "code": 0,
        "AccountInfo": {"UserName": "gh_test123", "NickName": "测试公众号"},
        "MsgList": {
            "Msg": [
                {
                    "BaseInfo": {"DateTime": 1720000000},
                    "AppMsg": {
                        "BaseInfo": {"AppMsgId": 123},
                        "DetailInfo": [
                            {
                                "Title": "最新商单文章",
                                "Digest": "摘要",
                                "ContentUrl": "https://mp.weixin.qq.com/s/new-article",
                                "CoverImgUrl": "https://example.com/cover.jpg",
                                "ItemIndex": 1,
                                "IsOriginal": 1,
                                "send_time": 1720000000,
                            }
                        ],
                    },
                }
            ]
        },
        "PagingInfo": {"Offset": "next-offset", "IsEnd": 0},
    }


def test_history_by_ghid_payload_uses_reference_url_and_provider_auth(monkeypatch):
    account = make_account()
    monkeypatch.setattr("app.services.scraping.adapters.dajiala_wechat_adapter._api_key", lambda: "api-key")
    monkeypatch.setattr("app.services.scraping.adapters.dajiala_wechat_adapter._verifycode", lambda: "verify")

    payload = _history_by_ghid_payload(account)

    assert payload == {
        "ghid": "",
        "url": "https://mp.weixin.qq.com/s/known-article",
        "nickname": "测试公众号",
        "offset": "",
        "key": "api-key",
        "verifycode": "verify",
    }


def test_history_by_ghid_items_parse_msg_list():
    account = make_account()

    items = _history_by_ghid_items(history_response(), account)

    assert len(items) == 1
    assert items[0].title == "最新商单文章"
    assert items[0].url.endswith("new-article")
    assert items[0].extras["endpoint"] == HISTORY_BY_GHID_ENDPOINT
    assert items[0].extras["history_by_ghid"] is True


@pytest.mark.asyncio
async def test_condition_error_falls_back_once_and_remembers_ghid(monkeypatch):
    account = make_account()
    monkeypatch.setattr("app.services.scraping.adapters.dajiala_wechat_adapter._api_key", lambda: "api-key")
    monkeypatch.setattr("app.services.scraping.adapters.dajiala_wechat_adapter._verifycode", lambda: "verify")
    client = FakeClient([
        FakeResponse({"code": 500, "msg": "接口暂时无法使用"}),
        FakeResponse(history_response()),
    ])

    items = await DajialaWechatAdapter()._post_account(
        client,
        "sogou_wechat_cases",
        "post_condition",
        account,
        page=None,
    )

    assert len(items) == 1
    assert [post[0] for post in client.posts] == [
        f"{API_BASE}/post_condition",
        f"{API_BASE}/{HISTORY_BY_GHID_ENDPOINT}",
    ]
    assert client.posts[1][1]["url"] == account.wechat_reference_url
    assert account.wechat_ghid == "gh_test123"
