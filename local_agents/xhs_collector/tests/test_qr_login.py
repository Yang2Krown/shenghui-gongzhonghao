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
