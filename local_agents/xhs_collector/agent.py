from __future__ import annotations

import argparse
import asyncio
import getpass
import json
import os
import platform
import random
import socket
import subprocess
import sys
import threading
import uuid
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx
import websockets

from client import ServerClient
from collector import RiskBlocked, XhsCollector
from normalizer import normalize, unwrap
from qr_login import LocalBrowserLogin, LocalQrLogin
from scheduling import build_daily_plan, build_two_wave_plan, recover_interrupted_slots, select_daily_keywords, slot_due, slot_expired
from storage import LocalStore

VERSION = "0.6.1"
PLAN_STRATEGY = "all_day_base30_plus_summary_v7"
LEGACY_PLAN_STRATEGY = PLAN_STRATEGY
RISK_COOLDOWN_MINUTES = (8, 12)
SERVICE = "com.midonghub.gzh.xhs-collector"
APP_DIR = Path.home() / "Library/Application Support/GzhXhsCollector"
CONFIG_PATH = APP_DIR / "config.json"
DB_PATH = APP_DIR / "agent.sqlite3"


def keychain_get() -> str:
    result = subprocess.run(["security", "find-generic-password", "-a", getpass.getuser(), "-s", SERVICE, "-w"], capture_output=True, text=True)
    if result.returncode: raise RuntimeError("本地采集节点尚未绑定")
    return result.stdout.strip()


def keychain_set(token: str) -> None:
    subprocess.run(["security", "add-generic-password", "-U", "-a", getpass.getuser(), "-s", SERVICE, "-w", token], check=True, capture_output=True)


def load_config() -> dict[str, Any]:
    if not CONFIG_PATH.is_file(): raise RuntimeError("缺少本地 Agent 配置，请先执行绑定")
    return json.loads(CONFIG_PATH.read_text())


def save_config(value: dict[str, Any]) -> None:
    APP_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(json.dumps(value, ensure_ascii=False, indent=2))
    CONFIG_PATH.chmod(0o600)


