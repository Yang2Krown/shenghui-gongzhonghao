import json
import subprocess
from datetime import date, datetime

import pytest

from collector import RiskBlocked, XhsCollector
from normalizer import has_result_list, normalize
from scheduling import build_daily_plan, recover_interrupted_slots, select_daily_keywords, slot_due, slot_expired
from storage import LocalStore


def test_search_card_normalization_keeps_rank_time_and_likes():
    raw = {
        "id": "note-1", "xsec_token": "token=", "model_type": "note",
        "note_card": {
            "type": "normal", "display_title": "标题",
            "corner_tag_info": [{"type": "publish_time", "text": "今天"}],
            "user": {"user_id": "u1", "nick_name": "作者"},
            "interact_info": {"liked_count": "1.2万"},
            "cover": {"url_default": "https://sns-webpic.xhscdn.com/a.jpg"},
        },
    }
    item = normalize(raw, 2)
    assert item["note_id"] == "note-1"
    assert item["provider_rank"] == 2
    assert item["engagement"]["likes"] == 12000
    assert isinstance(item["published_at"], datetime)
    assert "xsec_token=token%3D" in item["original_url"]


def test_local_store_persists_failed_uploads(tmp_path):
    store = LocalStore(tmp_path / "agent.sqlite3")
    store.set("last_scheduled_date", "2026-07-17")
    store.set("cookie_status", "verification_required")
    store.enqueue("/upload", {"note": 1})
    assert store.get("last_scheduled_date") == "2026-07-17"
    assert LocalStore(tmp_path / "agent.sqlite3").get("cookie_status") == "verification_required"
    assert store.pending_count() == 1
    row_id, endpoint, payload = store.pending()[0]
    assert endpoint == "/upload" and payload == {"note": 1}
    store.uploaded(row_id)
    assert store.pending_count() == 0


def test_collector_stops_immediately_on_captcha(tmp_path, monkeypatch):
    payload = {"ok": False, "error": {"code": "verification_required", "message": "Captcha required"}}
    monkeypatch.setattr(subprocess, "run", lambda *args, **kwargs: subprocess.CompletedProcess(args=[], returncode=1, stdout=json.dumps(payload), stderr=""))
    collector = XhsCollector(tmp_path)
    with pytest.raises(RiskBlocked):
        collector.collect_keyword("AI Agent")


def test_empty_result_list_is_distinguished_from_unrecognized_response():
    assert has_result_list({"ok": True, "data": []}) is True
    assert has_result_list({"ok": True, "data": {"items": []}}) is True
    assert has_result_list({"ok": True, "message": "unexpected"}) is False


def test_collector_reports_true_search_zero(tmp_path, monkeypatch):
    collector = XhsCollector(tmp_path)
    monkeypatch.setattr(collector, "_run_cli", lambda *args, **kwargs: {"ok": True, "data": []})
    result = collector.collect_keyword("AI startup")
    assert result["notes"] == []
    assert result["diagnostics"]["search_state"] == "empty"
    assert result["diagnostics"]["search_returned_count"] == 0


def test_collector_preserves_raw_count_when_every_result_is_filtered(tmp_path, monkeypatch):
    collector = XhsCollector(tmp_path)
    search_payload = {"ok": True, "data": [{
        "id": "note-low-like", "model_type": "note",
        "note_card": {
            "display_title": "低赞笔记",
            "corner_tag_info": [{"type": "publish_time", "text": "今天"}],
            "interact_info": {"liked_count": "120"},
        },
    }]}
    monkeypatch.setattr(collector, "_run_cli", lambda *args, **kwargs: search_payload)
    result = collector.collect_keyword("AI startup")
    diagnostics = result["diagnostics"]
    assert result["notes"] == []
    assert diagnostics["search_state"] == "ok"
    assert diagnostics["search_returned_count"] == 1
    assert diagnostics["within_week_count"] == 1
    assert diagnostics["eligible_like_count"] == 0
    assert diagnostics["rejection_counts"]["low_like"] == 1


def test_daily_plan_is_restart_safe_and_spread_across_the_day():
    keywords = [{"id": index, "keyword": f"词{index}", "type": "base", "group": (index % 3) + 1} for index in range(1, 36)]
    first = build_daily_plan(date(2026, 7, 17), keywords)
    second = build_daily_plan(date(2026, 7, 17), list(reversed(keywords)))
    assert first == second
    assert len(first) == 35
    times = [datetime.fromisoformat(item["scheduled_at"]) for item in first]
    assert times[0].hour == 9 and times[-1].hour == 22
    assert min((right - left).total_seconds() for left, right in zip(times, times[1:])) >= 15 * 60


def test_scheduler_never_catches_up_after_grace_window():
    assert slot_due(datetime(2026, 7, 17, 9, 35), "2026-07-17T09:30") is True
    assert slot_due(datetime(2026, 7, 17, 12, 12), "2026-07-17T09:30") is False
    assert slot_expired(datetime(2026, 7, 17, 9, 42), "2026-07-17T09:30") is True


def test_daily_selection_keeps_all_base_and_samples_up_to_five_derived():
    keywords = [
        *[{"id": index, "keyword": f"基础{index}", "type": "base"} for index in range(1, 31)],
        *[{"id": index, "keyword": f"总结{index}", "type": "derived", "eligible": index != 36} for index in range(31, 38)],
    ]
    first = select_daily_keywords(date(2026, 7, 17), keywords)
    second = select_daily_keywords(date(2026, 7, 17), list(reversed(keywords)))
    assert [item["id"] for item in first] == [item["id"] for item in second]
    assert len([item for item in first if item["type"] == "base"]) == 30
    assert len([item for item in first if item["type"] == "derived"]) == 5
    assert all(item["id"] != 36 for item in first)


def test_daily_selection_uses_every_available_derived_when_fewer_than_five():
    keywords = [{"id": 1, "keyword": "基础", "type": "base"}, {"id": 2, "keyword": "总结", "type": "derived", "eligible": True}]
    selected = select_daily_keywords(date(2026, 7, 17), keywords)
    assert [item["id"] for item in selected] == [1, 2]


def test_scheduler_recovers_persisted_running_slot_without_retrying_it():
    plan = {"slots": [
        {"keyword": "AI", "status": "running", "started_at": "2026-07-18T09:30:16"},
        {"keyword": "下一个词", "status": "pending"},
    ]}
    recovered = recover_interrupted_slots(plan, datetime(2026, 7, 18, 10, 8))
    assert recovered == 1
    assert plan["slots"][0]["status"] == "failed"
    assert "未重复采集" in plan["slots"][0]["error"]
    assert plan["slots"][1]["status"] == "pending"
