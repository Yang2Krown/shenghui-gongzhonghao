import pytest
from fastapi import HTTPException

from app.api.v1 import auth
from app.schemas.user import TokenRefresh


class FakeUser:
    id = 123
    is_active = True


@pytest.mark.asyncio
async def test_refresh_keeps_old_token_when_new_pair_cannot_be_issued(monkeypatch):
    monkeypatch.setattr(auth, "decode_token", lambda _token: {
        "type": "refresh",
        "jti": "old-jti",
        "sub": "123",
    })
    monkeypatch.setattr(auth.user_crud, "get", lambda *_args, **_kwargs: _return_user())
    monkeypatch.setattr(auth, "is_refresh_token_active", _active_token)
    revoke = _record_revoke()
    monkeypatch.setattr(auth, "revoke_refresh_token", revoke)

    async def fail_to_issue(_user_id):
        raise HTTPException(status_code=503, detail="刷新令牌服务暂不可用")

    monkeypatch.setattr(auth, "_issue_token_pair", fail_to_issue)

    with pytest.raises(HTTPException) as exc_info:
        await auth.refresh_token(TokenRefresh(refresh_token="old-refresh"), db=object())

    assert exc_info.value.status_code == 503
    assert revoke.calls == []


@pytest.mark.asyncio
async def test_refresh_issues_new_pair_before_revoking_old(monkeypatch):
    monkeypatch.setattr(auth, "decode_token", lambda _token: {
        "type": "refresh",
        "jti": "old-jti",
        "sub": "123",
    })
    monkeypatch.setattr(auth.user_crud, "get", lambda *_args, **_kwargs: _return_user())
    monkeypatch.setattr(auth, "is_refresh_token_active", _active_token)

    events = []

    async def issue_pair(_user_id):
        events.append("issue")
        return {"access_token": "new-access", "refresh_token": "new-refresh", "token_type": "bearer"}

    async def revoke_old(_jti):
        events.append("revoke")

    monkeypatch.setattr(auth, "_issue_token_pair", issue_pair)
    monkeypatch.setattr(auth, "revoke_refresh_token", revoke_old)

    result = await auth.refresh_token(TokenRefresh(refresh_token="old-refresh"), db=object())

    assert events == ["issue", "revoke"]
    assert result["data"]["access_token"] == "new-access"


async def _return_user(*_args, **_kwargs):
    return FakeUser()


async def _active_token(*_args, **_kwargs):
    return True


def _record_revoke():
    async def revoke(*args, **kwargs):
        revoke.calls.append((args, kwargs))

    revoke.calls = []
    return revoke
