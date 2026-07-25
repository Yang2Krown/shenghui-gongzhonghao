"""强化版小红书免费抓取 extract_xhs 的单元测试

覆盖：视频笔记封面、note.tagList 标签、发布时间兜底、风控/登录墙识别、
og: meta 兜底补缺失字段、传输层错误轻量重试、全局并发闸门（fail-open / 拥塞失败 / 正常释放）。
"""

import json

import httpx
import pytest

from app.services.scraping import link_extractor
from app.services.scraping.link_extractor import extract_xhs

URL = "https://www.xiaohongshu.com/explore/abc123"


@pytest.fixture(autouse=True)
def _disable_xhs_gate(monkeypatch):
    """默认让并发闸门走 fail-open（redis 不可用），既有用例不依赖真实 redis、也不引入 jitter 等待。
    需要测闸门本身的用例在测试内重新 monkeypatch aioredis.from_url 覆盖本 fixture。"""
    def _raise(*args, **kwargs):
        raise ConnectionError("test: no redis")

    monkeypatch.setattr(link_extractor.aioredis, "from_url", _raise)


# ============================================================
# Fixtures：HTML / INITIAL_STATE 构造
# ============================================================

def _state_html(state: dict, head: str = "") -> str:
    """把 INITIAL_STATE 包进 script 标签，模拟笔记页"""
    payload = json.dumps(state, ensure_ascii=False)
    return (
        f"<html><head>{head}</head><body>"
        f"<script>{link_extractor.INITIAL_STATE_PREFIX}{payload};</script>"
        f"</body></html>"
    )


def _note_state(note: dict) -> dict:
    return {"note": {"noteDetailMap": {"abc123": {"note": note}}}}


IMAGE_NOTE = {
    "noteId": "abc123",
    "type": "normal",
    "title": "图文标题",
    "desc": "图文正文内容",
    "time": 1753000000000,
    "user": {"userId": "u1", "nickname": "作者甲", "desc": "作者简介", "image": "https://img/avatar.jpg"},
    "tagList": [{"id": "t1", "name": "穿搭", "type": "topic"}, {"id": "t2", "name": "通勤", "type": "topic"}],
    "interactInfo": {
        "likedCount": 1200, "collectedCount": 300, "commentCount": 45, "shareCount": 12,
        "tagList": [{"name": "错误位置"}],
    },
    "imageList": [{"urlDefault": "https://img/cover1.jpg", "url": "https://img/cover1_fallback.jpg"}],
}

VIDEO_NOTE = {
    "noteId": "vid001",
    "type": "video",
    "title": "视频标题",
    "desc": "视频正文内容",
    "lastUpdateTime": 1753100000000,
    "user": {"userId": "u2", "nickname": "作者乙"},
    "tagList": [{"id": "t3", "name": "vlog", "type": "topic"}],
    "interactInfo": {"likedCount": 99},
    "video": {"cover": {"urlDefault": "https://img/video_cover.jpg"}},
}

BLOCKED_HTML = (
    "<html><head><title>安全验证</title></head><body>"
    "<div>访问异常，错误码 300031，请拖动下方滑块完成验证</div>"
    "</body></html>"
)

OG_ONLY_HTML = (
    "<html><head>"
    '<meta name="description" content="og 正文描述"/>'
    '<meta property="og:title" content="普通笔记标题"/>'
    '<meta property="og:image" content="https://img/og_cover.jpg"/>'
    "<title>普通笔记标题 - 小红书</title>"
    "</head><body></body></html>"
)


def _mock_fetch_html(monkeypatch, html: str):
    async def fake_fetch_html(url, cookie=None, ua=None, referer=None):
        return html

    monkeypatch.setattr(link_extractor, "fetch_html", fake_fetch_html)


def _http_status_error(status: int) -> httpx.HTTPStatusError:
    request = httpx.Request("GET", URL)
    response = httpx.Response(status, request=request)
    return httpx.HTTPStatusError(f"status {status}", request=request, response=response)


# ============================================================
# 图文笔记：完整 INITIAL_STATE
# ============================================================

async def test_image_note_full_state(monkeypatch):
    _mock_fetch_html(monkeypatch, _state_html(_note_state(IMAGE_NOTE)))

    result = await extract_xhs(URL)

    assert result["note_id"] == "abc123"
    assert result["title"] == "图文标题"
    assert result["content"] == "图文正文内容"
    assert result["author"] == "作者甲"
    # tags 必须来自 note.tagList，而不是 interactInfo.tagList
    assert result["tags"] == ["穿搭", "通勤"]
    assert result["published_at"] == 1753000000000
    assert result["note_type"] == "image"
    assert result["cover_url"] == "https://img/cover1.jpg"
    assert result["like_count"] == 1200
    assert "blocked" not in result


