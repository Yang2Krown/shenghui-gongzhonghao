"""Celery 应用单例。

集中定义 celery_app，让所有 task 文件 import 同一个实例。
- broker / backend 从 settings 读
- 自动发现 app.tasks.* 里的任务
"""

from celery import Celery

from app.core.config import settings
from app.tasks.scheduler import CELERY_BEAT_SCHEDULE


celery_app = Celery(
    "gzh",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
)

# 让 @celery_app.task 和 @shared_task 都挂到同一个实例
celery_app.set_default()

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Shanghai",
    enable_utc=False,
    task_track_started=True,
    task_time_limit=60 * 30,          # 30 分钟硬超时
    task_soft_time_limit=60 * 25,     # 25 分钟软超时
    worker_max_tasks_per_child=200,   # 每个 worker 跑 200 个任务后重启（防内存泄漏）
    broker_connection_retry_on_startup=True,
    beat_schedule=CELERY_BEAT_SCHEDULE,
    task_send_sent_event=True,
    task_default_queue="default",
    task_routes={
        "scraper.*": {"queue": "scraping"},
        "preprocess.*": {"queue": "ai"},
        "mining.*": {"queue": "ai"},
        "commercial.*": {"queue": "ai"},
        "ai.*": {"queue": "ai"},
        "content.*": {"queue": "ai"},
        "title.*": {"queue": "ai"},
        "outline.*": {"queue": "ai"},
        "publish.*": {"queue": "publish"},
        "xhs.publish*": {"queue": "publish"},
        "xhs.analyze_notes": {"queue": "ai"},
        "xhs.rebuild_semantic_topics": {"queue": "ai"},
        "xhs.generate_dynamic_keywords": {"queue": "ai"},
        "xhs.evaluate_keyword_lifecycle": {"queue": "ai"},
        "xhs.*": {"queue": "scraping"},
    },
)

# 显式导入任务模块，确保 @shared_task 注册到 celery_app
import app.tasks.scraper_tasks  # noqa: F401,E402
import app.tasks.preprocess_tasks  # noqa: F401,E402
import app.tasks.topic_mining_tasks  # noqa: F401,E402
import app.tasks.commercial_tasks  # noqa: F401,E402
import app.tasks.cleanup_tasks  # noqa: F401,E402
import app.tasks.subscription_tasks  # noqa: F401,E402
import app.tasks.monitoring_tasks  # noqa: F401,E402
import app.tasks.xhs_tasks  # noqa: F401,E402
import app.core.celery_monitor  # noqa: F401,E402

__all__ = ["celery_app"]
