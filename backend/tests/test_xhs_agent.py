from datetime import date, datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.api.v1 import api_router
from app.api.v1.xhs_agent import COMMAND_TYPES, CommandBody, _secret_hash
from app.db.base import Base
from app.models.xhs import XhsAgentBatch, XhsAgentUpload, XhsCollectorDevice, XhsKeyword, XhsKeywordRun, XhsNote, XhsProviderCall
from app.services import xhs_agent_ingestion as ingestion


def test_agent_routes_and_command_whitelist_are_registered():
    routes = {(route.path, method) for route in api_router.routes for method in getattr(route, "methods", set())}
    assert ("/xhs-agent/pair", "POST") in routes
    assert ("/xhs-agent/manifest", "GET") in routes
    assert ("/xhs-agent/batches/{batch_id}/results", "POST") in routes
    assert ("/admin/xhs-monitoring/agent/pairings", "POST") in routes
    assert ("/admin/xhs-monitoring/agent/commands", "POST") in routes
    assert COMMAND_TYPES == {"test_keyword", "refresh_image", "pause", "resume", "stop", "login"}


def test_agent_secret_hash_is_stable_and_does_not_store_raw_token():
    token = "agent-token-with-enough-entropy-123456789"
    assert _secret_hash(token) == _secret_hash(token)
    assert _secret_hash(token) != token
    assert len(_secret_hash(token)) == 64


def test_manual_agent_command_can_explicitly_request_cooldown_override():
    body=CommandBody(device_id="device-1",command_type="test_keyword",keyword_id=12,force=True)
    assert body.force is True and body.keyword_id==12


def test_agent_ingestion_is_idempotent_and_reuses_material_pipeline(monkeypatch):
    engine = create_engine("sqlite:///:memory:")
    table_names = [
        "source_registry", "raw_infos", "xhs_keywords", "xhs_collector_devices",
        "xhs_agent_commands", "xhs_agent_batches", "xhs_keyword_runs",
        "xhs_agent_uploads", "xhs_notes", "xhs_note_discoveries",
        "xhs_engagement_snapshots", "xhs_provider_calls",
    ]
    Base.metadata.create_all(engine, tables=[Base.metadata.tables[name] for name in table_names])
    factory = sessionmaker(bind=engine, class_=Session, expire_on_commit=False)
    monkeypatch.setattr(ingestion, "SessionLocal", factory)
    with factory() as db:
        keyword = XhsKeyword(keyword="AI Agent", normalized_keyword="ai agent", keyword_type="base", schedule_group=1, enabled=True)
        device = XhsCollectorDevice(name="Test Mac", token_hash="hash", schedule_config={})
        db.add_all([keyword, device]); db.flush()
        batch = XhsAgentBatch(device_id=device.id, local_batch_key="20260717-test", mode="test", status="running", schedule_date=date.today(), total_keywords=1, started_at=datetime.now())
        db.add(batch); db.commit()
        batch_id, device_id, keyword_id = batch.public_id, device.id, keyword.id
    payload = {
        "keyword_id": keyword_id, "idempotency_key": "20260717-test:keyword-1", "status": "success", "error": None,
        "diagnostics": {
            "version": 1, "search_state": "ok", "search_returned_count": 12,
            "normalized_count": 10, "within_week_count": 8, "eligible_like_count": 3,
            "detail_attempted_count": 3, "detail_success_count": 1,
            "rejection_counts": {"old": 2, "low_like": 5},
        },
        "notes": [{
            "note_id": "agent-note-1", "title": "", "content": "正文第一段可作为标题。\n\n正文第二段。",
            "published_at": datetime.now().isoformat(), "note_type": "image",
            "author": {"id": "u1", "nickname": "作者"}, "cover_url": "https://sns-webpic.xhscdn.com/a.jpg",
            "engagement": {"likes": 9000}, "provider_rank": 1,
        }],
    }
    first = ingestion.ingest_agent_result(device_id=device_id, batch_public_id=batch_id, keyword_id=keyword_id, idempotency_key=payload["idempotency_key"], payload=payload)
    second = ingestion.ingest_agent_result(device_id=device_id, batch_public_id=batch_id, keyword_id=keyword_id, idempotency_key=payload["idempotency_key"], payload=payload)
    assert first["accepted"] == 1 and not first["duplicate"]
    assert second["accepted"] == 1 and second["duplicate"]
    with factory() as db:
        note = db.query(XhsNote).one()
        assert note.note_id == "agent-note-1" and note.raw_info_id is not None
        assert note.title == "正文第一段可作为标题。" and note.quality_status == "ready_degraded"
        run = db.query(XhsKeywordRun).one()
        upload = db.query(XhsAgentUpload).one()
        assert (run.cli_raw_count, run.merged_count, run.within_week_count, run.eligible_like_count) == (12, 10, 8, 3)
        assert run.rejection_counts["_search_diagnostics"] == 1
        assert run.rejection_counts["_detail_success"] == 1
        assert upload.raw_count == 12


