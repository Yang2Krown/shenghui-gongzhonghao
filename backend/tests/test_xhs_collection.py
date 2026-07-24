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
    hydrate, merge_provider_candidates, needs_hydration, normalize_candidate, pre_hydration_rejection, rank,
    rejection_reason, reserve_tikhub_searches, unwrap_detail, unwrap_items, upsert_engagement_snapshot,
    upsert_note, xsec_note_url,
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


def test_strict_eligibility_uses_daily_200_and_weekly_2000_levels():
    now=datetime(2026,7,16,12,0,0)
    base=dict(note_id="n",title="完整标题",content="完整正文",author_nickname="作者",cover_url="https://sns-webpic.xhscdn.com/a.jpg",note_type="image")
    # 标准档未过但高于地板 → 放宽档待补录（low_like_soft）
    assert rejection_reason(Candidate(**base,published_at=now-timedelta(hours=23),like_count=200),now)=="low_like_soft"
    assert rejection_reason(Candidate(**base,published_at=now-timedelta(days=2),like_count=2000),now)=="low_like_soft"
    # 地板及以下 → 永久拒绝（low_like）
    assert rejection_reason(Candidate(**base,published_at=now-timedelta(hours=23),like_count=100),now)=="low_like"
    assert rejection_reason(Candidate(**base,published_at=now-timedelta(days=2),like_count=1500),now)=="low_like"
    # 标准档通过
    assert rejection_reason(Candidate(**base,published_at=now-timedelta(hours=23),like_count=201),now) is None
    assert rejection_reason(Candidate(**base,published_at=now-timedelta(days=2),like_count=2001),now) is None
    # 补录判定（relaxed=True）：放宽档通过，地板以下仍拒绝
    assert rejection_reason(Candidate(**base,published_at=now-timedelta(hours=23),like_count=101),now,relaxed=True) is None
    assert rejection_reason(Candidate(**base,published_at=now-timedelta(days=2),like_count=1501),now,relaxed=True) is None
    assert rejection_reason(Candidate(**base,published_at=now-timedelta(hours=23),like_count=100),now,relaxed=True)=="low_like"
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


def test_tikhub_search_sorts_by_popularity_within_one_week(monkeypatch):
    """TikHub search 按点赞最多排序 + 一周内,与高赞素材门槛对齐(防被改回综合排序)。"""
    from app.services.xhs_collection import TikHubProvider
    captured={}
    async def fake_call(self,path,params): captured.update({"path":path,**params}); return {"data":{"data":{"items":[]}}}
    monkeypatch.setattr(TikHubProvider,"_call",fake_call)
    asyncio.run(TikHubProvider().search("AI"))
    assert captured["sort_type"]=="popularity_descending"
    assert captured["time_filter"]=="一周内"


def test_tikhub_search_card_uses_note_timestamp_and_flat_metrics():
    """TikHub app_v2/search_notes:data.data.items[].note,发布时间取 note.timestamp(秒),互动数平铺。"""
    raw={
        "model_type":"note",
        "note":{
            "id":"6a5a54df00000000110069bb","type":"normal","title":"副业","desc":"#下班做副业#",
            "timestamp":1784304863,"update_time":1784522569000,"last_update_time":0,
            "liked_count":32131,"collected_count":18182,"comments_count":7161,"shared_count":1024,
            "images_list":[{"url":"https://sns-na-i27.xhscdn.com/a.webp"}],
            "user":{"nickname":"如果你冷","userid":"68ea28980000000037008a8a","images":"https://sns-avatar-qc.xhscdn.com/a.jpg"},
            "xsec_token":"tok123",
        },
    }
    c=normalize_candidate(raw,"tikhub",1)
    assert c.note_id=="6a5a54df00000000110069bb" and c.published_at==datetime.fromtimestamp(1784304863)
    assert c.like_count==32131 and c.collect_count==18182 and c.comment_count==7161 and c.share_count==1024
    assert c.cover_url=="https://sns-na-i27.xhscdn.com/a.webp" and c.author_id=="68ea28980000000037008a8a"
    assert c.author_nickname=="如果你冷" and _xsec_token(c.xsec_url)=="tok123"


def test_tikhub_detail_note_card_ms_time_and_wan_metrics():
    """TikHub web_v3 详情 note_card.time 是毫秒整数,interact_info.liked_count 是“万”字符串。"""
    payload={"data":{"data":{"items":[{"note_card":{
        "note_id":"6a5a54df00000000110069bb","title":"副业","type":"normal",
        "time":1784304863000,"last_update_time":1784449539000,
        "user":{"user_id":"u1","nickname":"如果你冷","avatar":"https://sns-avatar-qc.xhscdn.com/a.jpg"},
        "interact_info":{"liked_count":"3.2万","collected_count":"1.8万","comment_count":"7161","share_count":"1024"},
        "image_list":[{"url_default":"https://sns-webpic-qc.xhscdn.com/a.webp"}],
    }}]}}}
    flat=unwrap_detail(payload,"6a5a54df00000000110069bb")
    c=normalize_candidate(flat,"tikhub",99)
    assert c.published_at==datetime.fromtimestamp(1784304863) and c.like_count==32000 and c.collect_count==18000
    assert c.comment_count==7161 and c.share_count==1024 and c.cover_url=="https://sns-webpic-qc.xhscdn.com/a.webp"


