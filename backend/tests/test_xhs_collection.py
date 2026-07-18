import asyncio
import sys
import types
from datetime import date, datetime, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db.base import Base
from app.models.xhs import XhsDailyQuota, XhsKeyword, XhsKeywordRun
from app.db.seeds.seed_accounts_from_table2 import X_KEYWORDS
from app.services.xhs_collection import (
    Candidate, CliProvider, TikHubBudgetExhausted, _xsec_token, consume_tikhub_quota, count_value,
    hydrate, merge_provider_candidates, normalize_candidate, pre_hydration_rejection, rank,
    rejection_reason, reserve_tikhub_searches,
)
from app.services.xhs_cli_entrypoint import XHS_SEARCH_FILTERS, main as xhs_cli_main


def test_cli_error_message_prefers_structured_stdout():
    payload = b'{"ok":false,"error":{"code":"not_authenticated","message":"Session expired"}}'
    message = CliProvider._error_message(payload, b"")
    assert message == "not_authenticated: Session expired"
    assert CliProvider._is_auth_expired(message)
    assert not CliProvider._is_risk_error(message)


def test_cli_error_message_falls_back_to_stderr():
    assert CliProvider._error_message(b"", b"network failed\n") == "network failed"


def test_cli_search_filters_are_one_week_and_most_liked():
    filters={item["type"]:item["tags"] for item in XHS_SEARCH_FILTERS}
    assert filters["sort_type"] == ["popularity_descending"]
    assert filters["filter_note_time"] == ["一周内"]


def test_cli_entrypoint_calls_installed_click_cli(monkeypatch):
    called = []
    package = types.ModuleType("xhs_cli")
    package.__path__ = []
    client_mixins = types.ModuleType("xhs_cli.client_mixins")
    client_mixins._SEARCH_DEFAULT_FILTERS = []
    cli_module = types.ModuleType("xhs_cli.cli")
    cli_module.cli = lambda: called.append(True)
    package.client_mixins = client_mixins
    monkeypatch.setitem(sys.modules, "xhs_cli", package)
    monkeypatch.setitem(sys.modules, "xhs_cli.client_mixins", client_mixins)
    monkeypatch.setitem(sys.modules, "xhs_cli.cli", cli_module)

    xhs_cli_main()

    assert called == [True]
    assert client_mixins._SEARCH_DEFAULT_FILTERS == XHS_SEARCH_FILTERS


def test_strict_eligibility_excludes_equal_2000_old_and_unknown():
    now=datetime(2026,7,16,12,0,0)
    base=dict(note_id="n",title="完整标题",content="完整正文",author_nickname="作者",cover_url="https://sns-webpic.xhscdn.com/a.jpg",note_type="image")
    assert rejection_reason(Candidate(**base,published_at=now-timedelta(days=1),like_count=2000),now)=="low_like"
    assert rejection_reason(Candidate(**base,published_at=now-timedelta(days=8),like_count=9000),now)=="old"
    assert rejection_reason(Candidate(**base,published_at=None,like_count=9000),now)=="unknown_metric"
    assert rejection_reason(Candidate(**base,published_at=now-timedelta(days=1),like_count=None),now)=="unknown_metric"
    assert rejection_reason(Candidate(**base,published_at=now-timedelta(days=1),like_count=2001),now) is None


def test_missing_title_uses_first_content_paragraph_as_degraded_title():
    now=datetime(2026,7,16,12,0,0)
    candidate=Candidate(
        note_id="title-fallback", title="", content="第一段正文，应该成为临时标题。\n\n第二段不应进入标题。",
        author_nickname="作者", cover_url="https://sns-webpic.xhscdn.com/a.jpg",
        note_type="image", published_at=now, like_count=3000,
    )
    assert rejection_reason(candidate,now) is None
    assert candidate.title == "第一段正文，应该成为临时标题。"
    assert candidate.title_generated is True


def test_base_keyword_catalog_has_33_normalized_unique_entries():
    normalized=[" ".join(value.lower().split()) for value in X_KEYWORDS]
    assert len(normalized)==33
    assert len(set(normalized))==33


def test_image_and_video_are_both_eligible():
    now=datetime(2026,7,16,12,0,0)
    for note_type in ("image","video"):
        c=Candidate(note_id=note_type,title="标题",content="正文",author_nickname="作者",cover_url="https://sns-webpic.xhscdn.com/a.jpg",note_type=note_type,published_at=now,like_count=3000)
        assert rejection_reason(c,now) is None


def test_candidate_normalization_uses_note_id_and_preserves_explicit_zero():
    raw={"id":"abc123","title":"标题","type":"video","time":1720000000,"user":{"id":"u1","nickname":"作者"},"interact_info":{"liked_count":"2.1万","comment_count":0},"cover":{"url_default":"https://sns-webpic.xhscdn.com/a.jpg"}}
    c=normalize_candidate(raw,"cli",1)
    assert c.note_id=="abc123" and c.like_count==21000 and c.comment_count==0 and c.note_type=="video"
    assert count_value(None) is None and count_value("0")==0


def test_cli_non_note_search_items_are_ignored():
    raw={"id":"suggestion#123","model_type":"query_suggestion","title":"不是笔记"}
    assert normalize_candidate(raw,"cli",1) is None


