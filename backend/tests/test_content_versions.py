"""Phase 1c 文章版本、diff、经验库和文档解析测试。"""

import io
import json

import pytest
from fastapi import HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from starlette.datastructures import Headers
from starlette.datastructures import UploadFile

from app.api.v1 import content_versions as versions_api
from app.api.v1 import experience as experience_api
from app.models.article_member import ArticleMember
from app.models.content_version import ContentVersion, ExperienceCard
from app.models.creation import ContentCreation
from app.models.employee_profile import EmployeeProfile
from app.models.meeting import Meeting, MeetingSuggestion
from app.models.user import User
from app.schemas.content_version import (
    ContentVersionCreate,
    ExperienceCardDraftCreate,
    ExperienceCardUpdate,
)
from app.services.content_snapshot import build_content_snapshot
from app.services.content_version_service import (
    VersionDiffSummaryError,
    build_text_diff,
    summarize_version_diff,
)
from app.services.llm.llm_client import ChatResult


def _user(user_id: int, role: str = "user") -> User:
    return User(
        id=user_id,
        username=f"user-{user_id}",
        full_name=f"用户{user_id}",
        role=role,
        is_active=True,
        is_superuser=False,
    )


@pytest.fixture
async def version_db():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with engine.begin() as conn:
        await conn.run_sync(
            lambda sync_conn: User.metadata.create_all(
                sync_conn,
                tables=[
                    User.__table__,
                    EmployeeProfile.__table__,
                    ContentCreation.__table__,
                    Meeting.__table__,
                    MeetingSuggestion.__table__,
                    ContentVersion.__table__,
                    ExperienceCard.__table__,
                    ArticleMember.__table__,
                ],
            )
        )
    try:
        yield factory
    finally:
        await engine.dispose()


async def _seed_creation(db: AsyncSession, *, creation_id: int = 1) -> tuple[User, ContentCreation]:
    author = _user(creation_id)
    creation = ContentCreation(
        id=creation_id,
        user_id=author.id,
        title="一篇文章",
        content=json.dumps({"final_text": "开头冲突\n\n原始案例", "section_count": 2}, ensure_ascii=False),
        status="draft",
    )
    db.add_all([author, creation])
    await db.commit()
    return author, creation


@pytest.mark.asyncio
async def test_content_snapshot_extracts_editor_json_and_mixed_word_count():
    snapshot, text, count = build_content_snapshot(
        json.dumps({"final_text": "中文ABC 123", "gold_sentences": ["不要算入"]}, ensure_ascii=False)
    )
    assert snapshot["final_text"] == "中文ABC 123"
    assert text == "中文ABC 123"
    assert count == len("中文ABC 123")


@pytest.mark.asyncio
async def test_author_can_save_versions_and_previous_version_is_used(version_db, monkeypatch):
    async with version_db() as db:
        author, creation = await _seed_creation(db)
        async def fake_enqueue(card, db):
            return {"status": "failed", "task_id": "embedding-test"}

        monkeypatch.setattr(versions_api, "enqueue_embedding", fake_enqueue)
        first = await versions_api.save_creation_version(
            1,
            ContentVersionCreate(version_type="before_meeting", note="会前"),
            db,
            author,
        )
        assert first["data"]["version"]["version_no"] == 1
        assert first["data"]["version"]["content_text"] == "开头冲突\n\n原始案例"

        creation.content = json.dumps({"final_text": "开头冲突更具体了\n\n新增真实案例"}, ensure_ascii=False)
        await db.commit()
        second = await versions_api.save_creation_version(
            1,
            ContentVersionCreate(version_type="after_meeting", save_as_experience=True),
            db,
            author,
        )
        assert second["data"]["version"]["version_no"] == 2
        card = (await db.scalars(select(ExperienceCard))).one()
        assert card.version_pair == {"before": 1, "after": 2}
        assert "v1 → v2" in card.content


