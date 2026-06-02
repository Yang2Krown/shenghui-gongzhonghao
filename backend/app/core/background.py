"""后台任务工具。

直接用 `asyncio.create_task(coro)` 而不保存返回值有个隐患：事件循环只持有
任务的弱引用，任务可能在执行过程中被垃圾回收掉（Python 官方文档明确警告）。
表现就是"本地能跑、生产偶尔整个后台任务不执行"。

`spawn()` 在模块级集合里持有强引用，任务结束后再移除，杜绝这个问题。
"""

import asyncio
import logging
from typing import Coroutine

logger = logging.getLogger(__name__)

# 持有运行中的后台任务的强引用，防止被 GC 回收
_background_tasks: set[asyncio.Task] = set()


def spawn(coro: Coroutine) -> asyncio.Task:
    """创建后台任务并持有强引用，直到任务结束。"""
    task = asyncio.create_task(coro)
    _background_tasks.add(task)

    def _on_done(t: asyncio.Task) -> None:
        _background_tasks.discard(t)
        if t.cancelled():
            logger.warning("后台任务被取消: %r", t)
        else:
            exc = t.exception()
            if exc is not None:
                logger.error("后台任务异常: %r", exc, exc_info=exc)
            else:
                logger.info("后台任务完成: %r", t)

    task.add_done_callback(_on_done)
    return task
