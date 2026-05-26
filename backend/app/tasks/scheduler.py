"""
任务调度模块
"""
from celery.schedules import crontab


CELERY_BEAT_SCHEDULE = {
    # 每日 6:00 全量抓取
    "daily-fetch-all": {
        "task": "scraper.fetch_all_sources",
        "schedule": crontab(hour=6, minute=0),
    },
    # 06:30 预处理：raw_info → InfoCluster
    "morning-preprocess": {
        "task": "preprocess.run_batch",
        "schedule": crontab(hour=6, minute=30),
        "kwargs": {"limit": 2000},
    },
    # 07:30 兜底再跑一次预处理
    "morning-preprocess-fallback": {
        "task": "preprocess.run_batch",
        "schedule": crontab(hour=7, minute=30),
        "kwargs": {"limit": 2000},
    },
}