def test_agent_ingestion_accepts_all_qualified_notes_without_top_ten_cap(monkeypatch):
    engine = create_engine("sqlite:///:memory:")
    table_names = [
        "source_registry", "raw_infos", "xhs_keywords", "xhs_collector_devices",
        "xhs_agent_commands", "xhs_agent_batches", "xhs_keyword_runs",
        "xhs_agent_uploads", "xhs_notes", "xhs_note_discoveries",
        "xhs_engagement_snapshots", "xhs_provider_calls",
    ]
    Base.metadata.create_all(engine, tables=[Base.metadata.tables[name] for name in table_names])
    factory = sessionmaker(bind=engine, class_=Session, expire_on_commit=False)
    monkeypatch.setattr(ingestion, "SessionLocal", factory)
    with factory() as db:
        keyword = XhsKeyword(keyword="AI", normalized_keyword="ai", keyword_type="base", schedule_group=1, enabled=True)
        device = XhsCollectorDevice(name="Test Mac", token_hash="hash", schedule_config={})
        db.add_all([keyword, device]); db.flush()
        batch = XhsAgentBatch(device_id=device.id, local_batch_key="unlimited-test", mode="test", status="running", schedule_date=date.today(), total_keywords=1, started_at=datetime.now())
        db.add(batch); db.commit()
        batch_id, device_id, keyword_id = batch.public_id, device.id, keyword.id

    notes = [{
        "note_id": f"unlimited-{index}", "title": f"标题 {index}", "content": "完整正文",
        "published_at": datetime.now().isoformat(), "note_type": "image",
        "author": {"id": f"u{index}", "nickname": f"作者 {index}"},
        "cover_url": f"https://sns-webpic.xhscdn.com/{index}.jpg",
        "engagement": {"likes": 3000 + index}, "provider_rank": index + 1,
    } for index in range(12)]
    result = ingestion.ingest_agent_result(
        device_id=device_id, batch_public_id=batch_id, keyword_id=keyword_id,
        idempotency_key="unlimited-test:keyword", payload={"status": "success", "notes": notes},
    )
    assert result["accepted"] == 12
    with factory() as db:
        assert db.query(XhsNote).count() == 12
        run = db.query(XhsKeywordRun).one()
        assert run.final_count == 12 and run.displayable_count == 12


def test_agent_ingestion_labels_captcha_as_verification_required(monkeypatch):
    engine = create_engine("sqlite:///:memory:")
    table_names = [
        "source_registry", "raw_infos", "xhs_keywords", "xhs_collector_devices",
        "xhs_agent_commands", "xhs_agent_batches", "xhs_keyword_runs",
        "xhs_agent_uploads", "xhs_notes", "xhs_note_discoveries",
        "xhs_engagement_snapshots", "xhs_provider_calls",
    ]
    Base.metadata.create_all(engine, tables=[Base.metadata.tables[name] for name in table_names])
    factory = sessionmaker(bind=engine, class_=Session, expire_on_commit=False)
    monkeypatch.setattr(ingestion, "SessionLocal", factory)
    with factory() as db:
        keyword = XhsKeyword(keyword="大模型", normalized_keyword="大模型", keyword_type="base", schedule_group=1, enabled=True)
        device = XhsCollectorDevice(name="Test Mac", token_hash="hash", schedule_config={})
        db.add_all([keyword, device]); db.flush()
        batch = XhsAgentBatch(device_id=device.id, local_batch_key="20260717-captcha", mode="test", status="running", schedule_date=date.today(), total_keywords=1, started_at=datetime.now())
        db.add(batch); db.commit()
        batch_id, device_id, keyword_id = batch.public_id, device.id, keyword.id

    ingestion.ingest_agent_result(
        device_id=device_id, batch_public_id=batch_id, keyword_id=keyword_id,
        idempotency_key="20260717-captcha:keyword-1",
        payload={"status": "risk_blocked", "error": "Captcha required: type=216", "notes": []},
    )
    with factory() as db:
        run = db.query(XhsKeywordRun).one()
        upload = db.query(XhsAgentUpload).one()
        call = db.query(XhsProviderCall).one()
        assert run.status == "risk_blocked" and run.cli_status == "verification_required"
        assert upload.status == "blocked"
        assert call.status == "blocked" and call.error_code == "AgentVerificationRequired"
