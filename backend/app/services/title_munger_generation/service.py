"""
芒格版标题生成 - 编排服务

实现 6 Agent 协作流程 + 回环机制（最多3轮）
"""

import logging
from typing import Dict, Any, List, Optional, Callable
from datetime import datetime

from app.services.title_munger_generation.agent_planner import PlannerAgent
from app.services.title_munger_generation.agent_gap import GapAgent
from app.services.title_munger_generation.agent_anchor import AnchorAgent
from app.services.title_munger_generation.agent_conflict import ConflictAgent
from app.services.title_munger_generation.agent_enhancer import EnhancerAgent
from app.services.title_munger_generation.agent_judge import JudgeAgent

logger = logging.getLogger(__name__)

MAX_LOOP_ROUNDS = 3


class MungerTitleGenerationService:
    """
    芒格版标题生成编排服务

    流程:
    Step 0: 策划 Agent - 定位语提取
    Step 1: 缺口/锚点/冲突 并行 - 三维度生成
    Step 2: 增强 Agent - 芒格倾向叠加
    Step 3: 审判 Agent - 拇指测试+红线+字数
    回环: 全部淘汰 → 注入失败原因 → 重试（≤3轮）
    """

    def __init__(self, progress_callback: Optional[Callable] = None):
        self.progress_callback = progress_callback
        self.planner = PlannerAgent()
        self.gap = GapAgent()
        self.anchor = AnchorAgent()
        self.conflict = ConflictAgent()
        self.enhancer = EnhancerAgent()
        self.judge = JudgeAgent()

    async def generate(self, content: str) -> Dict[str, Any]:
        """
        执行完整的标题生成流程

        Args:
            content: 文章全文或内容摘要

        Returns:
            生成结果
        """
        start_time = datetime.now()
        loop_count = 0
        all_failure_reasons = []

        while loop_count < MAX_LOOP_ROUNDS:
            loop_count += 1
            logger.info(f"===== 芒格版标题生成 第 {loop_count} 轮 =====")

            await self._notify({"event": "step_start", "data": {
                "step": 0, "agent": "策划 Agent", "action": "正在提取定位语...",
                "round": loop_count, "max_rounds": MAX_LOOP_ROUNDS,
            }})

            # Step 0: 策划 Agent
            feedback = "\n".join(all_failure_reasons) if all_failure_reasons else ""
            plan_result = await self.planner.extract_positioning(content, feedback)
            positioning = plan_result.get("positioning", "")
            if not positioning:
                logger.error("策划 Agent 未生成定位语")
                await self._notify({"event": "error", "data": {"message": "策划 Agent 未生成定位语"}})
                break

            logger.info(f"定位语: {positioning}")
            await self._notify({"event": "step_done", "data": {"step": 0, "agent": "策划 Agent"}})

            # Step 1: 三维度并行
            dim_steps = [
                (1, "缺口 Agent", "正在生成信息缺口标题...", self.gap, "gap"),
                (1, "锚点 Agent", "正在生成社会位置标题...", self.anchor, "anchor"),
                (1, "冲突 Agent", "正在生成认知冲突标题...", self.conflict, "conflict"),
            ]

            all_titles = []

            for step_num, agent_name, action, agent_instance, key in dim_steps:
                await self._notify({"event": "step_start", "data": {
                    "step": step_num, "agent": agent_name, "action": action,
                    "round": loop_count,
                }})
                result = await agent_instance.execute(positioning=positioning)
                titles = result.get("titles", [])
                all_titles.extend(titles)
                await self._notify({"event": "step_done", "data": {"step": step_num, "agent": agent_name}})

            logger.info(f"Step 1 共产出 {len(all_titles)} 条标题")
            if not all_titles:
                logger.error("Step 1 未生成任何标题")
                break

            # Step 2: 增强 Agent
            await self._notify({"event": "step_start", "data": {
                "step": 2, "agent": "增强 Agent", "action": "正在芒格倾向叠加...",
                "round": loop_count,
            }})
            enhance_result = await self.enhancer.enhance_titles(all_titles)
            top5 = enhance_result.get("top5", [])
            await self._notify({"event": "step_done", "data": {"step": 2, "agent": "增强 Agent"}})

            if not top5:
                logger.error("增强 Agent 未输出 Top 5")
                all_failure_reasons.append("增强后标题为空")
                continue

            # Step 3: 审判 Agent
            await self._notify({"event": "step_start", "data": {
                "step": 3, "agent": "审判 Agent", "action": "正在拇指测试+红线审查...",
                "round": loop_count,
            }})
            verdict_result = await self.judge.verdict(top5)
            await self._notify({"event": "step_done", "data": {"step": 3, "agent": "审判 Agent"}})

            # 检查是否通过
            if not verdict_result.get("all_rejected", True):
                # 有通过的标题
                end_time = datetime.now()
                duration = (end_time - start_time).total_seconds()

                await self._notify({"event": "complete", "data": {
                    "step": 3, "agent": "审判 Agent",
                    "loop_count": loop_count,
                }})

                return {
                    "success": True,
                    "positioning": positioning,
                    "all_titles": all_titles,
                    "top5": top5,
                    "verdicts": verdict_result.get("verdicts", []),
                    "final_pick": verdict_result.get("final_pick", ""),
                    "loop_count": loop_count,
                    "duration_seconds": duration,
                }

            # 全部淘汰：提取失败原因，继续循环
            reasons = verdict_result.get("failure_reasons", [])
            reason_text = "; ".join(reasons) if reasons else "全部标题未通过审核"
            all_failure_reasons.append(f"第{loop_count}轮失败: {reason_text}")
            logger.warning(f"第{loop_count}轮全部淘汰: {reason_text}")

        # 超出最大轮次或异常退出
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()

        return {
            "success": False,
            "positioning": positioning if "positioning" in dir() else "",
            "all_titles": all_titles if "all_titles" in dir() else [],
            "top5": top5 if "top5" in dir() else [],
            "verdicts": verdict_result.get("verdicts", []) if "verdict_result" in dir() else [],
            "final_pick": "",
            "loop_count": loop_count,
            "failure_reasons": all_failure_reasons,
            "duration_seconds": duration,
            "message": f"经过{loop_count}轮仍未生成通过审核的标题",
        }

    async def _notify(self, event: dict):
        """推送进度事件"""
        if self.progress_callback:
            await self.progress_callback(event)
