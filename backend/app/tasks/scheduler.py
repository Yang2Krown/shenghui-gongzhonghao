"""
任务调度模块
"""
import logging
from typing import List, Optional
from celery.schedules import crontab
from celery import current_app as celery_app

from app.core.config import settings

logger = logging.getLogger(__name__)


def setup_periodic_tasks():
    """设置周期性任务"""
    try:
        # 每日 6 点：全量抓取（RSS / GitHub / HackerNews / web / 公众号搜索）
        celery_app.add_periodic_task(
            crontab(hour=6, minute=0),
            "scraper.fetch_all_sources",
            name="daily-fetch-all",
        )

        # 每小时：只抓 RSS（便宜稳定）
        celery_app.add_periodic_task(
            crontab(minute=15),
            "scraper.fetch_rss_only",
            name="hourly-rss-fetch",
        )

        # 每 6 小时：跑一次公众号搜索（Exa 调用，控制频率）
        celery_app.add_periodic_task(
            crontab(hour="*/6", minute=30),
            "scraper.fetch_wechat_search",
            name="wechat-search-fetch",
        )

        # 每 30 分钟：预处理（embed + 聚类 + LLM 富集）
        celery_app.add_periodic_task(
            crontab(minute="*/30"),
            "preprocess.run_batch",
            name="preprocess-batch",
            kwargs={"limit": 100},
        )

        # 每 2 小时：批量挖掘选题（Agent A + B），单次最多 10 个簇
        celery_app.add_periodic_task(
            crontab(minute=45, hour="*/2"),
            "mining.run_batch",
            name="mining-batch",
            kwargs={"limit": 10, "min_heat_score": 4.0},
        )

        # 每天 22:00：生成第二天的 Daily Topic List
        celery_app.add_periodic_task(
            crontab(hour=22, minute=0),
            "ranking.generate_daily_list",
            name="daily-list-generation",
        )

        logger.info("周期性任务设置完成")
        
    except Exception as e:
        logger.error(f"设置周期性任务失败: {e}")
        raise


def get_scheduled_tasks() -> List[dict]:
    """获取已调度的任务列表"""
    try:
        tasks = []
        
        # 从Celery获取已注册的周期性任务
        inspector = celery_app.control.inspect()
        scheduled = inspector.scheduled()
        
        if scheduled:
            for worker, task_list in scheduled.items():
                for task in task_list:
                    tasks.append({
                        "worker": worker,
                        "task": task.get("name"),
                        "args": task.get("args"),
                        "kwargs": task.get("kwargs"),
                        "eta": task.get("eta")
                    })
        
        return tasks
        
    except Exception as e:
        logger.error(f"获取已调度任务失败: {e}")
        return []