async def test_tags_fall_back_to_interact_info(monkeypatch):
    note = {**IMAGE_NOTE, "tagList": []}
    _mock_fetch_html(monkeypatch, _state_html(_note_state(note)))

    result = await extract_xhs(URL)

    assert result["tags"] == ["错误位置"]


# ============================================================
# 视频笔记：封面在 note.video 下
# ============================================================

async def test_video_note_cover_from_video_cover(monkeypatch):
    _mock_fetch_html(monkeypatch, _state_html(_note_state(VIDEO_NOTE)))

    result = await extract_xhs(URL)

    assert result["note_type"] == "video"
    assert result["cover_url"] == "https://img/video_cover.jpg"


async def test_video_note_cover_snake_case_first_frame(monkeypatch):
    note = {
        **VIDEO_NOTE,
        "video": {"first_frame": {"url_default": "https://img/first_frame.jpg"}},
    }
    _mock_fetch_html(monkeypatch, _state_html(_note_state(note)))

    result = await extract_xhs(URL)

    assert result["cover_url"] == "https://img/first_frame.jpg"


async def test_video_note_cover_origin_cover_camel_case(monkeypatch):
    note = {
        **VIDEO_NOTE,
        "video": {"originCover": {"url": "https://img/origin_cover.jpg"}},
    }
    _mock_fetch_html(monkeypatch, _state_html(_note_state(note)))

    result = await extract_xhs(URL)

    assert result["cover_url"] == "https://img/origin_cover.jpg"


# ============================================================
# 发布时间兜底
# ============================================================

async def test_published_at_falls_back_to_last_update_time(monkeypatch):
    _mock_fetch_html(monkeypatch, _state_html(_note_state(VIDEO_NOTE)))

    result = await extract_xhs(URL)

    assert result["published_at"] == 1753100000000


# ============================================================
# og: meta 兜底：只补缺失字段，不覆盖已解析值
# ============================================================

async def test_og_image_fills_missing_cover(monkeypatch):
    note = {k: v for k, v in IMAGE_NOTE.items() if k != "imageList"}
    head = (
        '<meta name="description" content="og 描述"/>'
        '<meta property="og:title" content="og 标题"/>'
        '<meta property="og:image" content="https://img/og_cover.jpg"/>'
    )
    _mock_fetch_html(monkeypatch, _state_html(_note_state(note), head=head))

    result = await extract_xhs(URL)

    # 缺失的 cover_url 由 og:image 补齐
    assert result["cover_url"] == "https://img/og_cover.jpg"
    # 已解析的 title 不被 og:title 覆盖
    assert result["title"] == "图文标题"


async def test_og_only_page_fallback(monkeypatch):
    """有的页面没有 INITIAL_STATE 但 og: meta 齐全，走正常正则兜底"""
    _mock_fetch_html(monkeypatch, OG_ONLY_HTML)

    result = await extract_xhs(URL)

    assert result["title"] == "普通笔记标题"
    assert result["cover_url"] == "https://img/og_cover.jpg"
    assert "blocked" not in result


# ============================================================
# 风控/登录墙识别
# ============================================================

async def test_blocked_page_returns_blocked(monkeypatch):
    _mock_fetch_html(monkeypatch, BLOCKED_HTML)

    result = await extract_xhs(URL)

    assert result["blocked"] is True
    assert result["platform"] == "xhs"
    assert result["title"] == ""
    assert result["content"] == ""
    assert result["author"] == ""
    assert result["tags"] == []
    assert not result["cover_url"]


async def test_login_wall_redirect_returns_blocked(monkeypatch):
    html = (
        '<html><head></head><body>'
        '<script>window.location.replace("/login?redirectUrl=https%3A%2F%2Fwww.xiaohongshu.com");</script>'
        "</body></html>"
    )
    _mock_fetch_html(monkeypatch, html)

    result = await extract_xhs(URL)

    assert result["blocked"] is True
    assert result["content"] == ""


async def test_blocked_status_code_returns_blocked(monkeypatch):
    for status in (461, 471, 403):
        calls = 0

        async def fake_fetch_html(url, cookie=None, ua=None, referer=None):
            nonlocal calls
            calls += 1
            raise _http_status_error(status)

        monkeypatch.setattr(link_extractor, "fetch_html", fake_fetch_html)

        result = await extract_xhs(URL)

        assert result["blocked"] is True, f"status={status}"
        assert result["title"] == ""
        assert result["content"] == ""
        assert calls == 1, f"status={status} 不应重试"
        monkeypatch.undo()


# ============================================================
# 轻量重试
# ============================================================

