"""Smoke test: 直接调用 TitleGenerationService 跑一遍 4-agent 流水线。

用法： python -m scripts.smoke_title_generation
需要 .env 已配置 DEEPSEEK_API_KEY 或 ANTHROPIC_API_KEY，且 LLM_PROVIDER 对齐。
"""

import asyncio
import logging
import sys
import uuid
from datetime import datetime

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("smoke")


async def main() -> int:
    # 延迟导入，触发 settings 校验
    from app.db.session import AsyncSessionLocal
    from app.models.task import Task, TaskStatus
    from app.schemas.title_generation import (
        TitleGenerationRequest, TopicInfo, OutlineInfo,
    )
    from app.services.title_generation_service import TitleGenerationService

    request = TitleGenerationRequest(
        topic=TopicInfo(
            title="复刻Ramp工程师：用Codex把代码审查从小时缩到分钟",
            direction="实践型",
            method="复刻挑战型",
            value_promise="给读者一份可落地的 Codex 代码审查工作流，把 PR review 时间从小时级压到分钟级",
        ),
        outline=OutlineInfo(
            section_titles=[
                "Ramp 工程师为什么说代码审查从小时缩到分钟",
                "5 条判断标准：哪些 PR 适合让 Codex 先过一遍",
                "完整工作流：从 prompt 模板到 reviewer 手动复核",
                "三个翻车现场和复盘",
                "今天就能用的 Codex 提示词清单",
            ],
            key_points=[
                "Ramp 工程师案例数据：审查时长从 1.5h → 12min",
                "5 条 PR 适配标准：函数级、纯逻辑、无配置变更等",
                "Codex prompt 模板：context 注入 + 风险扫描 + 改动摘要",
                "失败案例：Codex 漏检的边界场景",
                "可复制提示词清单（4 条）",
            ],
            spread_tags=["实用清单", "案例驱动", "工具升级"],
        ),
    )

    task_id = str(uuid.uuid4())

    async with AsyncSessionLocal() as db:
        task = Task(
            id=task_id,
            title=f"[smoke] {request.topic.title}",
            description="smoke test",
            status=TaskStatus.PENDING,
            input_data={
                "topic": request.topic.dict(),
                "outline": request.outline.dict(),
            },
        )
        db.add(task)
        await db.commit()
        log.info(f"创建测试 task: {task_id}")

    events = []

    async def progress_cb(event):
        events.append(event)
        log.info(f"[progress] {event.get('event')}: {str(event.get('data'))[:120]}")

    async with AsyncSessionLocal() as db:
        service = TitleGenerationService(db, progress_callback=progress_cb)
        try:
            await service.execute_title_generation(task_id=task_id, request=request)
        except Exception as e:
            log.exception(f"流水线异常: {e}")
            return 1

    # 检查最终状态
    async with AsyncSessionLocal() as db:
        from sqlalchemy import select
        from app.models.task import Task as T
        row = (await db.execute(select(T).where(T.id == task_id))).scalar_one()
        log.info(f"最终状态: {row.status} | error: {row.error_message}")
        if row.status == TaskStatus.FAILED:
            return 2

    log.info(f"流水线完成 ✅ 共 {len(events)} 个进度事件")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
