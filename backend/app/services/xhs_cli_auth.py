"""服务器端小红书 CLI 扫码授权。

二维码会话只保存在当前 web 进程内，Cookie 仅写入受限私密文件，
不返回前端、不写入数据库或日志。
"""
from __future__ import annotations

import json
import os
import secrets
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlencode


QR_WAITING = 0
QR_SCANNED = 1
QR_CONFIRMED = 2


def _xhs_components():
    """延迟导入：本地旧虚拟环境可以运行非集成测试，生产镜像按 requirements 安装 CLI。"""
    from xhs_cli.client import XhsClient
    from xhs_cli.exceptions import NeedVerifyError
    from xhs_cli.qr_login import (
        _apply_session_cookies,
        _build_saved_cookies,
        _complete_confirmed_session,
        _generate_a1,
        _generate_webid,
        _resolved_user_id,
    )
    return {
        "client": XhsClient,
        "apply": _apply_session_cookies,
        "build": _build_saved_cookies,
        "complete": _complete_confirmed_session,
        "generate_a1": _generate_a1,
        "generate_webid": _generate_webid,
        "user_id": _resolved_user_id,
        "verify_error": NeedVerifyError,
    }


@dataclass
class QrLoginSession:
    session_id: str
    client: Any
    qr_id: str
    code: str
    qr_url: str
    a1: str
    webid: str
    expires_at: float
    state: str = "waiting"


class XhsQrLoginManager:
    def __init__(
        self,
        cookie_path: str | Path,
        *,
        ttl_seconds: int = 240,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self.cookie_path = Path(cookie_path)
        self.ttl_seconds = ttl_seconds
        self.clock = clock
        self._sessions: dict[str, QrLoginSession] = {}
        self._lock = threading.RLock()

    @staticmethod
    def _close(session: QrLoginSession) -> None:
        try:
            session.client.close()
        except Exception:
            pass

    def _purge(self) -> None:
        now = self.clock()
        for session_id, session in list(self._sessions.items()):
            if session.expires_at <= now:
                self._close(session)
                self._sessions.pop(session_id, None)

    def start(self) -> dict[str, Any]:
        with self._lock:
            self._purge()
            for session in self._sessions.values():
                self._close(session)
            self._sessions.clear()

            parts = _xhs_components()
            a1 = parts["generate_a1"]()
            webid = parts["generate_webid"]()
            client = parts["client"]({"a1": a1, "webId": webid}, request_delay=0)
            try:
                try:
                    activate_data = client.login_activate()
                    parts["apply"](client, activate_data)
                except Exception:
                    # activate 是容错预热，CLI 官方实现也允许它失败后继续创建二维码。
                    pass
                qr_data = client.create_qr_login()
                qr_id = str(qr_data["qr_id"])
                code = str(qr_data["code"])
                qr_url = str(qr_data["url"])
            except Exception:
                client.close()
                raise

            session_id = secrets.token_urlsafe(24)
            expires_at = self.clock() + self.ttl_seconds
            self._sessions[session_id] = QrLoginSession(
                session_id=session_id,
                client=client,
                qr_id=qr_id,
                code=code,
                qr_url=qr_url,
                a1=a1,
                webid=webid,
                expires_at=expires_at,
            )
            return {
                "session_id": session_id,
                "qr_url": qr_url,
                "status": "waiting",
                "expires_in": self.ttl_seconds,
            }

    def _save_cookies(self, cookies: dict[str, str]) -> None:
        required = ("a1", "webId", "web_session")
        if any(not cookies.get(key) for key in required):
            raise RuntimeError("扫码成功，但小红书返回的 Cookie 不完整")
        self.cookie_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {**cookies, "saved_at": self.clock()}
        temp = self.cookie_path.with_name(f".{self.cookie_path.name}.{secrets.token_hex(6)}.tmp")
        try:
            temp.write_text(json.dumps(payload, ensure_ascii=False, indent=2))
            temp.chmod(0o600)
            os.replace(temp, self.cookie_path)
            self.cookie_path.chmod(0o600)
        finally:
            if temp.exists():
                temp.unlink()

    def poll(self, session_id: str) -> dict[str, Any]:
        with self._lock:
            self._purge()
            session = self._sessions.get(session_id)
            if not session:
                return {"status": "expired", "message": "二维码已过期，请重新获取"}

            try:
                parts = _xhs_components()
                status_data = session.client.check_qr_status(session.qr_id, session.code)
                code_status = int(status_data.get("codeStatus", -1))
                if code_status == QR_SCANNED:
                    session.state = "scanned"
                    return {"status": "scanned", "message": "已扫码，请在小红书中确认登录"}
                if code_status != QR_CONFIRMED:
                    return {
                        "status": "waiting",
                        "expires_in": max(0, int(session.expires_at - self.clock())),
                    }

                confirmed_user_id = str(status_data.get("userId") or "")
                if not confirmed_user_id:
                    raise RuntimeError("小红书已确认扫码，但未返回用户身份")
                completion = parts["complete"](
                    session.client,
                    session.qr_id,
                    session.code,
                    confirmed_user_id,
                )
                cookies = parts["build"](session.a1, session.webid, session.client.cookies)
                self._save_cookies(cookies)
                user_id = parts["user_id"](completion) or confirmed_user_id
                self._close(session)
                self._sessions.pop(session_id, None)
                return {"status": "authenticated", "user_id": user_id}
            except parts["verify_error"] as exc:
                session.state = "verification_required"
                query = urlencode({
                    "redirectPath": "https://www.xiaohongshu.com/explore",
                    "verifyUuid": exc.verify_uuid,
                    "verifyType": exc.verify_type,
                    "verifyBiz": "461",
                })
                return {
                    "status": "verification_required",
                    "message": "小红书要求进行人机验证，完成后请继续检查登录状态",
                    "verification_url": f"https://www.xiaohongshu.com/website-login/captcha?{query}",
                    "expires_in": max(0, int(session.expires_at - self.clock())),
                }
            except Exception as exc:
                self._close(session)
                self._sessions.pop(session_id, None)
                return {"status": "failed", "message": str(exc)[:500] or type(exc).__name__}

    def cancel(self, session_id: str) -> bool:
        with self._lock:
            session = self._sessions.pop(session_id, None)
            if not session:
                return False
            self._close(session)
            return True
