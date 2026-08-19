from datetime import datetime

import pytest

from app.core.timezone import BJT
from app.services.feishu_digest import (
    backfill_existing_english_records,
    digest_window,
    needs_chinese_translation,
    record_to_feishu_fields,
    source_group,
    sync_digest_records,
    translate_digest_records,
)
from app.services.llm.llm_client import ChatResult
from app.tasks.scheduler import CELERY_BEAT_SCHEDULE


def sample_record(**overrides):
    record = {
        "title": "AI 资讯标题",
        "collected_at": datetime(2026, 8, 19, 9, 30),
        "source_time": datetime(2026, 8, 19, 8, 0),
        "category": "信息选题",
        "source_name": "专业媒体 / RSS｜机器之心",
        "source_category": "专业媒体 / RSS",
        "summary": "摘要",
        "value": "高",
        "url": "https://example.com/article",
        "wave": "上午简报",
        "push_batch": "上午 09:30",
        "batch": "20260819-am",
        "metrics": "互动量 1000",
        "heat_score": 88.5,
        "brand": "",
        "product": "",
        "evidence": "",
        "recommendation": "值得关注",
        "angle": "产品动态",
        "commercial_grade": "无",
        "status": "待查看",
        "note": "互动量 1000",
        "dedupe_key": "20260819-am:信息选题:raw-1",
    }
    record.update(overrides)
    return record


def test_digest_windows_use_fixed_bjt_boundaries():
    morning = digest_window("morning", datetime(2026, 8, 19, 9, 34))
    assert morning.start == datetime(2026, 8, 18, 14, 30)
    assert morning.end == datetime(2026, 8, 19, 9, 34)
    assert morning.batch_time == datetime(2026, 8, 19, 9, 30)
    assert morning.batch_key == "20260819-am"

    afternoon = digest_window("afternoon", datetime(2026, 8, 19, 14, 35))
    assert afternoon.start == datetime(2026, 8, 19, 9, 30)
    assert afternoon.batch_time == datetime(2026, 8, 19, 14, 30)
    assert afternoon.batch_key == "20260819-pm"


def test_source_classification_is_readable():
    assert source_group("dajiala_wechat") == "重点公众号"
    assert source_group("github") == "GitHub 开源"
    assert source_group("unknown") == "其他信息源"


def test_translation_detection_only_targets_english_sentences():
    assert needs_chinese_translation("OpenAI launches a new agent platform for enterprise teams")
    assert needs_chinese_translation("OpenAI 发布新 agent platform for enterprise teams")
    assert not needs_chinese_translation("字节跳动发布新一代 AI 视频模型")
    assert not needs_chinese_translation("这是中文摘要 https://example.com/very-long-english-url")
    assert not needs_chinese_translation("Claude 新增 Gmail 与 Google Drive 连接器")
    assert not needs_chinese_translation("GPT-5")


class FakeTranslationClient:
    async def chat(self, messages, **kwargs):
        assert kwargs["json_mode"] is True
        return ChatResult(
            text="",
            parsed={
                "translations": [
                    {"id": 0, "title_zh": "OpenAI 发布企业智能体平台", "summary_zh": "该平台面向企业团队提供自动化能力。"}
                ]
            },
        )


@pytest.mark.asyncio
async def test_digest_translation_changes_only_english_fields():
    english = sample_record(
        title="OpenAI launches a new agent platform for enterprise teams",
        summary="The platform provides automation capabilities for enterprise teams.",
    )
    chinese = sample_record(title="国内 AI 行业迎来新变化", summary="这是一条中文摘要。")
    stats = await translate_digest_records(
        [english, chinese],
        llm_client=FakeTranslationClient(),
        batch_size=10,
    )
    assert english["title"] == "OpenAI 发布企业智能体平台"
    assert english["summary"] == "该平台面向企业团队提供自动化能力。"
    assert chinese["title"] == "国内 AI 行业迎来新变化"
    assert stats == {
        "candidate_records": 1,
        "translated_records": 1,
        "translated_titles": 1,
        "translated_summaries": 1,
        "failed_batches": 0,
    }


