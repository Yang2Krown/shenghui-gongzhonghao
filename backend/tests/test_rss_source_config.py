from unittest.mock import AsyncMock, patch

import pytest

from app.db.seeds.seed_source_changes_2026 import NEW_RSS, _slug_platform
from app.models.source_registry import SourceRegistry
from app.services.scraping.adapters.rss_adapter import RSSAdapter


XIAOHU_RSS_URL = "https://best.xiaohu.ai/rss.xml"


def test_xiaohu_rss_is_in_source_seed():
    row = next(row for row in NEW_RSS if row[1] == XIAOHU_RSS_URL)

    assert row == ("小互 · AI 解读站", XIAOHU_RSS_URL, "AI")
    assert _slug_platform(row[0]) == "rss_小互_·_AI_解读站"


@pytest.mark.asyncio
async def test_rss_adapter_maps_xiaohu_entry():
    source = SourceRegistry(
        name="小互 · AI 解读站",
        platform="rss_小互_·_AI_解读站",
        source_type="rss",
        url=XIAOHU_RSS_URL,
        fetch_config={"limit": 1},
    )
    entry = {
        "title": "测试标题",
        "url": "https://best.xiaohu.ai/article/test/",
        "summary": "测试摘要",
        "published": "Wed, 05 Aug 2026 00:00:00 -0000",
    }

    with patch(
        "app.services.scraping.adapters.rss_adapter.agent_reach_client.fetch_rss",
        new=AsyncMock(return_value=[entry]),
    ) as fetch_rss:
        items = await RSSAdapter().fetch(source)

    assert fetch_rss.call_args.args == (XIAOHU_RSS_URL,)
    assert fetch_rss.call_args.kwargs == {"limit": 1}
    assert len(items) == 1
    assert items[0].title == "测试标题"
    assert items[0].url == entry["url"]
    assert items[0].summary == "测试摘要"
    assert items[0].published_at.isoformat() == "2026-08-05T00:00:00"
