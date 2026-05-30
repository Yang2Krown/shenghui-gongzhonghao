"""
任务调度模块

时间全部为北京时间（celery 配置 timezone="Asia/Shanghai" + enable_utc=False）。

采集 / 预处理策略（鲁棒性优先）：
- 采集：每天 5 波（06/10/14/18/22 点）。每波由"派发器"把每个启用源拆成独立子任务，
  错峰 90 秒一个。每源独立抓取、独立提交、独立重试——任一源/任一波出问题，
  下一波自动补上，白天新发布的内容也能当天采到。
- 预处理：每 2 小时一趟，新采集的 raw_info 很快变成话题，前端尽快可见，
  不用等到第二天。
- 重算热度 + 回填低粉标记：中午、深夜各一次。
- AI HOT 保持独立链路，频率更高。
"""
from celery.schedules import crontab


CELERY_BEAT_SCHEDULE = {
    # ── 采集：每天 5 波，错峰派发每个源 ──
    "dispatch-fetch": {
        "task": "scraper.dispatch_fetch",
        "schedule": crontab(minute=0, hour="6,10,14,18,22"),
        "kwargs": {"gap_seconds": 90},
    },

    # ── 预处理：每 2 小时一趟（:30），raw_info → InfoCluster ──
    "preprocess-cycle": {
        "task": "preprocess.run_batch",
        "schedule": crontab(minute=30, hour="*/2"),
        "kwargs": {"limit": 500},
    },

    # ── 重算热度 + 回填低粉爆款标记：中午 + 深夜 ──
    "rescore-midday": {
        "task": "preprocess.rescore",
        "schedule": crontab(minute=0, hour=12),
    },
    "rescore-night": {
        "task": "preprocess.rescore",
        "schedule": crontab(minute=50, hour=23),
    },

    # ── AI HOT 独立链路（频率更高，与全网采集解耦）──
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