@pytest.mark.asyncio
async def test_viewer_cannot_save_but_editor_can_save_shared_article(version_db):
    async with version_db() as db:
        author, _ = await _seed_creation(db)
        viewer = _user(2)
        editor = _user(3)
        db.add_all([
            viewer,
            editor,
            ArticleMember(creation_id=1, user_id=2, role="viewer", granted_by=1),
            ArticleMember(creation_id=1, user_id=3, role="editor", granted_by=1),
        ])
        await db.commit()
        with pytest.raises(HTTPException) as viewer_error:
            await versions_api.save_creation_version(
                1,
                ContentVersionCreate(version_type="manual"),
                db,
                viewer,
            )
        assert viewer_error.value.status_code == 403
        result = await versions_api.save_creation_version(
            1,
            ContentVersionCreate(version_type="manual"),
            db,
            editor,
        )
        assert result["data"]["version"]["created_by"] == 3


@pytest.mark.asyncio
async def test_version_access_and_diff_permission_and_cross_creation_errors(version_db):
    async with version_db() as db:
        author, _ = await _seed_creation(db)
        another_author, _ = await _seed_creation(db, creation_id=2)
        first = await versions_api.save_creation_version(1, ContentVersionCreate(), db, author)
        second = await versions_api.save_creation_version(2, ContentVersionCreate(), db, another_author)
        with pytest.raises(HTTPException) as cross_error:
            await versions_api.diff_creation_versions(1, first["data"]["version"]["id"], second["data"]["version"]["id"], db, author)
        assert cross_error.value.status_code == 400

        outsider = _user(9)
        db.add(outsider)
        await db.commit()
        with pytest.raises(HTTPException) as forbidden:
            await versions_api.list_creation_versions(1, None, db, outsider)
        assert forbidden.value.status_code == 403


def test_text_diff_reports_added_removed_and_unchanged_lines():
    result = build_text_diff("第一行\n删除行\n保留行", "第一行\n新增行\n保留行")
    assert result["added_count"] == 1
    assert result["removed_count"] == 1
    assert {line["kind"] for line in result["lines"]} == {"added", "removed", "unchanged"}
    assert "新增行" in result["unified_diff"]


class FakeLLM:
    def __init__(self, result: ChatResult):
        self.result = result
        self.calls = 0

    async def chat(self, messages, **kwargs):
        self.calls += 1
        return self.result


@pytest.mark.asyncio
async def test_semantic_summary_accepts_json_and_loose_repair():
    fake = FakeLLM(ChatResult(text='```json\n{"summary":"强化开头","changes":[{"position":"开头","before":"旧","after":"新","reason":null}],"suggestion_match":null}\n```'))
    result = await summarize_version_diff("旧", "新", llm_client=fake)
    assert fake.calls == 1
    assert result["summary"] == "强化开头"
    assert result["changes"][0]["reason"] is None

    broken = FakeLLM(ChatResult(text='{"summary":"截断后仍可用","changes":[{"position":"中段","before":"旧","after":"新"'))
    repaired = await summarize_version_diff("旧", "新", llm_client=broken)
    assert repaired["summary"] == "截断后仍可用"


@pytest.mark.asyncio
async def test_semantic_summary_invalid_json_raises_without_affecting_text_diff():
    fake = FakeLLM(ChatResult(text="不是 JSON"))
    with pytest.raises(VersionDiffSummaryError):
        await summarize_version_diff("旧", "新", llm_client=fake)
    assert build_text_diff("旧", "新")["added_count"] == 1


@pytest.mark.asyncio
async def test_experience_library_blocks_normal_user_and_keyword_fallback(version_db, monkeypatch):
    async with version_db() as db:
        author, creation = await _seed_creation(db)
        employee = _user(2, "employee")
        normal = _user(3)
        db.add_all([
            employee,
            normal,
            ExperienceCard(
                title="真实案例要具体",
                content="开头需要先写清楚具体冲突和案例依据。",
                source_type="manual",
                category="开头",
                created_by=2,
            ),
        ])
        await db.commit()
        with pytest.raises(HTTPException) as forbidden:
            await experience_api.list_experience_cards("案例", None, 1, 20, db, normal)
        assert forbidden.value.status_code == 403

        async def no_embedding(text):
            return None

        monkeypatch.setattr("app.services.experience_service.embedding_service.embed", no_embedding)
        result = await experience_api.list_experience_cards("案例", None, 1, 20, db, employee)
        assert result["data"]["search_mode"] == "keyword_fallback"
        assert result["data"]["items"][0]["match_method"] == "keyword_fallback"


