from app.core.admin_permissions import has_permission
from app.core.celery_monitor import task_category, task_queue
from app.models.user import User
from app.services.monitoring.celery_tasks import _build_queue_stats


def test_celery_task_categories_and_queues():
    assert task_category("scraper.fetch_platform") == "scraping"
    assert task_category("content.generate_article") == "ai"
    assert task_category("publish.send_article") == "publish"
    assert task_category("monitoring.system_check") == "default"
    assert task_queue("scraper.fetch_platform") == "scraping"
    assert task_queue("monitoring.system_check", "default") == "default"


def test_queue_stats_merge_active_reserved_and_scheduled():
    result = _build_queue_stats({
        "active": {"worker-ai": [{"name": "content.generate_article", "delivery_info": {"routing_key": "ai"}}]},
        "reserved": {"worker-scrape": [{"name": "scraper.fetch_platform", "delivery_info": {"routing_key": "scraping"}}]},
        "scheduled": {"worker-default": [{"request": {"name": "monitoring.system_check", "delivery_info": {"routing_key": "default"}}}]},
        "stats": {},
    })
    by_queue = {item["queue"]: item for item in result}
    assert by_queue["ai"]["active"] == 1
    assert by_queue["scraping"]["waiting"] == 1
    assert by_queue["default"]["scheduled"] == 1


def test_task_retry_permission_is_admin_only():
    admin = User(id=1, username="admin", role="admin", is_superuser=False, is_active=True)
    normal = User(id=2, username="normal", role="user", is_superuser=False, is_active=True)
    assert has_permission(admin, "tasks:retry") is True
    assert has_permission(normal, "tasks:retry") is False
