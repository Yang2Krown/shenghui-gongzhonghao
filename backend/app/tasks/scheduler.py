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
    # ── 飞书内容资讯日报：按北京时间写入同一张多维表格 ──
    "feishu-digest-morning": {
        "task": "feishu_digest.publish",
        "schedule": crontab(minute=30, hour=9),
        "kwargs": {"wave": "morning"},
    },
    "feishu-digest-afternoon": {
        "task": "feishu_digest.publish",
        "schedule": crontab(minute=30, hour=14),
        "kwargs": {"wave": "afternoon"},
    },
    # ── 小红书集中采集：每天上午一波（TikHub 付费通道，本地 CLI 已弃用）──
    # 基础词按 schedule_group 分波，前端默认 1；为不依赖具体分组，覆盖 1-6 全组。
    # 每个词错峰 90s 派发，detail 兜底≈0，单波 ≈ 关键词数 次 TikHub search。
    "xhs-collect-morning": {
        "task": "xhs.dispatch_group",
        "schedule": crontab(minute=0, hour=8),
        "kwargs": {"group": 1},
    },
    "xhs-collect-morning-g2": {
        "task": "xhs.dispatch_group",
        "schedule": crontab(minute=2, hour=8),
        "kwargs": {"group": 2},
    },
    "xhs-collect-morning-g3": {
        "task": "xhs.dispatch_group",
        "schedule": crontab(minute=4, hour=8),
        "kwargs": {"group": 3},
    },
    # 动态衍生词：补充采集（每日最多 5 个，过冷却期的才跑）。
    "xhs-collect-derived": {
        "task": "xhs.dispatch_derived",
        "schedule": crontab(minute=6, hour=8),
    },
    # 采集后生成「每日热点 + 持续发酵」总结：上午采集错峰 ~30min 内完成，10:00 重建成型。
    "xhs-topic-after-morning-collect": {
        "task": "xhs.rebuild_semantic_topics",
        "schedule": crontab(minute=0, hour=10),
        "kwargs": {"wave": "morning"},
    },
    # 搜索采集已由本地 Mac Agent 接管；服务器只保留关键词生成和素材分析。
    "xhs-note-analysis": {"task": "xhs.analyze_notes", "schedule": crontab(minute=0, hour="13,18")},
    "xhs-dynamic-generate": {"task": "xhs.generate_dynamic_keywords", "schedule": crontab(minute=20, hour=18)},
    "xhs-keyword-lifecycle": {"task":"xhs.evaluate_keyword_lifecycle","schedule":crontab(minute=25,hour=18)},
    # ── 采集：每天 5 波，错峰派发每个源 ──
    "dispatch-fetch": {
        "task": "scraper.dispatch_fetch",
        "schedule": crontab(minute=0, hour="6,10,14,18,22"),
        "kwargs": {"gap_seconds": 90},
    },

    # ── 固定公众号博主：极致了当天发文接口 ──
    # 每天晚间查一次当天发文；历史补库不进 beat，避免 post_history 被定时误扣费。
    "dajiala-wechat-cases-daily": {
        "task": "scraper.fetch_platform",
        "schedule": crontab(minute=20, hour=23),
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

    # 小红书前端只展示近 7 天；同步删除更早或已淘汰素材的本地图片缓存。
    "xhs-cleanup-media-cache": {
        "task": "xhs.cleanup_media_cache",
        "schedule": crontab(minute=25, hour=4),
        "kwargs": {"days": 7},
    },

    # 封面/头像自愈：媒体原本懒加载（查看时才拉取），而 xhscdn 签名 URL 短时效，
    # 过期即 403 → 封面失败。周期性为可展示素材补齐缺失缓存，趁 URL 相对新鲜预取。
    # 每小时跑一次 + 单次拉取硬上限，已缓存的跳过，实际回源量极小，对 CDN 无压力。
    "xhs-warm-media-cache": {
        "task": "xhs.warm_media_cache",
        "schedule": crontab(minute=15),
        "kwargs": {"days": 7},
    },

    # ── 创作工具订阅到期：每天凌晨 4:20 处理到期订阅（仅移除权益，积分永久保留）──
    "subscription-expire-due": {
        "task": "subscription.expire_due",
        "schedule": crontab(minute=20, hour=4),
    },

    # ── 管理员后台监测：内容供给链路、任务失败、用户健康概览 ──
    "monitor-system": {
        "task": "monitoring.system_check",
        "schedule": crontab(minute="*/10"),
    },

    # ── 接口健康日志清理：保留 30 天，避免线上请求日志无限增长 ──
    "cleanup-api-request-logs": {
        "task": "monitoring.cleanup_api_request_logs",
        "schedule": crontab(minute=35, hour=4),
        "kwargs": {"days": 30},
    },

    # ── LLM 成本日志清理：保留 90 天，兼顾趋势分析和库体积 ──
    "cleanup-llm-call-logs": {
        "task": "monitoring.cleanup_llm_call_logs",
        "schedule": crontab(minute=45, hour=4),
        "kwargs": {"days": 90},
    },
}
