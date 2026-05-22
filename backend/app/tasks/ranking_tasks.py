"""全局排序 Celery 任务。

定时生成每日选题清单。
"""

import logging
from datetime import date

from app.core.celery_app import celery_app
from app.services.ranking_service import generate_daily_list

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, name="ranking.generate_daily_list", max_retries=1)
def generate_daily_list_task(self, target_date_str: str = None) -> dict:
    """生成每日选题清单任务。

    Args:
        target_date_str: 目标日期字符串 (YYYY-MM-DD)，默认今天

    Returns:
        {"list_id": int, "date": str, "count": int, ...}
    """
    try:
        target_date = None
        if target_date_str:
            target_date = date.fromisoformat(target_date_str)

        result = generate_daily_list(target_date=target_date, top_n=10)
        logger.info(f"每日清单任务完成: {result}")
        return result
    except Exception as exc:
        logger.exception(f"每日清单任务失败: {exc}")
        raise self.retry(exc=exc)