async def test_transport_error_retried_once(monkeypatch):
    monkeypatch.setattr(link_extractor.random, "uniform", lambda a, b: 0)
    calls = 0

    async def fake_fetch_html(url, cookie=None, ua=None, referer=None):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise httpx.ConnectError("connection refused")
        return _state_html(_note_state(IMAGE_NOTE))

    monkeypatch.setattr(link_extractor, "fetch_html", fake_fetch_html)

    result = await extract_xhs(URL)

    assert calls == 2
    assert result["title"] == "图文标题"


async def test_transport_error_gives_up_after_one_retry(monkeypatch):
    monkeypatch.setattr(link_extractor.random, "uniform", lambda a, b: 0)
    calls = 0

    async def fake_fetch_html(url, cookie=None, ua=None, referer=None):
        nonlocal calls
        calls += 1
        raise httpx.ReadTimeout("read timeout")

    monkeypatch.setattr(link_extractor, "fetch_html", fake_fetch_html)

    result = await extract_xhs(URL)

    assert calls == 2
    assert result["content"].startswith("提取失败")
    assert "blocked" not in result


async def test_http_status_error_not_retried(monkeypatch):
    calls = 0

    async def fake_fetch_html(url, cookie=None, ua=None, referer=None):
        nonlocal calls
        calls += 1
        raise _http_status_error(404)

    monkeypatch.setattr(link_extractor, "fetch_html", fake_fetch_html)

    result = await extract_xhs(URL)

    assert calls == 1
    assert result["content"].startswith("请求失败")
    assert "blocked" not in result


# ============================================================
# 全局并发闸门
# ============================================================

class _FakeLock:
    """内存版 redis lock，模拟槽位锁"""

    def __init__(self, acquire_ok: bool = True):
        self._acquire_ok = acquire_ok
        self.acquired = False
        self.released = False

    async def acquire(self, blocking=False):
        if self._acquire_ok:
            self.acquired = True
        return self._acquire_ok

    async def owned(self):
        return self.acquired and not self.released

    async def release(self):
        self.released = True


class _FakeRedis:
    """内存版 redis.asyncio 客户端，只实现闸门用到的方法"""

    def __init__(self, acquire_ok: bool = True):
        self._acquire_ok = acquire_ok
        self.locks = []
        self.closed = False

    def lock(self, name, timeout=None, blocking=False):
        lock = _FakeLock(self._acquire_ok)
        self.locks.append(lock)
        return lock

    async def aclose(self):
        self.closed = True


async def test_gate_congestion_returns_failure_dict(monkeypatch):
    """槽位始终被占：等满 XHS_HTML_GATE_WAIT_SECONDS 返回失败 dict，且不调用 fetch_html"""
    fake_redis = _FakeRedis(acquire_ok=False)
    monkeypatch.setattr(link_extractor.aioredis, "from_url", lambda *a, **kw: fake_redis)
    monkeypatch.setattr(link_extractor.settings, "XHS_HTML_GATE_WAIT_SECONDS", 0.01)

    fetch_calls = 0

    async def fake_fetch_html(url, cookie=None, ua=None, referer=None):
        nonlocal fetch_calls
        fetch_calls += 1
        return _state_html(_note_state(IMAGE_NOTE))

    monkeypatch.setattr(link_extractor, "fetch_html", fake_fetch_html)

    result = await extract_xhs(URL)

    assert fetch_calls == 0
    assert result["content"].startswith("提取失败")
    assert "blocked" not in result
    assert fake_redis.closed is True


async def test_gate_redis_failure_fails_open(monkeypatch):
    """redis.from_url 抛异常：fail-open 正常抓取"""
    def _raise(*args, **kwargs):
        raise ConnectionError("redis down")

    monkeypatch.setattr(link_extractor.aioredis, "from_url", _raise)
    _mock_fetch_html(monkeypatch, _state_html(_note_state(IMAGE_NOTE)))

    result = await extract_xhs(URL)

    assert result["title"] == "图文标题"
    assert "blocked" not in result


async def test_gate_releases_lock_on_success(monkeypatch):
    """正常路径拿到锁后 release，并关闭 redis 连接"""
    fake_redis = _FakeRedis(acquire_ok=True)
    monkeypatch.setattr(link_extractor.aioredis, "from_url", lambda *a, **kw: fake_redis)
    # 跳过拿槽位后的 jitter 等待
    monkeypatch.setattr(link_extractor.random, "uniform", lambda a, b: 0)
    _mock_fetch_html(monkeypatch, _state_html(_note_state(IMAGE_NOTE)))

    result = await extract_xhs(URL)

    assert result["title"] == "图文标题"
    assert len(fake_redis.locks) == 1
    assert fake_redis.locks[0].released is True
    assert fake_redis.closed is True