@pytest.mark.asyncio
async def test_experience_draft_stays_hidden_until_confirmed(version_db, monkeypatch):
    async def fake_enqueue(card, db):
        return {"status": "queued", "task_id": "experience-test"}

    monkeypatch.setattr(experience_api, "enqueue_embedding", fake_enqueue)
    async with version_db() as db:
        employee = _user(2, "employee")
        db.add(employee)
        await db.commit()
        draft = await experience_api.create_experience_draft(
            ExperienceCardDraftCreate(
                title="先写清楚冲突",
                content="文章开头先让读者看见具体冲突，再进入解释。",
                category="开头",
                source_type="uploaded",
                source_meta={"filename": "会议方法论.docx"},
            ),
            db,
            employee,
        )
        card_id = draft["data"]["card"]["id"]
        assert draft["data"]["card"]["status"] == "pending"

        formal_list = await experience_api.list_experience_cards(None, None, 1, 20, db, employee)
        pending_list = await experience_api.list_experience_cards(
            None,
            None,
            1,
            20,
            db,
            employee,
            card_status="pending",
        )
        assert formal_list["data"]["total"] == 0
        assert pending_list["data"]["total"] == 1

        updated = await experience_api.update_experience_card(
            card_id,
            ExperienceCardUpdate(content="先写具体冲突，再给出案例和判断。"),
            db,
            employee,
        )
        assert updated["data"]["card"]["content"].startswith("先写具体冲突")
        confirmed = await experience_api.confirm_experience_card(card_id, db, employee)
        assert confirmed["data"]["card"]["status"] == "confirmed"

        formal_list = await experience_api.list_experience_cards(None, None, 1, 20, db, employee)
        assert formal_list["data"]["total"] == 1


@pytest.mark.asyncio
async def test_pdf_word_upload_is_parsed_before_manual_save(version_db, monkeypatch):
    from docx import Document

    buffer = io.BytesIO()
    document = Document()
    document.add_paragraph("上传的经验正文：先写冲突，再给案例。")
    document.save(buffer)
    buffer.seek(0)
    upload = UploadFile(
        file=buffer,
        filename="经验.docx",
        headers=Headers({"content-type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document"}),
    )
    request = Request({
        "type": "http",
        "method": "POST",
        "path": "/api/v1/experience/upload",
        "headers": [],
        "query_string": b"",
        "server": ("testserver", 80),
        "client": ("testclient", 1),
    })
    monkeypatch.setattr(experience_api, "enforce_rate_limit", lambda *args, **kwargs: _async_noop())
    async with version_db() as db:
        employee = _user(2, "employee")
        db.add(employee)
        await db.commit()
        result = await experience_api.parse_experience_upload(request, upload, db, employee)
    assert result["data"]["text"] == "上传的经验正文：先写冲突，再给案例。"
    assert result["data"]["truncated"] is False


@pytest.mark.asyncio
async def test_pdf_upload_is_parsed_before_manual_save(version_db, monkeypatch):
    import fitz

    document = fitz.open()
    page = document.new_page()
    page.insert_text((72, 72), "PDF experience body: start with a conflict, then give a case.")
    pdf_data = document.tobytes()
    document.close()
    upload = UploadFile(
        file=io.BytesIO(pdf_data),
        filename="经验.pdf",
        headers=Headers({"content-type": "application/pdf"}),
    )
    request = Request({
        "type": "http",
        "method": "POST",
        "path": "/api/v1/experience/upload",
        "headers": [],
        "query_string": b"",
        "server": ("testserver", 80),
        "client": ("testclient", 1),
    })
    monkeypatch.setattr(experience_api, "enforce_rate_limit", lambda *args, **kwargs: _async_noop())
    async with version_db() as db:
        employee = _user(2, "employee")
        db.add(employee)
        await db.commit()
        result = await experience_api.parse_experience_upload(request, upload, db, employee)
    assert "PDF experience body" in result["data"]["text"]
    assert result["data"]["truncated"] is False


async def _async_noop():
    return None