class CollectorAgent:
    def __init__(self):
        self.config = load_config()
        self.token = keychain_get()
        self.server = ServerClient(self.config["server_url"], self.token)
        self.store = LocalStore(DB_PATH)
        self.collector = XhsCollector(Path(__file__).resolve().parent)
        self.commands: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        self.auth_cancel = threading.Event()
        self.collection_lock = asyncio.Lock()
        self.paused = asyncio.Event()
        saved_plan = self.today_plan()
        if not saved_plan or not saved_plan.get("paused"):
            self.paused.set()
        self.stop_requested = asyncio.Event()
        self.running_keyword: str | None = None
        cookie_default = "valid" if (Path.home() / ".xiaohongshu-cli/cookies.json").is_file() else "missing"
        self.cookie_status = self.store.get("cookie_status", cookie_default)

    def today_plan(self) -> dict[str, Any] | None:
        plan = self.store.get("daily_plan")
        return plan if isinstance(plan, dict) and plan.get("date") == date.today().isoformat() else None

    def save_plan(self, plan: dict[str, Any]) -> None:
        self.store.set("daily_plan", plan)

    async def report_status(self, status: str | None = None, last_error: str | None = None) -> None:
        plan = self.today_plan()
        default_status = (
            "running" if self.running_keyword else
            "risk_blocked" if self.cookie_status == "verification_required" else
            "paused" if plan and plan.get("paused") else "idle"
        )
        payload = {
            "status": status or default_status,
            "cookie_status": self.cookie_status,
            "current_keyword": self.running_keyword,
            "last_error": last_error,
            "agent_version": VERSION,
            "daily_plan": plan,
        }
        try:
            await asyncio.to_thread(self.server.heartbeat, payload)
        except Exception as exc:
            print(f"[heartbeat] {type(exc).__name__}: {exc}", file=sys.stderr, flush=True)

    async def upload_pending(self) -> None:
        for row_id, endpoint, payload in self.store.pending():
            try:
                await asyncio.to_thread(self.server.request, "POST", endpoint, payload)
                self.store.uploaded(row_id)
            except Exception:
                self.store.failed_attempt(row_id)
                break

    async def safe_upload(self, batch_id: str, payload: dict[str, Any]) -> None:
        endpoint = f"/api/v1/xhs-agent/batches/{batch_id}/results"
        try:
            await asyncio.to_thread(self.server.upload, batch_id, payload)
        except Exception:
            self.store.enqueue(endpoint, payload)

    async def safe_progress(self, batch_id: str, payload: dict[str, Any]) -> None:
        try:
            await asyncio.to_thread(self.server.progress, batch_id, payload)
        except Exception as exc:
            print(f"[progress] {type(exc).__name__}: {exc}", file=sys.stderr, flush=True)

    async def interruptible_gap(self, seconds: float) -> None:
        deadline = asyncio.get_running_loop().time() + seconds
        while asyncio.get_running_loop().time() < deadline:
            if self.stop_requested.is_set(): return
            await self.paused.wait()
            await asyncio.sleep(min(5, deadline - asyncio.get_running_loop().time()))

    async def run_batch(self, keywords: list[dict[str, Any]], mode: str, command_id: str | None = None) -> dict[str, Any]:
        async with self.collection_lock:
            return await self._run_batch(keywords, mode, command_id)

    async def _run_batch(self, keywords: list[dict[str, Any]], mode: str, command_id: str | None = None) -> dict[str, Any]:
        if not keywords: return {"completed": 0, "failed": 0}
        self.stop_requested.clear()
        wave = str(keywords[0].get("wave") or "manual")
        attempt = int(keywords[0].get("attempt") or 1)
        identity = f"{keywords[0]['id']}-{wave}-a{attempt}" if mode == "scheduled" else command_id or uuid.uuid4().hex[:12]
        local_key = f"{date.today().isoformat()}-{mode}-{identity}"
        body = {
            "local_batch_key": local_key, "mode": mode, "schedule_date": date.today().isoformat(),
            "schedule_group": keywords[0].get("group") if mode == "scheduled" else None,
            "wave": wave, "total_keywords": len(keywords), "command_id": command_id,
        }
        batch_id = (await asyncio.to_thread(self.server.create_batch, body))["batch_id"]
        completed = failed = 0
        last_error = None
        try:
            for index, keyword in enumerate(keywords):
                if self.stop_requested.is_set(): break
                await self.paused.wait()
                self.running_keyword = keyword["keyword"]
                await self.safe_progress(batch_id, {"status": "running", "current_keyword_id": keyword["id"], "completed_keywords": completed, "failed_keywords": failed})
                try:
                    collection = await asyncio.to_thread(self.collector.collect_keyword, keyword["keyword"])
                    notes = collection.get("notes") if isinstance(collection, dict) else collection
                    diagnostics = collection.get("diagnostics") if isinstance(collection, dict) else None
                    payload = {"keyword_id": keyword["id"], "idempotency_key": f"{local_key}:{keyword['id']}", "status": "success", "notes": notes or [], "diagnostics": diagnostics or {}}
                    await self.safe_upload(batch_id, payload)
                    completed += 1
                    self.cookie_status = "valid"
                    self.store.set("cookie_status", self.cookie_status)
                except RiskBlocked as exc:
                    failed += 1
                    self.cookie_status = "verification_required"
                    self.store.set("cookie_status", self.cookie_status)
                    self.store.set(
                        "risk_cooldown_until",
                        (datetime.now() + timedelta(minutes=random.randint(*RISK_COOLDOWN_MINUTES))).isoformat(timespec="minutes"),
                    )
                    self.store.set("verification_url", exc.verification_url)
                    self.paused.clear()
                    await self.safe_upload(batch_id, {"keyword_id": keyword["id"], "idempotency_key": f"{local_key}:{keyword['id']}", "status": "risk_blocked", "error": str(exc), "notes": []})
                    await self.safe_progress(batch_id, {"status": "risk_blocked", "current_keyword_id": keyword["id"], "completed_keywords": completed, "failed_keywords": failed, "error": str(exc)})
                    await self.report_status("risk_blocked", str(exc))
                    self.notify_verification()
                    return {"completed": completed, "failed": failed, "risk_blocked": True, "verification_url": exc.verification_url}
                except Exception as exc:
                    failed += 1
                    last_error = f"{type(exc).__name__}: {str(exc)[:500]}"
                    await self.safe_upload(batch_id, {"keyword_id": keyword["id"], "idempotency_key": f"{local_key}:{keyword['id']}", "status": "failed", "error": str(exc), "notes": []})
            status_value = "stopped" if self.stop_requested.is_set() else "completed" if not failed else "partial"
            await self.safe_progress(batch_id, {"status": status_value, "current_keyword_id": None, "completed_keywords": completed, "failed_keywords": failed})
            return {"completed": completed, "failed": failed, "error": last_error}
        finally:
            self.running_keyword = None

    def notify_verification(self) -> None:
        """Notify locally without opening a generic XHS page that cannot clear the challenge."""
        try:
            subprocess.run(["osascript", "-e", 'display notification "请回到采集监测页打开人机验证链接" with title "小红书采集已暂停"'], check=False, capture_output=True)
        except OSError:
            pass

    def requeue_risk_slots(self, plan: dict[str, Any]) -> int:
        stored_resume = self.store.get("risk_cooldown_until")
        resume_at = datetime.fromisoformat(stored_resume) if stored_resume else datetime.now() + timedelta(minutes=random.randint(*RISK_COOLDOWN_MINUTES))
        count = 0
        for slot in plan.get("slots", []):
            if slot.get("status") != "risk_blocked": continue
            slot["status"] = "pending"; slot["attempt"] = int(slot.get("attempt") or 1) + 1
            slot["scheduled_at"] = resume_at.isoformat(timespec="minutes")
            remaining = max(1, int((resume_at - datetime.now()).total_seconds() / 60) + 1)
            slot["reason"] = f"验证完成，约 {remaining} 分钟后自动续跑"
            count += 1
        plan["paused"] = bool(count); plan["pause_reason"] = "risk_cooldown" if count else None
        plan["risk_blocked"] = False
        plan["resume_after"] = resume_at.isoformat(timespec="minutes") if count else None
        return count

    async def handle_command(self, command: dict[str, Any]) -> None:
        command_id = command["id"]
        command_type = command["command_type"]
        if command_type in {"test_keyword", "refresh_image"} and self.collection_lock.locked():
            await asyncio.to_thread(self.server.command_status, command_id, {"status": "failed", "error": "本地采集节点正在执行其他批次，请等待或先停止"})
            return
        await asyncio.to_thread(self.server.command_status, command_id, {"status": "running"})
        try:
            if command_type == "pause":
                self.paused.clear()
                plan = self.today_plan()
                if plan:
                    plan["paused"] = True
                    self.save_plan(plan)
                result = {"paused": True}
                await self.report_status("paused")
            elif command_type == "resume":
                if self.cookie_status != "valid":
                    raise RuntimeError("请先完成小红书扫码或人机验证，再继续今日计划")
                plan = self.today_plan()
                if plan:
                    if plan.get("risk_blocked"):
                        self.requeue_risk_slots(plan)
                    resume_after = datetime.fromisoformat(plan["resume_after"]) if plan.get("resume_after") else None
                    if resume_after and datetime.now() < resume_after:
                        remaining = max(1, int((resume_after - datetime.now()).total_seconds() / 60) + 1)
                        self.paused.clear()
                        self.save_plan(plan)
                        raise RuntimeError(f"刚触发过风控，需要再冷却约 {remaining} 分钟；到时会自动续跑")
                    plan["paused"] = False
                    plan["pause_reason"] = None
                    self.save_plan(plan)
                self.paused.set()
                result = {"paused": False}
                await self.report_status()
            elif command_type == "stop":
                self.stop_requested.set(); self.paused.set()
                plan = self.today_plan()
                if plan:
                    plan["stopped"] = True
                    plan["stop_reason"] = "manual"
                    plan["paused"] = False
                    for slot in plan.get("slots", []):
                        if slot.get("status") == "pending": slot["status"] = "stopped"
                    self.save_plan(plan)
                cancelled = 0
                while not self.commands.empty():
                    queued = self.commands.get_nowait()
                    await asyncio.to_thread(self.server.command_status, queued["id"], {"status": "cancelled", "error": "已由停止命令取消"})
                    cancelled += 1
                result = {"stopping": True, "cancelled_commands": cancelled}
            elif command_type == "test_keyword":
                payload = command.get("payload") or {}
                result = await self.run_batch([{"id": payload["keyword_id"], "keyword": payload["keyword"], "group": None}], "test", command_id)
                plan = self.today_plan()
                if plan:
                    slot = next((item for item in plan.get("slots", []) if int(item.get("keyword_id") or 0) == int(payload["keyword_id"]) and item.get("status") == "failed"), None)
                    if slot and result.get("completed") and not result.get("failed"):
                        slot["status"] = "completed"
                        slot["finished_at"] = datetime.now().isoformat(timespec="seconds")
                        slot["reason"] = "前端应急重试成功"
                        slot.pop("error", None)
                        self.save_plan(plan)
                        await self.report_status()
                    elif slot and result.get("failed"):
                        slot["error"] = f"应急重试失败：{result.get('error') or 'CLI 未完成采集'}"
                        self.save_plan(plan)
                        await self.report_status(last_error=slot["error"])
            elif command_type == "refresh_image":
                payload = command.get("payload") or {}
                note_id = str(payload.get("note_id") or "")
                url = str(payload.get("url") or "")
                if not note_id or not url:
                    raise RuntimeError("封面刷新参数不完整")
                response = await asyncio.to_thread(self.collector._run_cli, "read", url)
                rows = unwrap(response)
                raw = rows[0] if rows else response
                item = normalize(raw, 1) if isinstance(raw, dict) else None
                if not item or item.get("note_id") != note_id or not item.get("cover_url"):
                    raise RuntimeError("小红书未返回新的封面图")
                result = {
                    "note_id": note_id,
                    "cover_url": item["cover_url"],
                    "avatar_url": (item.get("author") or {}).get("avatar_url"),
                }
            elif command_type in {"login", "browser_login", "verify_session"}:
                def update_login(value):
                    self.server.command_status(command_id, {"status": "running", "result": value})
                self.auth_cancel.clear()
                if command_type == "verify_session":
                    try:
                        await asyncio.to_thread(self.collector._run_cli, "status", timeout_seconds=30)
                        result = {"status": "authenticated", "source": "captcha", "message": "人机验证已通过，当前 Cookie 继续使用"}
                    except RiskBlocked as exc:
                        result = {
                            "status": "verification_required",
                            "message": "小红书仍要求完成人机验证",
                            "verification_url": exc.verification_url,
                        }
                        if not self.store.get("risk_cooldown_until"):
                            self.store.set(
                                "risk_cooldown_until",
                                (datetime.now() + timedelta(minutes=random.randint(*RISK_COOLDOWN_MINUTES))).isoformat(timespec="minutes"),
                            )
                        self.store.set("verification_url", exc.verification_url)
                        plan = self.today_plan()
                        if plan:
                            plan["verification_url"] = exc.verification_url
                            plan["risk_blocked"] = True
                            plan["paused"] = True
                            plan["pause_reason"] = "human_verification"
                            self.save_plan(plan)
                        await self.report_status("risk_blocked", str(exc))
                elif command_type == "browser_login":
                    result = await asyncio.to_thread(LocalBrowserLogin().run, update_login)
                else:
                    result = await asyncio.to_thread(LocalQrLogin().run, update_login, 240, self.auth_cancel)
                if result.get("status") == "verification_required":
                    pass
                elif result.get("status") != "authenticated":
                    raise RuntimeError(result.get("message") or "本地扫码登录失败")
                else:
                    self.cookie_status = "valid"
                    self.store.set("cookie_status", self.cookie_status)
                    plan = self.today_plan()
                    if plan:
                        self.requeue_risk_slots(plan)
                        stored_resume = self.store.get("risk_cooldown_until")
                        resume_after = datetime.fromisoformat(stored_resume) if stored_resume else None
                        if resume_after and datetime.now() < resume_after:
                            plan["paused"] = True
                            plan["pause_reason"] = "risk_cooldown"
                            plan["risk_blocked"] = False
                            plan["resume_after"] = resume_after.isoformat(timespec="minutes")
                        plan["verification_url"] = None
                        self.save_plan(plan)
                    self.store.set("verification_url", None)
                    if plan and plan.get("pause_reason") == "risk_cooldown":
                        self.paused.clear()
                    else:
                        self.paused.set()
                    await self.report_status("paused" if plan and plan.get("paused") else "idle")
            else: raise RuntimeError("未知命令")
            await asyncio.to_thread(self.server.command_status, command_id, {"status": "succeeded", "result": result})
        except Exception as exc:
            await asyncio.to_thread(self.server.command_status, command_id, {"status": "failed", "error": str(exc)})

    async def command_worker(self) -> None:
        while True:
            await self.handle_command(await self.commands.get())

    async def scheduler(self) -> None:
        manifest = None
        manifest_date = None
        while True:
            try:
                today_key = date.today().isoformat()
                if manifest is None or manifest_date != today_key:
                    manifest = await asyncio.to_thread(self.server.manifest)
                    manifest_date = today_key
                schedule = manifest.get("schedule") or {}
                now = datetime.now()
                plan = self.today_plan()
                two_wave_enabled = schedule.get("strategy") == "two_waves"
                desired_strategy = "two_waves_legacy_v5" if two_wave_enabled else PLAN_STRATEGY
                if plan is None or plan.get("strategy") != desired_strategy:
                    keywords = select_daily_keywords(
                        date.today(), manifest["keywords"], int(schedule.get("daily_derived_limit") or 5),
                    )
                    morning = str(schedule.get("morning_start") or schedule.get("window_start") or "00:30")
                    afternoon = str(schedule.get("afternoon_start") or "14:20")
                    slots = build_two_wave_plan(date.today(), keywords, morning, afternoon, int(schedule.get("priority_keyword_limit") or 4)) if two_wave_enabled else build_daily_plan(date.today(),keywords,str(schedule.get("window_start") or "00:30"),str(schedule.get("window_end") or "23:30"),int(schedule.get("jitter_minutes") or 8))
                    for slot in slots:
                        keyword = next((item for item in keywords if int(item["id"]) == slot["keyword_id"]), None)
                        completed = bool(keyword and (slot.get("wave") in (keyword.get("completed_waves") or []) if two_wave_enabled else keyword.get("completed_today")))
                        if keyword and completed:
                            slot["status"] = "completed"
                            slot["reason"] = "本波已通过其他任务完成"
                    plan = {
                        "date": today_key, "strategy": desired_strategy,
                        "morning_start": morning, "afternoon_start": afternoon,
                        "window_start": str(schedule.get("window_start") or "00:30"),
                        "window_end": str(schedule.get("window_end") or "23:30"),
                        "base_count": sum(item.get("type") == "base" for item in keywords),
                        "derived_count": sum(item.get("type") == "derived" for item in keywords),
                        "paused": False, "stopped": False,
                        "slots": slots,
                    }
                    self.save_plan(plan)
                    await self.report_status()

                # A scheduler iteration cannot coexist with its own scheduled
                # collection. Therefore a persisted running slot seen here was
                # interrupted by an exception or an Agent restart.
                if recover_interrupted_slots(plan, now):
                    self.save_plan(plan)
                    await self.report_status(last_error="检测到未正常收尾的采集任务，已自动标记失败")

                if self.cookie_status == "verification_required" and not plan.get("paused"):
                    plan["risk_blocked"] = True
                    plan["paused"] = True
                    plan["pause_reason"] = "human_verification"
                    self.paused.clear()
                    self.save_plan(plan)
                    await self.report_status("risk_blocked")

                expired=0
                for slot in plan.get("slots",[]):
                    if slot.get("status")=="pending" and slot_expired(now,slot["scheduled_at"]):
                        slot["status"]="skipped";slot["finished_at"]=now.isoformat(timespec="seconds");slot["reason"]="Mac 休眠或错过执行窗口，不集中补跑"
                        expired+=1
                if expired:
                    self.save_plan(plan);await self.report_status()

                resume_after = datetime.fromisoformat(plan["resume_after"]) if plan.get("resume_after") else None
                if (
                    plan.get("paused") and plan.get("pause_reason") == "risk_cooldown"
                    and resume_after and now >= resume_after and self.cookie_status == "valid"
                ):
                    plan["paused"] = False
                    plan["pause_reason"] = None
                    plan["resume_after"] = None
                    self.store.set("risk_cooldown_until", None)
                    self.paused.set()
                    self.save_plan(plan)
                    await self.report_status()

                if schedule.get("enabled", True) and self.paused.is_set() and not plan.get("paused") and not plan.get("stopped") and self.cookie_status == "valid":
                    due = next((slot for slot in plan.get("slots", []) if slot.get("status") == "pending" and slot_due(now,slot["scheduled_at"])), None)
                    if due and not self.collection_lock.locked():
                        due["status"] = "running"
                        due["started_at"] = datetime.now().isoformat(timespec="seconds")
                        self.save_plan(plan)
                        await self.report_status("running")
                        result = None
                        try:
                            result = await self.run_batch([{"id": due["keyword_id"], "keyword": due["keyword"], "group": due.get("group"), "wave": due.get("wave"), "attempt": due.get("attempt", 1)}], "scheduled")
                        except Exception as exc:
                            due["status"] = "failed"
                            due["finished_at"] = datetime.now().isoformat(timespec="seconds")
                            due["error"] = f"采集异常：{type(exc).__name__}: {str(exc)[:300]}"
                            self.save_plan(plan)
                            await self.report_status(last_error=due["error"])
                        if result and result.get("risk_blocked"):
                            due["status"] = "risk_blocked"
                            plan["risk_blocked"] = True
                            plan["paused"] = True
                            plan["pause_reason"] = "human_verification"
                            plan["risk_blocked_at"] = datetime.now().isoformat(timespec="seconds")
                            plan["verification_url"] = result.get("verification_url")
                        elif result and result.get("failed"):
                            due["status"] = "failed"
                        elif result:
                            due["status"] = "completed"
                        if result:
                            due["finished_at"] = datetime.now().isoformat(timespec="seconds")
                            self.save_plan(plan)
                            await self.report_status("risk_blocked" if result.get("risk_blocked") else None)
            except Exception as exc:
                print(f"[scheduler] {type(exc).__name__}: {exc}", file=sys.stderr, flush=True)
            await asyncio.sleep(60)

    async def heartbeat(self) -> None:
        while True:
            await self.report_status()
            await self.upload_pending()
            await asyncio.sleep(300)

    async def websocket(self) -> None:
        base = self.config["server_url"].rstrip("/")
        uri = ("wss://" + base[8:] if base.startswith("https://") else "ws://" + base[7:] if base.startswith("http://") else base) + "/api/v1/xhs-agent/ws"
        while True:
            try:
                async with websockets.connect(uri, additional_headers={"Authorization": f"Bearer {self.token}"}, ping_interval=30, ping_timeout=30) as connection:
                    async for raw in connection:
                        message = json.loads(raw)
                        if message.get("type") == "command":
                            command = message["command"]
                            if command.get("command_type") in {"pause", "resume", "stop"}:
                                asyncio.create_task(self.handle_command(command))
                            else:
                                if command.get("command_type") in {"login", "browser_login", "verify_session"}:
                                    self.auth_cancel.set()
                                await self.commands.put(command)
            except Exception as exc:
                print(f"[websocket] {type(exc).__name__}: {exc}", file=sys.stderr, flush=True)
                await asyncio.sleep(10)

    async def run(self) -> None:
        await asyncio.gather(self.websocket(), self.command_worker(), self.scheduler(), self.heartbeat())


