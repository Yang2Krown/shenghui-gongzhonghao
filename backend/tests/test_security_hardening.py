import pytest
from starlette.requests import Request

from app.main import _required_product_for_request
from app.core.progress import ProgressStore
from app.core.url_security import UnsafeURL, validate_public_http_url


def test_progress_store_requires_owner_for_snapshot():
    store = ProgressStore()
    run_id = store.create_run(user_id=1)

    assert store.can_access(run_id, 1) is True
    assert store.snapshot(run_id, user_id=1)["exists"] is True

    assert store.can_access(run_id, 2) is False
    assert store.snapshot(run_id, user_id=2) is None


def test_progress_store_legacy_unowned_run_is_not_readable():
    store = ProgressStore()
    run_id = store.create_run()

    assert store.exists(run_id) is True
    assert store.can_access(run_id, 1) is False
    assert store.snapshot(run_id, user_id=1) is None


def test_payment_order_close_endpoint_is_not_blocked_by_product_gate():
    request = Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/api/v1/credits/purchase/close/GZH123",
            "headers": [],
            "query_string": b"",
            "scheme": "http",
            "server": ("testserver", 80),
            "client": ("testclient", 1234),
            "root_path": "",
        }
    )

    assert _required_product_for_request(request) is None


@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1:8000/private",
        "http://localhost:8000/private",
        "http://10.0.0.5/private",
        "http://169.254.169.254/latest/meta-data",
        "file:///etc/passwd",
    ],
)
def test_validate_public_http_url_blocks_private_targets(url):
    with pytest.raises(UnsafeURL):
        validate_public_http_url(url)


def test_validate_public_http_url_allows_public_https(monkeypatch):
    monkeypatch.setattr(
        "app.core.url_security.socket.getaddrinfo",
        lambda *args, **kwargs: [(None, None, None, None, ("93.184.216.34", 0))],
    )

    assert validate_public_http_url("https://example.com/a") == "https://example.com/a"
