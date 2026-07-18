import json

from app.services import xhs_cli_auth
from app.services.xhs_cli_auth import XhsQrLoginManager


class FakeClient:
    def __init__(self, cookies, request_delay=0):
        self.cookies = cookies
        self.closed = False
        self.code_status = 0

    def login_activate(self):
        return {}

    def create_qr_login(self):
        return {"qr_id": "qr-1", "code": "code-1", "url": "xhs://qr/demo"}

    def check_qr_status(self, qr_id, code):
        return {"codeStatus": self.code_status, "userId": "user-1"}

    def close(self):
        self.closed = True


class FakeNeedVerifyError(Exception):
    def __init__(self, verify_type, verify_uuid):
        self.verify_type = verify_type
        self.verify_uuid = verify_uuid


def fake_components():
    return {
        "client": FakeClient,
        "apply": lambda client, payload: None,
        "build": lambda a1, webid, cookies: {
            "a1": a1,
            "webId": webid,
            "web_session": "new-session",
        },
        "complete": lambda client, qr_id, code, user_id: {"user_id": user_id},
        "generate_a1": lambda: "a1-value",
        "generate_webid": lambda: "webid-value",
        "user_id": lambda payload: payload.get("user_id", ""),
        "verify_error": FakeNeedVerifyError,
    }


def test_qr_login_saves_cookie_only_after_confirmation(tmp_path, monkeypatch):
    monkeypatch.setattr(xhs_cli_auth, "_xhs_components", fake_components)
    cookie_path = tmp_path / "cookies.json"
    manager = XhsQrLoginManager(cookie_path, clock=lambda: 1000)

    started = manager.start()
    assert started["qr_url"] == "xhs://qr/demo"
    assert not cookie_path.exists()

    waiting = manager.poll(started["session_id"])
    assert waiting["status"] == "waiting"

    manager._sessions[started["session_id"]].client.code_status = 2
    completed = manager.poll(started["session_id"])
    assert completed == {"status": "authenticated", "user_id": "user-1"}
    payload = json.loads(cookie_path.read_text())
    assert payload["web_session"] == "new-session"
    assert payload["saved_at"] == 1000
    assert cookie_path.stat().st_mode & 0o777 == 0o600


def test_qr_login_expires_and_closes_client(tmp_path, monkeypatch):
    monkeypatch.setattr(xhs_cli_auth, "_xhs_components", fake_components)
    now = [1000]
    manager = XhsQrLoginManager(tmp_path / "cookies.json", ttl_seconds=10, clock=lambda: now[0])
    started = manager.start()
    client = manager._sessions[started["session_id"]].client
    now[0] = 1011
    assert manager.poll(started["session_id"])["status"] == "expired"
    assert client.closed


def test_qr_captcha_keeps_session_and_returns_safe_verification_url(tmp_path, monkeypatch):
    monkeypatch.setattr(xhs_cli_auth, "_xhs_components", fake_components)
    manager = XhsQrLoginManager(tmp_path / "cookies.json", clock=lambda: 1000)
    started = manager.start()
    session = manager._sessions[started["session_id"]]

    def require_verification(qr_id, code):
        raise FakeNeedVerifyError("124", "verify-uuid")

    session.client.check_qr_status = require_verification
    result = manager.poll(started["session_id"])

    assert result["status"] == "verification_required"
    assert "verifyUuid=verify-uuid" in result["verification_url"]
    assert "verifyType=124" in result["verification_url"]
    assert "verifyBiz=461" in result["verification_url"]
    assert started["session_id"] in manager._sessions
    assert not session.client.closed
