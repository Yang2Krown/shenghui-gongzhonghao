import threading

import pytest

import qr_login


class FakeClient:
    created = 0

    def __init__(self, cookies, **kwargs):
        type(self).created += 1
        self.instance = type(self).created
        self.cookies = {"web_session": "session"}
        self.closed = False

    def login_activate(self):
        return {}

    def create_qr_login(self):
        if self.instance == 1:
            raise TimeoutError("_ssl.c:999: The handshake operation timed out")
        return {"qr_id": "qr-1", "code": "code-1", "url": "xhs://login"}

    def check_qr_status(self, qr_id, code):
        return {"codeStatus": 2, "userId": "user-1"}

    def close(self):
        self.closed = True


def test_qr_login_retries_ssl_timeout_and_succeeds(tmp_path, monkeypatch):
    FakeClient.created = 0
    updates = []
    monkeypatch.setattr(qr_login, "XhsClient", FakeClient)
    monkeypatch.setattr(qr_login, "_apply_session_cookies", lambda *_: None)
    monkeypatch.setattr(qr_login, "_complete_confirmed_session", lambda *_: None)
    monkeypatch.setattr(
        qr_login,
        "_build_saved_cookies",
        lambda a1, webid, cookies: {"a1": a1, "webId": webid, "web_session": cookies["web_session"]},
    )
    monkeypatch.setattr(qr_login.time, "sleep", lambda *_: None)

    result = qr_login.LocalQrLogin(tmp_path / "cookies.json").run(updates.append)

    assert result == {"status": "authenticated", "user_id": "user-1"}
    assert FakeClient.created == 2
    assert updates[0]["status"] == "retrying"
    assert updates[1]["status"] == "waiting"


def test_qr_login_translates_final_ssl_timeout(tmp_path, monkeypatch):
    class AlwaysTimeoutClient(FakeClient):
        def create_qr_login(self):
            raise TimeoutError("_ssl.c:999: The handshake operation timed out")

    monkeypatch.setattr(qr_login, "XhsClient", AlwaysTimeoutClient)
    monkeypatch.setattr(qr_login.time, "sleep", lambda *_: None)

    with pytest.raises(RuntimeError, match="连接小红书超时"):
        qr_login.LocalQrLogin(tmp_path / "cookies.json").run(lambda *_: None)


def test_qr_login_can_be_cancelled_when_switching_auth_method(tmp_path, monkeypatch):
    class WaitingClient(FakeClient):
        def create_qr_login(self):
            return {"qr_id": "qr-1", "code": "code-1", "url": "xhs://login"}

        def check_qr_status(self, qr_id, code):
            return {"codeStatus": 0}

    cancel = threading.Event()
    cancel.set()
    monkeypatch.setattr(qr_login, "XhsClient", WaitingClient)
    result = qr_login.LocalQrLogin(tmp_path / "cookies.json").run(lambda *_: None, cancel_event=cancel)
    assert result["status"] == "cancelled"


def test_browser_login_refreshes_existing_browser_cookie(monkeypatch):
    class BrowserClient:
        def __init__(self, cookies, **kwargs):
            assert cookies["web_session"] == "browser-session"

        def __enter__(self):
            return self

        def __exit__(self, *_):
            return None

        def get_self_info(self):
            return {"user_id": "user-2"}

    updates = []
    monkeypatch.setattr(qr_login, "get_cookies", lambda *_, **__: ("chrome", {"web_session": "browser-session"}))
    monkeypatch.setattr(qr_login, "XhsClient", BrowserClient)
    monkeypatch.setattr(qr_login, "normalize_xhs_user_payload", lambda _: {"id": "user-2", "guest": False})

    result = qr_login.LocalBrowserLogin().run(updates.append)

    assert result["status"] == "authenticated"
    assert result["source"] == "browser:chrome"
    assert updates[0]["status"] == "syncing_browser"


def test_browser_login_explains_how_to_recover_when_no_cookie(monkeypatch):
    def fail(*_, **__):
        raise RuntimeError("no browser cookie")

    monkeypatch.setattr(qr_login, "get_cookies", fail)
    with pytest.raises(RuntimeError, match="Chrome/Safari"):
        qr_login.LocalBrowserLogin().run(lambda *_: None)