def test_unwrap_items_drills_through_tikhub_double_data():
    """unwrap_items 能穿过 TikHub 的双层 data 包裹拿到 items 列表。"""
    payload={"code":200,"data":{"success":True,"data":{"items":[{"model_type":"note","note":{"id":"a"}},{"model_type":"note","note":{"id":"b"}}]}}}
    items=unwrap_items(payload)
    assert len(items)==2 and items[0]["note"]["id"]=="a"


def test_bare_search_url_is_rebuilt_with_separate_xsec_token():
    raw={
        "id":"6a57633a0000000021019bc5",
        "url":"https://www.xiaohongshu.com/explore/6a57633a0000000021019bc5",
        "xsec_token":"ABZC7Wl4Gb4YIaf4alGHhvcVNDgPRfGIVjx5_DeFoMTfA=",
        "xsec_source":"pc_search",
        "title":"可直达笔记",
    }
    candidate=normalize_candidate(raw,"cli",1)
    assert candidate.xsec_url == (
        "https://www.xiaohongshu.com/explore/6a57633a0000000021019bc5"
        "?xsec_token=ABZC7Wl4Gb4YIaf4alGHhvcVNDgPRfGIVjx5_DeFoMTfA%3D"
        "&xsec_source=pc_search"
    )


def test_tokenized_candidate_replaces_bare_url_during_provider_merge():
    bare=Candidate(note_id="note-1",xsec_url="https://www.xiaohongshu.com/explore/note-1")
    tokenized=Candidate(note_id="note-1",xsec_url=xsec_note_url("note-1",token="search-token="))
    bare.merge(tokenized)
    assert _xsec_token(bare.xsec_url)=="search-token="


def test_truncated_card_content_triggers_hydration_and_gets_replaced():
    # 搜索卡片正文被截断在 ~60 字：字段"齐全"也要继续拉详情
    now=datetime(2026,7,16,12,0,0)
    card=Candidate(note_id="n",title="标题",content="残" * 60,author_nickname="作者",cover_url="https://sns-webpic.xhscdn.com/a.jpg",note_type="image",published_at=now,like_count=300)
    assert needs_hydration(card) is True
    #  genuinely 短正文（<55 字）的笔记不重复拉详情
    short=Candidate(note_id="n2",title="标题",content="短正文",author_nickname="作者",cover_url="https://sns-webpic.xhscdn.com/a.jpg",note_type="image",published_at=now,like_count=300)
    assert needs_hydration(short) is False
    # 详情拿到更长正文时替换残文，而不是保留截断版
    detail=Candidate(note_id="n",content="完整" * 200)
    card.merge(detail)
    assert card.content == "完整" * 200


def test_search_card_prefilter_avoids_details_for_definitely_ineligible_notes():
    now=datetime(2026,7,16,12,0,0)
    old=Candidate(note_id="old",published_at=datetime(2026,6,23),like_count=22916,note_type="video")
    hard_low=Candidate(note_id="hard-low",published_at=datetime(2026,7,14),like_count=1500,note_type="video")
    soft=Candidate(note_id="soft",published_at=datetime(2026,7,14),like_count=2000,note_type="video")
    possible=Candidate(note_id="possible",published_at=datetime(2026,7,15),like_count=3000,note_type="image")
    assert pre_hydration_rejection(old,now)=="old"
    assert pre_hydration_rejection(hard_low,now)=="low_like"
    # 放宽档候选不提前淘汰也不立即水化，标记为待补录
    assert pre_hydration_rejection(soft,now)=="low_like_soft"
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


def test_repeated_note_refreshes_metrics_and_same_day_snapshot():
    engine=create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine,tables=[Base.metadata.tables["xhs_notes"],Base.metadata.tables["xhs_engagement_snapshots"]])
    now=datetime(2026,7,18,12,0,0)
    with Session(engine) as db:
        first=Candidate(note_id="repeat-note",like_count=300,collect_count=20,comment_count=5,share_count=2,view_count=1000)
        note=upsert_note(db,first,"ready",now);upsert_engagement_snapshot(db,note,now.date());db.commit()
        second=Candidate(note_id="repeat-note",like_count=560,collect_count=44,comment_count=9,share_count=7,view_count=1800)
        note=upsert_note(db,second,"ready",now+timedelta(hours=2));upsert_engagement_snapshot(db,note,now.date());db.commit()
        db.refresh(note)
        snapshot=db.query(Base.metadata.tables["xhs_engagement_snapshots"]).one()
        assert (note.like_count,note.collect_count,note.comment_count,note.share_count,note.view_count)==(560,44,9,7,1800)
        assert (snapshot.like_count,snapshot.collect_count,snapshot.comment_count,snapshot.share_count,snapshot.view_count)==(560,44,9,7,1800)


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
