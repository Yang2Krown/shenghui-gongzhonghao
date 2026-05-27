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
    # ── AI HOT（独立于通用 RSS 链路）──
    # 精选：每 2 小时
    "aihot-selected": {
        "task": "scraper.fetch_aihot",
        "schedule": crontab(minute=15, hour="*/2"),
        "kwargs": {"feed_key": "selected"},
    },
    # 全部：上午 10:00 + 下午 16:00
    "aihot-all-morning": {
        "task": "scraper.fetch_aihot",
        "schedule": crontab(minute=0, hour=10),
        "kwargs": {"feed_key": "all"},
    },
    "aihot-all-afternoon": {
        "task": "scraper.fetch_aihot",
        "schedule": crontab(minute=0, hour=16),
        "kwargs": {"feed_key": "all"},
    },
    # 日报：每天 8:30（人家 8:00 更新）
    "aihot-daily": {
        "task": "scraper.fetch_aihot",
        "schedule": crontab(minute=30, hour=8),
        "kwargs": {"feed_key": "daily"},
    },
}