class FakeBackfillClient:
    def __init__(self):
        self.updated = []

    async def tenant_token(self):
        return "token"

    async def list_records(self, token):
        return [
            {
                "record_id": "rec_en",
                "fields": {
                    "标题": "OpenAI launches a new agent platform for enterprise teams",
                    "内容摘要": "The platform provides automation capabilities for enterprise teams.",
                },
            },
            {"record_id": "rec_zh", "fields": {"标题": "中文标题", "内容摘要": "中文摘要"}},
        ]

    async def batch_update(self, token, records):
        self.updated.extend(records)
        return len(records)


@pytest.mark.asyncio
async def test_backfill_updates_only_existing_english_text_fields():
    base = FakeBackfillClient()
    result = await backfill_existing_english_records(base, llm_client=FakeTranslationClient())
    assert result["records_checked"] == 2
    assert result["records_needing_translation"] == 1
    assert result["records_updated"] == 1
    assert base.updated == [{
        "record_id": "rec_en",
        "fields": {
            "标题": "OpenAI 发布企业智能体平台",
            "内容摘要": "该平台面向企业团队提供自动化能力。",
        },
    }]


def test_record_mapping_respects_field_types_and_existing_options():
    fields = [
        {"field_name": "标题", "type": 1},
        {"field_name": "采集时间", "type": 5},
        {"field_name": "推送批次", "type": 3, "property": {"options": [{"name": "上午 09:30"}, {"name": "下午 14:30"}]}},
        {"field_name": "内容分类", "type": 3, "property": {"options": [{"name": "信息选题"}]}},
        {"field_name": "信息源名称", "type": 1},
        {"field_name": "内容摘要", "type": 1},
        {"field_name": "选题价值", "type": 3, "property": {"options": [{"name": "高价值"}]}},
        {"field_name": "热度分", "type": 2},
        {"field_name": "处理状态", "type": 3, "property": {"options": [{"name": "待查看"}]}},
        {"field_name": "原文链接", "type": 15},
        {"field_name": "去重键", "type": 1},
    ]
    mapped = record_to_feishu_fields(sample_record(), fields)
    expected_ms = int(datetime(2026, 8, 19, 9, 30, tzinfo=BJT).timestamp() * 1000)
    assert mapped["标题"] == "AI 资讯标题"
    assert mapped["采集时间"] == expected_ms
    assert mapped["内容分类"] == "信息选题"
    assert mapped["推送批次"] == "上午 09:30"
    assert mapped["选题价值"] == "高价值"
    assert mapped["热度分"] == 88.5
    assert mapped["处理状态"] == "待查看"
    assert mapped["原文链接"] == {"link": "https://example.com/article", "text": "查看原文"}
    assert mapped["去重键"].endswith("raw-1")


def test_record_mapping_skips_select_value_not_present_in_schema():
    fields = [
        {"field_name": "标题", "type": 1},
        {"field_name": "内容分类", "type": 3, "property": {"options": [{"name": "潜在商单"}]}},
    ]
    mapped = record_to_feishu_fields(sample_record(), fields)
    assert mapped == {"标题": "AI 资讯标题"}


class FakeBaseClient:
    def __init__(self):
        self.created = []

    async def tenant_token(self):
        return "token"

    async def list_fields(self, token):
        assert token == "token"
        return [
            {"field_name": "标题", "type": 1},
            {"field_name": "内容分类", "type": 3, "property": {"options": [{"name": "信息选题"}]}},
            {"field_name": "去重键", "type": 1},
        ]

    async def existing_signatures(self, token):
        return {"key:20260819-am:信息选题:raw-1"}

    async def batch_create(self, token, records):
        self.created.extend(records)
        return len(records)


@pytest.mark.asyncio
async def test_sync_is_idempotent_by_dedupe_key():
    client = FakeBaseClient()
    result = await sync_digest_records(
        [sample_record(), sample_record(title="第二条", dedupe_key="20260819-am:信息选题:raw-2")],
        client=client,
    )
    assert result["selected"] == 2
    assert result["created"] == 1
    assert result["skipped_existing"] == 1
    assert client.created[0]["标题"] == "第二条"


def test_celery_schedule_runs_twice_daily():
    morning = CELERY_BEAT_SCHEDULE["feishu-digest-morning"]
    afternoon = CELERY_BEAT_SCHEDULE["feishu-digest-afternoon"]
    assert morning["task"] == "feishu_digest.publish"
    assert morning["kwargs"] == {"wave": "morning"}
    assert afternoon["kwargs"] == {"wave": "afternoon"}
    assert "30 9" in str(morning["schedule"])
    assert "30 14" in str(afternoon["schedule"])
