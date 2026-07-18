"""本地 XHS Agent 结果的幂等校验与服务器入库。"""
from __future__ import annotations

import hashlib
import json
from datetime import timedelta
from typing import Any

from sqlalchemy import select

from app.core.timezone import utcnow
from app.db.session import SessionLocal
from app.models.xhs import (
    XhsAgentBatch, XhsAgentUpload, XhsEngagementSnapshot, XhsKeyword,
    XhsKeywordRun, XhsProviderCall,
)
from app.services.xhs_collection import (
    Candidate, count_value, dt_value, rank, record_discoveries, rejection_reason,
    sync_raw_info, upsert_note,
)

LOCAL_PROVIDER = "local_cli"


class AgentIngestionConflict(RuntimeError):
    pass


def canonical_payload_hash(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def _candidate(raw: dict[str, Any], fallback_rank: int) -> Candidate:
    author = raw.get("author") if isinstance(raw.get("author"), dict) else {}
    engagement = raw.get("engagement") if isinstance(raw.get("engagement"), dict) else {}
    note_id = str(raw.get("note_id") or raw.get("id") or "").strip()
    if not note_id:
        raise ValueError("笔记缺少 note_id")
    return Candidate(
        note_id=note_id,
        title=str(raw.get("title") or "")[:500],
        content=str(raw.get("content") or ""),
        published_at=dt_value(raw.get("published_at")),
        note_type=raw.get("note_type") or raw.get("type"),
        author_id=str(author.get("id") or raw.get("author_id") or "") or None,
        author_nickname=str(author.get("nickname") or raw.get("author_nickname") or "")[:200],
        author_bio=str(author.get("bio") or raw.get("author_bio") or ""),
        avatar_url=author.get("avatar_url") or raw.get("avatar_url"),
        cover_url=raw.get("cover_url"),
        like_count=count_value(engagement.get("likes", raw.get("like_count"))),
        collect_count=count_value(engagement.get("collects", raw.get("collect_count"))),
        comment_count=count_value(engagement.get("comments", raw.get("comment_count"))),
        share_count=count_value(engagement.get("shares", raw.get("share_count"))),
        view_count=count_value(engagement.get("views", raw.get("view_count"))),
        tags=[str(x) for x in (raw.get("tags") or raw.get("native_tags") or [])][:30],
        xsec_url=raw.get("original_url") or raw.get("xsec_url"),
        ranks={LOCAL_PROVIDER: int(raw.get("provider_rank") or fallback_rank)},
        payloads={LOCAL_PROVIDER: {"agent": True}},
    )


def ingest_agent_result(
    *,
    device_id: int,
    batch_public_id: str,
    keyword_id: int,
    idempotency_key: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    """一次关键词一个事务；重复上传直接返回第一次结果。"""
    payload_hash = canonical_payload_hash(payload)
    now = utcnow()
    with SessionLocal() as db:
        existing = db.scalar(select(XhsAgentUpload).where(XhsAgentUpload.idempotency_key == idempotency_key))
        if existing:
            if existing.payload_hash != payload_hash:
                raise AgentIngestionConflict("同一幂等键对应了不同内容")
            return {
                "upload_id": existing.id,
                "duplicate": True,
                "accepted": existing.accepted_count,
                "rejections": existing.rejection_counts or {},
            }

        batch = db.scalar(select(XhsAgentBatch).where(XhsAgentBatch.public_id == batch_public_id, XhsAgentBatch.device_id == device_id))
        if not batch:
            raise ValueError("采集批次不存在或不属于当前设备")
        keyword = db.get(XhsKeyword, keyword_id)
        if not keyword or not keyword.enabled:
            raise ValueError("关键词不存在或已停用")

        run = db.scalar(select(XhsKeywordRun).where(XhsKeywordRun.keyword_id == keyword.id, XhsKeywordRun.run_date == now.date()))
        if not run:
            run = XhsKeywordRun(keyword_id=keyword.id, run_date=now.date(), started_at=now)
            db.add(run)
            db.flush()
        run.run_source = "local_agent"
        run.agent_batch_id = batch.id
        run.status = "running"
        run.cli_status = "running"
        run.tikhub_status = "skipped_free"

        notes = payload.get("notes") if isinstance(payload.get("notes"), list) else []
        candidates: list[Candidate] = []
        invalid_payload = 0
        for index, raw in enumerate(notes, 1):
            if not isinstance(raw, dict):
                invalid_payload += 1
                continue
            try:
                candidates.append(_candidate(raw, index))
            except (TypeError, ValueError):
                invalid_payload += 1

        diagnostics = payload.get("diagnostics") if isinstance(payload.get("diagnostics"), dict) else {}
        diagnostic_rejections = diagnostics.get("rejection_counts") if isinstance(diagnostics.get("rejection_counts"), dict) else {}
        rejections = {"old": 0, "low_like": 0, "unknown_metric": 0, "unknown_date": 0, "unknown_type": 0, "core_incomplete": 0, "rank_overflow": 0, "invalid_payload": invalid_payload}
        for key in ("old", "low_like", "unknown_metric", "unknown_date", "invalid_payload"):
            rejections[key] += max(0, int(diagnostic_rejections.get(key) or 0))
        eligible: list[Candidate] = []
        for candidate in candidates:
            candidate.score = rank(candidate, now)
            reason = rejection_reason(candidate, now)
            if reason:
                rejections[reason] += 1
                note = upsert_note(db, candidate, "rejected_" + reason, now)
                record_discoveries(db, run.id, keyword.id, note, candidate, now)
            else:
                eligible.append(candidate)

        eligible.sort(key=lambda item: item.score, reverse=True)
        selected = eligible[:10]
        rejections["rank_overflow"] = max(0, len(eligible) - len(selected))
        for candidate in eligible[10:]:
            note = upsert_note(db, candidate, "rejected_rank", now)
            record_discoveries(db, run.id, keyword.id, note, candidate, now)
        for candidate in selected:
            note = upsert_note(db, candidate, "ready_degraded" if candidate.title_generated else "ready", now)
            record_discoveries(db, run.id, keyword.id, note, candidate, now)
            snapshot = db.scalar(select(XhsEngagementSnapshot).where(XhsEngagementSnapshot.note_id == note.id, XhsEngagementSnapshot.snapshot_date == now.date()))
            if not snapshot:
                db.add(XhsEngagementSnapshot(
                    note_id=note.id, snapshot_date=now.date(), like_count=note.like_count,
                    collect_count=note.collect_count, comment_count=note.comment_count,
                    share_count=note.share_count, view_count=note.view_count,
                ))
            sync_raw_info(db, note)

        agent_status = str(payload.get("status") or "success")
        risk_blocked = agent_status == "risk_blocked"
        error_message = str(payload.get("error") or "")[:1000] or None
        has_diagnostics = int(diagnostics.get("version") or 0) >= 1
        search_raw_count = max(0, int(diagnostics.get("search_returned_count") or 0)) if has_diagnostics else len(candidates)
        run.cli_raw_count = search_raw_count
        run.merged_count = max(0, int(diagnostics.get("normalized_count") or 0)) if has_diagnostics else len(candidates)
        run.within_week_count = max(0, int(diagnostics.get("within_week_count") or 0)) if has_diagnostics else sum(1 for item in candidates if item.published_at and item.published_at >= now - timedelta(days=7))
        run.eligible_like_count = max(0, int(diagnostics.get("eligible_like_count") or 0)) if has_diagnostics else sum(1 for item in candidates if (item.like_count or 0) > 2000)
        run.filtered_count = len(eligible)
        run.final_count = len(selected)
        run.displayable_count = len(selected)
        run.rejection_counts = {
            **rejections,
            **({
                "_search_diagnostics": 1,
                "_search_state_empty": int(diagnostics.get("search_state") == "empty"),
                "_search_state_unrecognized": int(diagnostics.get("search_state") == "unrecognized"),
                "_detail_attempted": max(0, int(diagnostics.get("detail_attempted_count") or 0)),
                "_detail_success": max(0, int(diagnostics.get("detail_success_count") or 0)),
            } if has_diagnostics else {}),
        }
        run.cli_status = "verification_required" if risk_blocked else "success" if agent_status == "success" else "failed"
        run.status = "risk_blocked" if risk_blocked else "completed" if agent_status == "success" else "partial"
        run.error_message = error_message
        run.finished_at = now
        keyword.last_run_at = now
        if keyword.keyword_type == "derived":
            keyword.cooldown_until = now.date() + timedelta(days=3)
            keyword.next_run_at = None

        upload = XhsAgentUpload(
            batch_id=batch.id, keyword_id=keyword.id, run_id=run.id,
            idempotency_key=idempotency_key, payload_hash=payload_hash,
            status="blocked" if risk_blocked else "accepted" if agent_status == "success" else "partial",
            raw_count=search_raw_count, accepted_count=len(selected),
            rejection_counts=rejections, error_message=error_message,
        )
        db.add(upload)
        db.add(XhsProviderCall(
            provider=LOCAL_PROVIDER, operation="agent_upload", run_id=run.id,
            status="blocked" if risk_blocked else "success" if agent_status == "success" else "failed",
            is_paid=False, request_count=0, estimated_cost=0,
            error_code="AgentVerificationRequired" if risk_blocked else None if agent_status == "success" else "AgentCollectionError",
            error_message=error_message,
            metadata_json={"batch_id": batch.public_id, "device_id": device_id, "raw_count": search_raw_count, "diagnostics": diagnostics},
        ))
        batch.completed_keywords += 1 if agent_status == "success" else 0
        batch.failed_keywords += 0 if agent_status == "success" else 1
        batch.current_keyword_id = None
        batch.last_progress_at = now
        db.commit()
        db.refresh(upload)
        return {"upload_id": upload.id, "duplicate": False, "accepted": len(selected), "rejections": rejections, "run_id": run.id}