def pair(server_url: str, code: str, name: str) -> None:
    response = httpx.post(
        server_url.rstrip("/") + "/api/v1/xhs-agent/pair",
        json={"code": code, "name": name, "agent_version": VERSION, "platform": "macos"}, timeout=30,
    )
    response.raise_for_status()
    payload = response.json()
    keychain_set(payload["device_token"])
    save_config({"server_url": server_url.rstrip("/"), "device_id": payload["device_id"], "name": name})
    store = LocalStore(DB_PATH)
    store.set("cookie_status", "valid" if (Path.home() / ".xiaohongshu-cli/cookies.json").is_file() else "missing")
    print(f"绑定成功：{name}")


def main() -> None:
    parser = argparse.ArgumentParser(description="公众号智能体小红书本地采集节点")
    sub = parser.add_subparsers(dest="command", required=True)
    pair_parser = sub.add_parser("pair")
    pair_parser.add_argument("--server", default="https://gzh.midonghub.com")
    pair_parser.add_argument("--code", required=True)
    pair_parser.add_argument("--name", default=f"{socket.gethostname()} · {platform.machine()}")
    sub.add_parser("run")
    args = parser.parse_args()
    if args.command == "pair": pair(args.server, args.code, args.name)
    else: asyncio.run(CollectorAgent().run())


if __name__ == "__main__":
    main()
