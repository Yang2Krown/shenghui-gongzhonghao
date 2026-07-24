from __future__ import annotations

import json
import os
import secrets
import threading
import time
from pathlib import Path
from urllib.parse import urlencode

from xhs_cli.client import XhsClient
from xhs_cli.commands.auth import normalize_xhs_user_payload
from xhs_cli.cookies import extract_browser_cookies
from xhs_cli.exceptions import NeedVerifyError
from xhs_cli.qr_login import (
    _apply_session_cookies, _build_saved_cookies, _complete_confirmed_session,
    _generate_a1, _generate_webid,
)


QR_NETWORK_ATTEMPTS = 2
QR_REQUEST_TIMEOUT_SECONDS = 15
DEFAULT_COOKIE_PATH = Path.home() / ".xiaohongshu-cli/cookies.json"


def atomic_write_cookies(cookies: dict, cookie_path: Path) -> None:
    """原子写入 cookie 文件，避免采集/登录并发时读到写一半的损坏文件。"""
    cookie_path.parent.mkdir(parents=True, exist_ok=True)
    temp = cookie_path.with_name("." + cookie_path.name + ".tmp")
    temp.write_text(json.dumps({**cookies, "saved_at": time.time()}, ensure_ascii=False, indent=2))
    temp.chmod(0o600)
    os.replace(temp, cookie_path)


def _is_transient_network_error(exc: Exception) -> bool:
    """兼容 httpx 包装异常和 Python SSL/socket 原始异常。"""
    current: BaseException | None = exc
    while current is not None:
        name = type(current).__name__.lower()
        message = str(current).lower()
        if (
            "timeout" in name
            or "network" in name
            or "connecterror" in name
            or "timed out" in message
            or "handshake operation" in message
            or "connection reset" in message
            or "temporary failure" in message
        ):
            return True
        current = current.__cause__ or current.__context__
    return False


def _network_error_message(exc: Exception) -> str:
    if _is_transient_network_error(exc):
        return "连接小红书超时，请检查这台 Mac 的网络或代理后重试"
    return str(exc) or type(exc).__name__


class LocalQrLogin:
    def __init__(self, cookie_path: Path | None = None):
        self.cookie_path = cookie_path or DEFAULT_COOKIE_PATH

    def run(self, on_update, ttl_seconds: int = 240, cancel_event: threading.Event | None = None) -> dict:
        client = None
        qr_data = None
        a1 = webid = ""
        for attempt in range(1, QR_NETWORK_ATTEMPTS + 1):
            a1, webid = _generate_a1(), _generate_webid()
            client = XhsClient(
                {"a1": a1, "webId": webid},
                timeout=QR_REQUEST_TIMEOUT_SECONDS,
                request_delay=0,
                max_retries=1,
            )
            try:
                try:
                    _apply_session_cookies(client, client.login_activate())
                except Exception:
                    pass
                qr_data = client.create_qr_login()
                break
            except Exception as exc:
                client.close()
                client = None
                if attempt >= QR_NETWORK_ATTEMPTS or not _is_transient_network_error(exc):
                    raise RuntimeError(_network_error_message(exc)) from exc
                on_update({
                    "status": "retrying",
                    "message": "网络连接超时，正在重新连接小红书…",
                })
                time.sleep(2)

        if client is None or qr_data is None:
            raise RuntimeError("未能创建小红书登录会话")
        deadline = time.time() + ttl_seconds
        try:
            qr_id, code = str(qr_data["qr_id"]), str(qr_data["code"])
            qr_url = str(qr_data["url"])
            last_waiting_update = time.time()
            on_update({"status": "waiting", "qr_url": qr_url, "expires_in": ttl_seconds})
            while time.time() < deadline:
                if cancel_event and cancel_event.is_set():
                    return {"status": "cancelled", "message": "已切换到新的验证方式"}
                try:
                    status_data = client.check_qr_status(qr_id, code)
                    code_status = int(status_data.get("codeStatus", -1))
                    if code_status == 1:
                        on_update({"status": "scanned", "qr_url": qr_url, "message": "已扫码，请在手机上确认"})
                    elif code_status == 2:
                        user_id = str(status_data.get("userId") or "")
                        if not user_id: raise RuntimeError("扫码确认后未返回用户身份")
                        _complete_confirmed_session(client, qr_id, code, user_id)
                        cookies = _build_saved_cookies(a1, webid, client.cookies)
                        if any(not cookies.get(key) for key in ("a1", "webId", "web_session")):
                            raise RuntimeError("扫码成功但 Cookie 不完整")
                        atomic_write_cookies(cookies, self.cookie_path)
                        return {
                            "status": "authenticated",
                            "user_id": user_id,
                            "message": "登录成功，本地 Cookie 已保存并验证",
                        }
                    elif time.time() - last_waiting_update >= 10:
                        last_waiting_update = time.time()
                        on_update({
                            "status": "waiting",
                            "qr_url": qr_url,
                            "expires_in": max(0, int(deadline - time.time())),
                        })
                except NeedVerifyError as exc:
                    query = urlencode({"redirectPath": "https://www.xiaohongshu.com/explore", "verifyUuid": exc.verify_uuid, "verifyType": exc.verify_type, "verifyBiz": "461"})
                    on_update({"status": "verification_required", "message": "请完成人机验证", "verification_url": f"https://www.xiaohongshu.com/website-login/captcha?{query}"})
                except Exception as exc:
                    if not _is_transient_network_error(exc):
                        raise
                    on_update({"status": "retrying", "message": "网络短暂超时，正在继续检查扫码状态…"})
                time.sleep(2)
            return {"status": "expired", "message": "二维码已过期"}
        finally:
            client.close()


class LocalBrowserLogin:
    """Refresh the CLI session from a browser already logged in to XHS."""

    def __init__(self, cookie_path: Path | None = None):
        self.cookie_path = cookie_path or DEFAULT_COOKIE_PATH

    def run(self, on_update) -> dict:
        on_update({
            "status": "syncing_browser",
            "message": "正在从本机浏览器读取小红书登录状态…",
        })
        try:
            # 纯读浏览器（不写盘），再由我们用原子写入盘，避免与采集并发写坏文件。
            result = extract_browser_cookies("auto")
            if not result:
                raise RuntimeError("浏览器中的小红书登录已失效")
            browser, cookies = result
            cookies = dict(cookies)
            cookies.pop("saved_at", None)
            atomic_write_cookies(cookies, self.cookie_path)
            with XhsClient(cookies, timeout=QR_REQUEST_TIMEOUT_SECONDS, request_delay=0, max_retries=1) as client:
                user = normalize_xhs_user_payload(client.get_self_info())
            if user.get("guest"):
                raise RuntimeError("浏览器中的小红书登录已失效")
            return {
                "status": "authenticated",
                "user_id": str(user.get("id") or ""),
                "source": f"browser:{browser}",
                "message": f"已从 {browser} 同步 Cookie",
            }
        except Exception as exc:
            raise RuntimeError(
                "未能从浏览器同步 Cookie。请先在 Chrome/Safari 打开小红书并完成登录或人机验证，"
                "再重试；若 macOS 询问钥匙串权限，请选择允许。"
            ) from exc
