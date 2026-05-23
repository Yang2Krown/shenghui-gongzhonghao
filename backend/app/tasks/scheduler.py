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
    """设置周期性任务。

    设计：每日早上自动抓取 + 入库到话题库（不挖掘候选选题）。
    候选选题挖掘由用户在前端"立即挖掘"按钮手动触发。
    """
    try:
        # 每日 6 点：全量抓取（RSS / GitHub / HackerNews / web / 公众号搜索）
        celery_app.add_periodic_task(
            crontab(hour=6, minute=0),
            "scraper.fetch_all_sources",
            name="daily-fetch-all",
        )

        # ┌─────────────────────────────────────────────────┐
        # │ 06:30 — 预处理：raw_info → InfoCluster           │
        # │  embed + 聚类 + LLM 富集 + 翻译                  │
        # │  跑完话题库就有当天的新话题                       │
        # └─────────────────────────────────────────────────┘
        celery_app.add_periodic_task(
            crontab(hour=6, minute=30),
            "preprocess.run_batch",
            name="morning-preprocess",
            kwargs={"limit": 2000},
        )

        # ┌─────────────────────────────────────────────────┐
        # │ 07:30 — 兜底再跑一次预处理                       │
        # │  如果 6:30 因 LLM 限流没跑完，这一轮收尾          │
        # └─────────────────────────────────────────────────┘
        celery_app.add_periodic_task(
            crontab(hour=7, minute=30),
            "preprocess.run_batch",
            name="morning-preprocess-fallback",
            kwargs={"limit": 2000},
        )

        # ──── 以下不自动跑 ────
        # mining (Agent A/B 挖掘候选选题) → 前端"立即挖掘"按钮手动触发
        # generate_daily_list → 等挖掘后手动生成

        logger.info("周期性任务设置完成（每日 6:00 抓取 + 6:30 / 7:30 预处理，不自动挖掘）")
        
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
