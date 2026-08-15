"""初稿诊断复用已确认经验的单元测试。"""

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.api.v1 import draft_diagnoses as diagnosis_api
from app.models.content_version import ExperienceCard
from app.models.creation import ContentCreation
from app.models.draft_diagnosis import DraftDiagnosis
from app.models.employee_profile import EmployeeProfile
from app.models.meeting import Meeting, MeetingSuggestion
from app.models.user import User
from app.schemas.draft_diagnosis import (
    DraftDiagnosisCreate,
    DraftDiagnosisExperienceDraftCreate,
    DraftDiagnosisTitleUpdate,
)
from app.services.draft_diagnosis_service import normalize_draft_diagnosis_analysis


def _user(user_id: int, role: str = "admin") -> User:
    return User(
        id=user_id,
        username=f"diagnosis-user-{user_id}",
        full_name=f"诊断用户{user_id}",
        role=role,
        is_active=True,
        is_superuser=False,
    )


@pytest.fixture
async def diagnosis_db():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with engine.begin() as conn:
        await conn.run_sync(
            lambda sync_conn: User.metadata.create_all(
                sync_conn,
                tables=[
                    User.__table__,
                    ContentCreation.__table__,
                    Meeting.__table__,
                    MeetingSuggestion.__table__,
                    ExperienceCard.__table__,
                    DraftDiagnosis.__table__,
                    EmployeeProfile.__table__,
                ],
            )
        )
    try:
        yield factory
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_normalize_diagnosis_keeps_only_recalled_experience_ids():
    result = normalize_draft_diagnosis_analysis(
        {
            "summary": "开头缺少具体冲突",
            "overall_score": 58,
            "issues": [{
                "title": "冲突不清",
                "severity": "high",
                "problem": "读者不知道为什么要继续看",
                "recommendation": "先写具体场景",
                "experience_ids": [1, 999, "bad"],
            }],
            "improvement_plan": [{"priority": 1, "action": "补充真实案例", "experience_ids": [1]}],
            "referenced_experience_ids": [1, 999],
        },
        allowed_experience_ids=[1],
    )
    assert result["overall_score"] == 58
    assert result["issues"][0]["experience_ids"] == [1]
    assert result["referenced_experience_ids"] == [1]


@pytest.mark.asyncio
async def test_draft_diagnosis_reuses_confirmed_cards_and_can_create_pending_experience(
    diagnosis_db,
    monkeypatch,
):
    async with diagnosis_db() as db:
        employee = _user(1)
        card = ExperienceCard(
            id=11,
            title="先写清楚冲突",
            content="文章开头先让读者看到具体冲突，再进入解释。",
            category="开头",
            source_type="meeting_methodology",
            status="confirmed",
            created_by=employee.id,
        )
        db.add_all([employee, card])
        await db.commit()

        async def fake_match(*args, **kwargs):
            return [(card, 0.91, "semantic")], "semantic", True

        async def fake_diagnose(*args, **kwargs):
            assert kwargs["matched_experiences"][0]["id"] == 11
            assert kwargs["brief_context"]["core_message"] == "先让读者看到结果"
            return {
                "summary": "开头需要更具体",
                "overall_score": 62,
                "issues": [{
                    "index": 0,
                    "title": "冲突太晚出现",
                    "severity": "high",
                    "problem": "前两段没有具体场景",
                    "evidence": "开头从概念解释开始",
                    "recommendation": "先补一个真实冲突",
                    "experience_ids": [11],
                }],
                "strengths": [],
                "improvement_plan": [],
                "questions": [],
                "overall_assessment": None,
                "referenced_experience_ids": [11],
            }

        monkeypatch.setattr(diagnosis_api, "match_experience_cards", fake_match)
        monkeypatch.setattr(diagnosis_api, "diagnose_draft", fake_diagnose)

        result = await diagnosis_api.create_pasted_draft_diagnosis(
            DraftDiagnosisCreate(
                title="初稿 A",
                content="这是一篇还在整理中的初稿。",
                goal="让读者理解问题",
                brief_context={
                    "core_message": "先让读者看到结果",
                    "must_cover": ["真实使用场景"],
                    "banned": ["夸大承诺"],
                    "raw_text": "先让读者看到结果",
                },
            ),
            db,
            employee,
        )
        diagnosis = result["data"]["diagnosis"]
        assert diagnosis["status"] == "completed"
        assert diagnosis["matched_experience_ids"] == [11]
        assert diagnosis["matched_experiences"][0]["title"] == "先写清楚冲突"
        assert diagnosis["brief_context"]["core_message"] == "先让读者看到结果"

        pending = await diagnosis_api.create_draft_diagnosis_experience(
            diagnosis["id"],
            DraftDiagnosisExperienceDraftCreate(finding_index=0),
            db,
            employee,
        )
        assert pending["data"]["card"]["status"] == "pending"
        saved = (await db.scalars(select(ExperienceCard).where(ExperienceCard.status == "pending"))).one()
        assert saved.source_type == "review_feedback"
        assert saved.source_meta["diagnosis_id"] == diagnosis["id"]


