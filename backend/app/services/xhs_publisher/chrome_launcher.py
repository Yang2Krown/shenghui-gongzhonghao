"""
Chrome launcher with CDP remote debugging support.
Adapted from post-to-xhs skill with macOS support.
"""

import os
import sys
import time
import socket
import subprocess
import shutil
from typing import Optional

CDP_PORT = 9222
PROFILE_DIR_NAME = "XiaohongshuProfile"
STARTUP_TIMEOUT = 15

_chrome_process: Optional[subprocess.Popen] = None
_current_account: Optional[str] = None


def _find_playwright_chromium() -> Optional[str]:
    """定位 Playwright 安装的 chromium（服务器/容器环境常用）。"""
    import glob
    bases = [
        os.environ.get("PLAYWRIGHT_BROWSERS_PATH", ""),
        os.path.join(os.path.expanduser("~"), ".cache", "ms-playwright"),
        "/ms-playwright",
    ]
    candidates = []
    for base in bases:
        if not base:
            continue
        candidates += glob.glob(os.path.join(base, "chromium-*", "chrome-linux", "chrome"))
        candidates += glob.glob(os.path.join(base, "chromium-*", "chrome-linux", "headless_shell"))
    for path in sorted(candidates, reverse=True):
        if os.path.isfile(path):
            return path
    return None


def get_chrome_path() -> str:
    # 1) 显式环境变量优先（部署时最可靠）
    env_path = os.environ.get("XHS_CHROME_PATH") or os.environ.get("CHROME_PATH")
    if env_path and os.path.isfile(env_path):
        return env_path

    if sys.platform == "darwin":
        mac_path = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
        if os.path.isfile(mac_path):
            return mac_path
    elif sys.platform == "win32":
        for env_var in ("PROGRAMFILES", "PROGRAMFILES(X86)", "LOCALAPPDATA"):
            base = os.environ.get(env_var, "")
            if base:
                path = os.path.join(base, "Google", "Chrome", "Application", "chrome.exe")
                if os.path.isfile(path):
                    return path

    found = (
        shutil.which("chrome")
        or shutil.which("chrome.exe")
        or shutil.which("google-chrome")
        or shutil.which("google-chrome-stable")
        or shutil.which("chromium")
        or shutil.which("chromium-browser")
    )
    if found:
        return found

    # 2) 容器/服务器：回退到 Playwright 安装的 chromium
    pw = _find_playwright_chromium()
    if pw:
        return pw

    raise FileNotFoundError(
        "Chrome not found. 请安装 Google Chrome，或设置环境变量 XHS_CHROME_PATH 指向 "
        "chromium 可执行文件（服务器可用 Playwright 的 chromium）。"
    )


def get_user_data_dir(account: Optional[str] = None) -> str:
    try:
        from app.services.xhs_publisher.account_manager import get_profile_dir
        return get_profile_dir(account)
    except ImportError:
        home = os.path.expanduser("~")
        if sys.platform == "darwin":
            base = os.path.join(home, "Library", "Application Support")
        else:
            base = os.environ.get("LOCALAPPDATA", home)
        return os.path.join(base, "Google", "Chrome", PROFILE_DIR_NAME)


def is_port_open(port: int, host: str = "127.0.0.1") -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(1)
        try:
            s.connect((host, port))
            return True
        except (ConnectionRefusedError, socket.timeout, OSError):
            return False


def launch_chrome(port: int = CDP_PORT, headless: bool = False, account: Optional[str] = None) -> Optional[subprocess.Popen]:
    global _chrome_process, _current_account

    if is_port_open(port):
        print(f"[chrome_launcher] Chrome already running on port {port}.")
        return None

    chrome_path = get_chrome_path()
    user_data_dir = get_user_data_dir(account)
    os.makedirs(user_data_dir, exist_ok=True)
    _current_account = account

    cmd = [
        chrome_path,
        f"--remote-debugging-port={port}",
        f"--user-data-dir={user_data_dir}",
        "--no-first-run",
        "--no-default-browser-check",
    ]

    # 容器/无 root 环境下 Chrome 必需的参数（Linux）
    if sys.platform.startswith("linux"):
        cmd += [
            "--no-sandbox",
            "--disable-dev-shm-usage",
            "--disable-gpu",
            "--remote-debugging-address=127.0.0.1",
        ]

    # headless 可由环境变量强制开启（无显示器的服务器）
    env_headless = os.environ.get("XHS_HEADLESS", "").lower() in ("1", "true", "yes")
    if headless or env_headless:
        cmd.append("--headless=new")
        cmd.append("--window-size=1280,2000")

    mode_label = "headless" if headless else "headed"
    account_label = account or "default"
    print(f"[chrome_launcher] Launching Chrome ({mode_label}, account: {account_label})...")
    print(f"  executable : {chrome_path}")
    print(f"  profile dir: {user_data_dir}")

    proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    _chrome_process = proc

    deadline = time.time() + STARTUP_TIMEOUT
    while time.time() < deadline:
        if is_port_open(port):
            print(f"[chrome_launcher] Chrome is ready on port {port}.")
            return proc
        time.sleep(0.5)

    print(f"[chrome_launcher] WARNING: Chrome started but port {port} not responding after {STARTUP_TIMEOUT}s.", file=sys.stderr)
    return proc


def kill_chrome(port: int = CDP_PORT):
    global _chrome_process

    try:
        import requests
        resp = requests.get(f"http://127.0.0.1:{port}/json/version", timeout=2)
        if resp.ok:
            ws_url = resp.json().get("webSocketDebuggerUrl")
            if ws_url:
                import websockets.sync.client as ws_client
                ws = ws_client.connect(ws_url)
                ws.send('{"id":1,"method":"Browser.close"}')
                try:
                    ws.recv(timeout=2)
                except Exception:
                    pass
                ws.close()
    except Exception:
        pass

    time.sleep(1)

    if _chrome_process and _chrome_process.poll() is None:
        try:
            _chrome_process.terminate()
            _chrome_process.wait(timeout=5)
        except Exception:
            try:
                _chrome_process.kill()
            except Exception:
                pass
    _chrome_process = None

    if sys.platform != "win32" and is_port_open(port):
        try:
            import signal
            result = subprocess.run(["lsof", "-ti", f":{port}"], capture_output=True, text=True, timeout=5)
            for pid in result.stdout.strip().split('\n'):
                if pid.strip():
                    os.kill(int(pid.strip()), signal.SIGTERM)
        except Exception:
            pass

    deadline = time.time() + 5
    while time.time() < deadline:
        if not is_port_open(port):
            return
        time.sleep(0.5)


def restart_chrome(port: int = CDP_PORT, headless: bool = False, account: Optional[str] = None) -> Optional[subprocess.Popen]:
    kill_chrome(port)
    time.sleep(1)
    return launch_chrome(port, headless=headless, account=account)


def ensure_chrome(port: int = CDP_PORT, headless: bool = False, account: Optional[str] = None) -> bool:
    if is_port_open(port):
        return True
    try:
        launch_chrome(port, headless=headless, account=account)
        return is_port_open(port)
    except FileNotFoundError as e:
        print(f"[chrome_launcher] Error: {e}", file=sys.stderr)
        return False
