"""
任务调度模块

全网采集按 source_type 拆分成独立任务，每个类型失败互不影响。
AI HOT 保持独立链路，频率更高（每 2h 精选）。
"""
from celery.schedules import crontab


CELERY_BEAT_SCHEDULE = {
    # ── 全网采集：按 source_type 分批，错开 5 分钟 ──
    # RSS 类（轻量、稳定，最早跑）
    "fetch-rss": {
        "task": "scraper.fetch_source_type",
        "schedule": crontab(hour=6, minute=0),
        "kwargs": {"source_type": "rss"},
    },
    "fetch-github": {
        "task": "scraper.fetch_source_type",
        "schedule": crontab(hour=6, minute=5),
        "kwargs": {"source_type": "github"},
    },
    "fetch-hackernews": {
        "task": "scraper.fetch_source_type",
        "schedule": crontab(hour=6, minute=10),
        "kwargs": {"source_type": "hackernews"},
    },
    "fetch-tophub": {
        "task": "scraper.fetch_source_type",
        "schedule": crontab(hour=6, minute=15),
        "kwargs": {"source_type": "tophub"},
    },
    "fetch-v2ex": {
        "task": "scraper.fetch_source_type",
        "schedule": crontab(hour=6, minute=20),
        "kwargs": {"source_type": "v2ex"},
    },
    "fetch-reddit": {
        "task": "scraper.fetch_source_type",
        "schedule": crontab(hour=6, minute=25),
        "kwargs": {"source_type": "reddit"},
    },
    "fetch-xhs-daily": {
        "task": "scraper.fetch_source_type",
        "schedule": crontab(hour=6, minute=30),
        "kwargs": {"source_type": "xhs_daily"},
    },
    "fetch-gzh-explosive": {
        "task": "scraper.fetch_source_type",
        "schedule": crontab(hour=6, minute=35),
        "kwargs": {"source_type": "gzh_explosive"},
    },
    # 搜狗微信搜索（替代 exa_wechat，国内无障碍）
    "fetch-sogou-wechat": {
        "task": "scraper.fetch_source_type",
        "schedule": crontab(hour=6, minute=40),
        "kwargs": {"source_type": "sogou_wechat"},
    },
    # 重量级（需要 Exa API / Playwright，放后面）
    "fetch-exa-wechat": {
        "task": "scraper.fetch_source_type",
        "schedule": crontab(hour=6, minute=45),
        "kwargs": {"source_type": "exa_wechat"},
    },
    "fetch-x-playwright": {
        "task": "scraper.fetch_source_type",
        "schedule": crontab(hour=6, minute=50),
        "kwargs": {"source_type": "x_playwright"},
    },

    # ── 预处理 ──
    # 07:00 预处理：raw_info → InfoCluster（给采集留 1 小时窗口）
    "morning-preprocess": {
        "task": "preprocess.run_batch",
        "schedule": crontab(hour=7, minute=0),
        "kwargs": {"limit": 500},
    },
    # 08:00 兜底再跑一次预处理（小批次，防超时）
    "morning-preprocess-fallback": {
        "task": "preprocess.run_batch",
        "schedule": crontab(hour=8, minute=0),
        "kwargs": {"limit": 500},
    },
    # 09:00 重算所有活跃 cluster 的 heat_score（让排序反映最新状态）
    "morning-rescore": {
        "task": "preprocess.rescore",
        "schedule": crontab(hour=9, minute=0),
    },

    # ── AI HIGH 独立链路（频率更高，与全网采集解耦）──
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
