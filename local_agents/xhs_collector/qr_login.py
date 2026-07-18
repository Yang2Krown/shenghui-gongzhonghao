from __future__ import annotations

import json
import os
import secrets
import time
from pathlib import Path
from urllib.parse import urlencode

from xhs_cli.client import XhsClient
from xhs_cli.exceptions import NeedVerifyError
from xhs_cli.qr_login import (
    _apply_session_cookies, _build_saved_cookies, _complete_confirmed_session,
    _generate_a1, _generate_webid,
)


class LocalQrLogin:
    def __init__(self, cookie_path: Path | None = None):
        self.cookie_path = cookie_path or Path.home() / ".xiaohongshu-cli/cookies.json"

    def run(self, on_update, ttl_seconds: int = 240) -> dict:
        a1, webid = _generate_a1(), _generate_webid()
        client = XhsClient({"a1": a1, "webId": webid}, request_delay=0)
        deadline = time.time() + ttl_seconds
        try:
            try:
                _apply_session_cookies(client, client.login_activate())
            except Exception:
                pass
            qr_data = client.create_qr_login()
            qr_id, code = str(qr_data["qr_id"]), str(qr_data["code"])
            on_update({"status": "waiting", "qr_url": str(qr_data["url"]), "expires_in": ttl_seconds})
            while time.time() < deadline:
                try:
                    status_data = client.check_qr_status(qr_id, code)
                    code_status = int(status_data.get("codeStatus", -1))
                    if code_status == 1:
                        on_update({"status": "scanned", "message": "已扫码，请在手机上确认"})
                    elif code_status == 2:
                        user_id = str(status_data.get("userId") or "")
                        if not user_id: raise RuntimeError("扫码确认后未返回用户身份")
                        _complete_confirmed_session(client, qr_id, code, user_id)
                        cookies = _build_saved_cookies(a1, webid, client.cookies)
                        if any(not cookies.get(key) for key in ("a1", "webId", "web_session")):
                            raise RuntimeError("扫码成功但 Cookie 不完整")
                        self.cookie_path.parent.mkdir(parents=True, exist_ok=True)
                        temp = self.cookie_path.with_name("." + self.cookie_path.name + ".tmp")
                        temp.write_text(json.dumps({**cookies, "saved_at": time.time()}, ensure_ascii=False, indent=2))
                        temp.chmod(0o600); os.replace(temp, self.cookie_path)
                        return {"status": "authenticated", "user_id": user_id}
                except NeedVerifyError as exc:
                    query = urlencode({"redirectPath": "https://www.xiaohongshu.com/explore", "verifyUuid": exc.verify_uuid, "verifyType": exc.verify_type, "verifyBiz": "461"})
                    on_update({"status": "verification_required", "message": "请完成人机验证", "verification_url": f"https://www.xiaohongshu.com/website-login/captcha?{query}"})
                time.sleep(2)
            return {"status": "expired", "message": "二维码已过期"}
        finally:
            client.close()
