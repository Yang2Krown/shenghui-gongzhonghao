from types import SimpleNamespace

import pytest

from app.services.scraping.adapters.x_twitterapi_adapter import (
    TwitterApiCreditsExhausted,
    XTwitterApiAdapter,
)


@pytest.mark.asyncio
async def test_credit_exhaustion_stops_remaining_accounts(monkeypatch):
    source = SimpleNamespace(
        platform="x",
        fetch_config={"min_interval_sec": 0, "concurrency": 1},
        auth_status="ok",
    )
    accounts = [
        SimpleNamespace(handle=f"account_{index}", id=index)
        for index in range(5)
    ]
    adapter = XTwitterApiAdapter()
    calls = []

    async def no_sleep(_delay):
        return None

    async def credits_exhausted(*args, **kwargs):
        calls.append(args[2])
        raise TwitterApiCreditsExhausted("credits is not enough")

    monkeypatch.setenv("TWITTERAPI_IO_KEY", "test-key")
    monkeypatch.setattr("asyncio.sleep", no_sleep)
    monkeypatch.setattr(adapter, "_user_tweets", credits_exhausted)

    with pytest.raises(TwitterApiCreditsExhausted):
        await adapter.fetch(source, accounts=accounts)

    assert calls == ["account_0"]
    assert source.auth_status == "expired"