def test_cli_search_card_schema_preserves_token_date_shares_and_https_images(monkeypatch):
    monkeypatch.setattr("app.services.xhs_collection.utcnow",lambda:datetime(2026,7,16,12,0,0))
    raw={
        "id":"69e72965000000001e00f40c",
        "xsec_token":"token-with-equals=",
        "note_card":{
            "type":"video","display_title":"Claude Code 教程",
            "corner_tag_info":[{"type":"publish_time","text":"07-15"}],
            "user":{"user_id":"u1","nick_name":"作者","avatar":"http://sns-avatar-qc.xhscdn.com/a.jpg"},
            "interact_info":{"liked_count":"22916","shared_count":"3803"},
            "cover":{"url_default":"http://sns-webpic-qc.xhscdn.com/a.webp"},
        },
    }
    c=normalize_candidate(raw,"cli",1)
    assert c.note_id==raw["id"] and c.title=="Claude Code 教程" and c.author_nickname=="作者"
    assert c.published_at==datetime(2026,7,15) and c.like_count==22916 and c.share_count==3803
    assert c.cover_url.startswith("https://") and c.avatar_url.startswith("https://")
    assert "xsec_token=token-with-equals%3D" in c.xsec_url and "xsec_source=pc_search" in c.xsec_url
    assert _xsec_token(c.xsec_url)=="token-with-equals="


def test_search_card_prefilter_avoids_details_for_definitely_ineligible_notes():
    now=datetime(2026,7,16,12,0,0)
    old=Candidate(note_id="old",published_at=datetime(2026,6,23),like_count=22916,note_type="video")
    low=Candidate(note_id="low",published_at=datetime(2026,7,15),like_count=709,note_type="video")
    possible=Candidate(note_id="possible",published_at=datetime(2026,7,15),like_count=3000,note_type="image")
    assert pre_hydration_rejection(old,now)=="old"
    assert pre_hydration_rejection(low,now)=="low_like"
    assert pre_hydration_rejection(possible,now) is None


def test_comprehensive_rank_rewards_better_rank_freshness_and_dual_source():
    now=datetime(2026,7,16,12,0,0)
    high=Candidate(note_id="a",published_at=now,like_count=10000,ranks={"cli":1,"tikhub":2})
    low=Candidate(note_id="b",published_at=now-timedelta(days=6),like_count=3000,ranks={"cli":20})
    assert rank(high,now)>rank(low,now)


def test_each_equal_provider_is_capped_at_20_before_note_id_merge():
    cli=[{"id":f"n{i}","title":f"CLI {i}"} for i in range(25)]
    tikhub=[{"id":f"n{i}","title":f"TikHub {i}"} for i in range(10,35)]
    merged=merge_provider_candidates({"cli":cli,"tikhub":tikhub})
    assert len(merged)==30  # 20 + 20 - 10 duplicate note_ids
    assert set(merged["n10"].ranks)=={"cli","tikhub"}
    assert set(merged["n24"].ranks)=={"tikhub"}


def test_tikhub_search_and_detail_share_atomic_100_call_limit():
    engine=create_engine("sqlite:///:memory:")
    Base.metadata.tables["xhs_daily_quotas"].create(engine)
    with Session(engine) as db:
        reserve_tikhub_searches(db,2,date(2026,7,16))
        # The service uses current Beijing date; align the test row with that date.
        db.query(XhsDailyQuota).delete();db.commit();reserve_tikhub_searches(db,2)
        consume_tikhub_quota(db,operation="search")
        quota=db.query(XhsDailyQuota).one();quota.used_count=99;quota.reserved_search_count=0;db.commit()
        consume_tikhub_quota(db,operation="detail")
        try:consume_tikhub_quota(db,operation="search")
        except TikHubBudgetExhausted:pass
        else:raise AssertionError("100 次后必须停止全部 TikHub 请求")


def test_keyword_run_has_same_day_unique_constraint():
    engine=create_engine("sqlite:///:memory:")
    Base.metadata.tables["xhs_keywords"].create(engine)
    Base.metadata.tables["xhs_keyword_runs"].create(engine)
    with Session(engine) as db:
        kw=XhsKeyword(keyword="Codex",normalized_keyword="codex",keyword_type="base",schedule_group=1,enabled=True);db.add(kw);db.flush();db.add(XhsKeywordRun(keyword_id=kw.id,run_date=date.today()));db.commit()
        duplicate=XhsKeywordRun(keyword_id=kw.id,run_date=date.today());db.add(duplicate)
        try:db.commit()
        except Exception:db.rollback()
        else:raise AssertionError("同一关键词当天只能有一个逻辑轮次")


def test_free_hydration_never_calls_tikhub(monkeypatch):
    paid_calls=[]

    class FreeCli:
        async def detail(self, _candidate):
            return {"data": {"id": "free-note", "title": "仅免费补全"}}

    class PaidTikHub:
        async def detail(self, _candidate):
            paid_calls.append(_candidate.note_id)
            return {}

    monkeypatch.setattr("app.services.xhs_collection.log_call", lambda *args, **kwargs: None)
    candidate=Candidate(note_id="free-note")
    asyncio.run(hydrate(candidate,FreeCli(),PaidTikHub(),None,1,allow_paid=False))
    assert candidate.title=="仅免费补全"
    assert paid_calls==[]