async def _seed_diagnosis(db, user, title: str = "原始标题") -> int:
    async def fake_match(*args, **kwargs):
        return [], "keyword_fallback", False

    async def fake_diagnose(*args, **kwargs):
        return {
            "summary": "诊断总结",
            "overall_score": 70,
            "issues": [],
            "strengths": [],
            "improvement_plan": [],
            "questions": [],
            "overall_assessment": None,
            "referenced_experience_ids": [],
        }

    original_match = diagnosis_api.match_experience_cards
    original_diagnose = diagnosis_api.diagnose_draft
    diagnosis_api.match_experience_cards = fake_match
    diagnosis_api.diagnose_draft = fake_diagnose
    try:
        result = await diagnosis_api.create_pasted_draft_diagnosis(
            DraftDiagnosisCreate(title=title, content="这是一篇初稿正文。"),
            db,
            user,
        )
        return result["data"]["diagnosis"]["id"]
    finally:
        diagnosis_api.match_experience_cards = original_match
        diagnosis_api.diagnose_draft = original_diagnose


@pytest.mark.asyncio
async def test_update_draft_diagnosis_title_by_owner(diagnosis_db):
    async with diagnosis_db() as db:
        employee = _user(1)
        db.add(employee)
        await db.commit()
        diagnosis_id = await _seed_diagnosis(db, employee)

        updated = await diagnosis_api.update_draft_diagnosis_title(
            diagnosis_id,
            DraftDiagnosisTitleUpdate(title="  新的诊断标题  "),
            db,
            employee,
        )
        assert updated["data"]["diagnosis"]["title"] == "新的诊断标题"

        stored = (await db.scalars(
            select(DraftDiagnosis).where(DraftDiagnosis.id == diagnosis_id)
        )).one()
        assert stored.title == "新的诊断标题"


@pytest.mark.asyncio
async def test_non_owner_cannot_update_or_delete_diagnosis(diagnosis_db):
    async with diagnosis_db() as db:
        owner = _user(1)
        other = _user(2, role="employee")
        other_profile = EmployeeProfile(user_id=2, department="编辑部", position="作者", status="active")
        db.add_all([owner, other, other_profile])
        await db.commit()
        diagnosis_id = await _seed_diagnosis(db, owner)

        with pytest.raises(Exception) as exc_info:
            await diagnosis_api.update_draft_diagnosis_title(
                diagnosis_id,
                DraftDiagnosisTitleUpdate(title="不允许的标题"),
                db,
                other,
            )
        assert getattr(exc_info.value, "status_code", None) == 404

        with pytest.raises(Exception) as exc_info:
            await diagnosis_api.delete_draft_diagnosis(diagnosis_id, db, other)
        assert getattr(exc_info.value, "status_code", None) == 404

        # 记录仍然存在。
        assert (await db.scalars(
            select(DraftDiagnosis).where(DraftDiagnosis.id == diagnosis_id)
        )).one()


@pytest.mark.asyncio
async def test_delete_draft_diagnosis_by_owner(diagnosis_db):
    async with diagnosis_db() as db:
        employee = _user(1)
        db.add(employee)
        await db.commit()
        diagnosis_id = await _seed_diagnosis(db, employee)

        deleted = await diagnosis_api.delete_draft_diagnosis(diagnosis_id, db, employee)
        assert deleted["data"]["diagnosis_id"] == diagnosis_id

        assert (await db.scalars(
            select(DraftDiagnosis).where(DraftDiagnosis.id == diagnosis_id)
        )).first() is None
