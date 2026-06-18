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

    # ── 公众号案例源：独立高频小批量（防搜狗反爬）──
    # 不混进上面 5 波大派发——那样会和 sogou_wechat_search 在同一波里把搜狗 burst 拉高，
    # 触发 IP 风控。改成每 30 分钟单独跑一次，每次只搜一小批账号（rotate_batch），
    # 按时间片轮转，几小时内覆盖全部 29 个号，但单次请求量小。
    "sogou-cases-rotate": {
        "task": "scraper.fetch_platform",
        "schedule": crontab(minute="5,35"),
        "kwargs": {"platform": "sogou_wechat_cases"},
    },

    # ── 预处理：每 30 分钟一小批，滚动消化 pending ──
    # 不再每 2 小时一次 limit=500 硬啃——那样配合全文抓取容易撑爆 25 分钟软超时直接崩溃，
    # 导致整批数据进不了话题。改成小批量高频：每批 120 条，积压多时分多趟跑完，
    # 单趟稳稳在超时内，前端也能更快看到新话题。
    "preprocess-cycle": {
        "task": "preprocess.run_batch",
        "schedule": crontab(minute="*/30"),
        "kwargs": {"limit": 120},
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

    # ── X (Twitter) via twitterapi.io：独立调度，不混进上面 5 波 ──
    # 博主订阅：每天 1 次（按用户要求）。58 个号在一次任务内并发 3 + 抖动细水长流，不一次性炸出去。
    "x-accounts-daily": {
        "task": "scraper.fetch_platform",
        "schedule": crontab(minute=0, hour=7),
        "kwargs": {"platform": "x"},
    },
    # 关键词搜索：每 4 小时一次，配合 fetch_config.rotate_batch 每次只搜一小批主题词，
    # 一天覆盖一轮全部中英文关键词；单次请求量小，省钱也防限流。
    "x-search-rotate": {
        "task": "scraper.fetch_platform",
        "schedule": crontab(minute=20, hour="*/4"),
        "kwargs": {"platform": "x_search"},
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

    # ── 信息库清理：每天凌晨 4:10 删 14 天前、没人挖掘/创作过的旧资讯 ──
    "cleanup-stale-clusters": {
        "task": "cleanup.purge_stale_clusters",
        "schedule": crontab(minute=10, hour=4),
        "kwargs": {"days": 14},
    },
}
