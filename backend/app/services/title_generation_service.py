"""
标题生成服务

实现4 Agent协作流程的核心业务逻辑。
"""

import uuid
from datetime import datetime
from typing import Callable, List, Dict, Any, Optional
import logging

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.task import Task, TaskStatus
from app.models.title import TitleGenerationResult, TitleCandidate, FinalRecommendation
from app.models.agent import AgentLog
from app.schemas.title_generation import (
    TitleGenerationRequest,
    TopicInfo,
    OutlineInfo,
)
from app.services.title_generation import (
    TitleCreatorAgent,
    TitleReviewerAgent,
    ClickPredictorAgent,
    FinalJudgeAgent,
)
from app.core.config import settings

logger = logging.getLogger(__name__)


class TitleGenerationService:
    """
    标题生成服务
    
    负责编排4个Agent的协作流程，实现完整的标题生成流水线。
    """
    
    def __init__(self, db: AsyncSession, progress_callback: Optional[Callable] = None):
        """
        初始化标题生成服务

        Args:
            db: 数据库会话
            progress_callback: 进度回调函数（可选）
        """
        self.db = db
        self.progress_callback = progress_callback
        self.agent_a = TitleCreatorAgent()
        self.agent_b = TitleReviewerAgent()
        self.agent_c = ClickPredictorAgent()
        self.agent_d = FinalJudgeAgent()
    
    async def execute_title_generation(
        self,
        task_id: str,
        request: TitleGenerationRequest,
    ) -> None:
        """
        执行标题生成流程
        
        完整的4 Agent协作流程:
        1. Agent A: 生成10-15个标题候选
        2. Agent B: 一票否决 + 评分 + 筛选Top 5
        3. Agent C: 点击预测
        4. Agent D: 综合评分 + 输出Top 3
        
        如果Top 3综合分 < 7.0，触发重生机制（最多1次）。
        
        Args:
            task_id: 任务ID
            request: 标题生成请求
        """
        start_time = datetime.now()
        regeneration_count = 0
        
        try:
            # 更新任务状态为处理中
            await self._update_task_status(task_id, TaskStatus.PROCESSING)
            
            # 创建结果记录
            result = await self._create_result(task_id)
            
            # 执行Agent流程
            success = await self._execute_agent_pipeline(
                task_id=task_id,
                result_id=result.id,
                request=request,
                regeneration_count=regeneration_count,
            )
            
            if success:
                # 更新任务状态为完成
                await self._update_task_status(task_id, TaskStatus.COMPLETED)
                logger.info(f"标题生成任务 {task_id} 完成")
                if self.progress_callback:
                    await self.progress_callback({"event": "complete", "data": {"step": 4, "agent": "Agent D"}})
            else:
                # 更新任务状态为失败
                await self._update_task_status(
                    task_id,
                    TaskStatus.FAILED,
                    "难以成标题，需要人工介入",
                )
                logger.warning(f"标题生成任务 {task_id} 失败，需要人工介入")
                if self.progress_callback:
                    await self.progress_callback({"event": "error", "data": {"message": "难以成标题，需要人工介入"}})
            
            # 计算耗时
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            
            # 更新结果记录
            await self._update_result(result.id, {
                "completed_at": end_time,
                "duration_seconds": duration,
                "regeneration_count": regeneration_count,
            })

            # 提交事务（确保 task / result / candidates / recommendations / agent_logs 持久化）
            await self.db.commit()

        except Exception as e:
            logger.error(f"标题生成任务 {task_id} 异常: {str(e)}", exc_info=True)
            try:
                await self.db.rollback()
            except Exception:
                pass
            await self._update_task_status(task_id, TaskStatus.FAILED, str(e))
            try:
                await self.db.commit()
            except Exception:
                pass
            raise
    
    async def _execute_agent_pipeline(
        self,
        task_id: str,
        result_id: str,
        request: TitleGenerationRequest,
        regeneration_count: int,
    ) -> bool:
        """
        执行Agent流水线
        
        Args:
            task_id: 任务ID
            result_id: 结果ID
            request: 标题生成请求
            regeneration_count: 当前重生次数
            
        Returns:
            是否成功
        """
        # Agent A: 生成候选标题
        candidates = await self._execute_agent_a(
            task_id=task_id,
            result_id=result_id,
            request=request,
        )
        
        if not candidates:
            logger.error("Agent A 未生成任何候选标题")
            return False
        
        # Agent B: 评审和筛选
        b_result = await self._execute_agent_b(
            task_id=task_id,
            result_id=result_id,
            candidates=candidates,
            request=request,
        )
        
        if not b_result or not b_result.get("top5"):
            logger.error("Agent B 未筛选出Top 5")
            return False
        
        # Agent C: 点击预测
        c_result = await self._execute_agent_c(
            task_id=task_id,
            result_id=result_id,
            top5=b_result["top5"],
            request=request,
        )
        
        if not c_result:
            logger.error("Agent C 未完成点击预测")
            return False
        
        # Agent D: 最终判定
        d_result = await self._execute_agent_d(
            task_id=task_id,
            result_id=result_id,
            b_result=b_result,
            c_result=c_result,
            request=request,
        )
        
        if not d_result:
            logger.error("Agent D 未完成最终判定")
            return False
        
        # 检查是否需要重生
        if d_result.get("need_regeneration") and regeneration_count < settings.MAX_REGENERATIONS:
            logger.info(f"触发重生机制，当前重生次数: {regeneration_count}")
            
            # 执行重生
            return await self._execute_regeneration(
                task_id=task_id,
                result_id=result_id,
                request=request,
                regeneration_count=regeneration_count + 1,
                feedback=d_result.get("feedback", ""),
            )
        
        # 检查是否通过
        if d_result.get("passed", False):
            # 保存最终推荐
            await self._save_recommendations(
                result_id=result_id,
                recommendations=d_result.get("recommendations", []),
            )
            
            # 更新结果统计
            await self._update_result(result_id, {
                "total_candidates": len(candidates),
                "covered_methods": b_result.get("covered_methods", 0),
                "eliminated_count": b_result.get("eliminated_count", 0),
                "self_check_passed": "1",
                "self_check_details": d_result.get("self_check_details"),
            })
            
            return True
        else:
            return False
    
    async def _execute_agent_a(
        self,
        task_id: str,
        result_id: str,
        request: TitleGenerationRequest,
        feedback: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        执行Agent A - 标题创作员
        
        Args:
            task_id: 任务ID
            result_id: 结果ID
            request: 标题生成请求
            feedback: 重生反馈（可选）
            
        Returns:
            候选标题列表
        """
        logger.info("执行 Agent A - 标题创作员")

        if self.progress_callback:
            await self.progress_callback({"event": "step_start", "data": {"step": 1, "agent": "Agent A", "action": "正在生成 10-15 个标题候选..."}})

        # 创建Agent日志
        log = await self._create_agent_log(
            task_id=task_id,
            result_id=result_id,
            agent_type="A",
            agent_name="标题创作员",
            agent_role="百万粉 AI 公众号博主",
            execution_order=1,
        )
        
        try:
            # 调用Agent A
            result = await self.agent_a.generate_titles(
                topic=request.topic,
                outline=request.outline,
                feedback=feedback,
            )
            
            # 保存候选标题
            candidates = []
            for i, candidate in enumerate(result.get("candidates", [])):
                candidate_id = str(uuid.uuid4())
                
                # 创建候选记录
                title_candidate = TitleCandidate(
                    id=candidate_id,
                    result_id=result_id,
                    sequence=i + 1,
                    title=candidate.get("title", ""),
                    word_count=candidate.get("word_count", 0),
                    method=candidate.get("method", ""),
                    modifiers=candidate.get("modifiers", []),
                    explanation=candidate.get("explanation", ""),
                )
                
                self.db.add(title_candidate)
                candidates.append({
                    "id": candidate_id,
                    **candidate,
                })
            
            await self.db.flush()
            
            # 更新Agent日志
            await self._update_agent_log(log.id, {
                "status": "completed",
                "output_data": {"candidates_count": len(candidates)},
                "completed_at": datetime.now(),
            })

            if self.progress_callback:
                await self.progress_callback({"event": "step_done", "data": {"step": 1, "agent": "Agent A"}})

            return candidates
            
        except Exception as e:
            logger.error(f"Agent A 执行失败: {str(e)}", exc_info=True)
            await self._update_agent_log(log.id, {
                "status": "failed",
                "error_message": str(e),
                "completed_at": datetime.now(),
            })
            raise
    
    async def _execute_agent_b(
        self,
        task_id: str,
        result_id: str,
        candidates: List[Dict[str, Any]],
        request: TitleGenerationRequest,
    ) -> Optional[Dict[str, Any]]:
        """
        执行Agent B - 标题评审员
        
        Args:
            task_id: 任务ID
            result_id: 结果ID
            candidates: 候选标题列表
            request: 标题生成请求
            
        Returns:
            评审结果
        """
        logger.info("执行 Agent B - 标题评审员")

        if self.progress_callback:
            await self.progress_callback({"event": "step_start", "data": {"step": 2, "agent": "Agent B", "action": "正在一票否决扫描 + 6 维度评分..."}})

        # 创建Agent日志
        log = await self._create_agent_log(
            task_id=task_id,
            result_id=result_id,
            agent_type="B",
            agent_name="标题评审员",
            agent_role="公众号运营专家",
            execution_order=2,
        )
        
        try:
            # 调用Agent B
            result = await self.agent_b.review_titles(
                candidates=candidates,
                topic=request.topic,
                outline=request.outline,
            )
            
            # 更新候选标题的评分
            for score_data in result.get("scores", []):
                candidate_id = score_data.get("candidate_id")
                if candidate_id:
                    await self._update_candidate_score(candidate_id, score_data)
            
            # 标记一票否决的候选
            for eliminated in result.get("eliminated", []):
                candidate_id = eliminated.get("candidate_id")
                if candidate_id:
                    await self._update_candidate_elimination(
                        candidate_id,
                        eliminated.get("reason", ""),
                    )
            
            # 标记Top 5
            for top5_id in result.get("top5_ids", []):
                await self._update_candidate_top5(top5_id, True)
            
            # 更新Agent日志
            await self._update_agent_log(log.id, {
                "status": "completed",
                "output_data": result,
                "completed_at": datetime.now(),
            })

            if self.progress_callback:
                await self.progress_callback({"event": "step_done", "data": {"step": 2, "agent": "Agent B"}})

            return result

        except Exception as e:
            logger.error(f"Agent B 执行失败: {str(e)}", exc_info=True)
            await self._update_agent_log(log.id, {
                "status": "failed",
                "error_message": str(e),
                "completed_at": datetime.now(),
            })
            raise
    
    async def _execute_agent_c(
        self,
        task_id: str,
        result_id: str,
        top5: List[Dict[str, Any]],
        request: TitleGenerationRequest,
    ) -> Optional[Dict[str, Any]]:
        """
        执行Agent C - 读者点击预测员
        
        Args:
            task_id: 任务ID
            result_id: 结果ID
            top5: Top 5候选列表
            request: 标题生成请求
            
        Returns:
            点击预测结果
        """
        logger.info("执行 Agent C - 读者点击预测员")

        if self.progress_callback:
            await self.progress_callback({"event": "step_start", "data": {"step": 3, "agent": "Agent C", "action": "正在模拟读者场景，预测点击意愿..."}})

        # 创建Agent日志
        log = await self._create_agent_log(
            task_id=task_id,
            result_id=result_id,
            agent_type="C",
            agent_name="读者点击预测员",
            agent_role="目标读者(28岁互联网产品经理)",
            execution_order=3,
        )
        
        try:
            # 调用Agent C
            result = await self.agent_c.predict_clicks(
                top5=top5,
                topic=request.topic,
                outline=request.outline,
            )
            
            # 更新候选标题的点击预测
            for prediction in result.get("predictions", []):
                candidate_id = prediction.get("candidate_id")
                if candidate_id:
                    await self._update_candidate_click_prediction(
                        candidate_id,
                        prediction,
                    )
            
            # 更新Agent日志
            await self._update_agent_log(log.id, {
                "status": "completed",
                "output_data": result,
                "completed_at": datetime.now(),
            })

            if self.progress_callback:
                await self.progress_callback({"event": "step_done", "data": {"step": 3, "agent": "Agent C"}})

            return result

        except Exception as e:
            logger.error(f"Agent C 执行失败: {str(e)}", exc_info=True)
            await self._update_agent_log(log.id, {
                "status": "failed",
                "error_message": str(e),
                "completed_at": datetime.now(),
            })
            raise
    
    async def _execute_agent_d(
        self,
        task_id: str,
        result_id: str,
        b_result: Dict[str, Any],
        c_result: Dict[str, Any],
        request: TitleGenerationRequest,
    ) -> Optional[Dict[str, Any]]:
        """
        执行Agent D - 最终判定员
        
        Args:
            task_id: 任务ID
            result_id: 结果ID
            b_result: Agent B的评审结果
            c_result: Agent C的点击预测结果
            request: 标题生成请求
            
        Returns:
            最终判定结果
        """
        logger.info("执行 Agent D - 最终判定员")

        if self.progress_callback:
            await self.progress_callback({"event": "step_start", "data": {"step": 4, "agent": "Agent D", "action": "正在综合评分，输出 Top 3 推荐..."}})

        # 创建Agent日志
        log = await self._create_agent_log(
            task_id=task_id,
            result_id=result_id,
            agent_type="D",
            agent_name="最终判定员",
            agent_role="综合决策者",
            execution_order=4,
        )
        
        try:
            # 调用Agent D
            result = await self.agent_d.judge_titles(
                b_result=b_result,
                c_result=c_result,
                topic=request.topic,
                outline=request.outline,
            )
            
            # 更新Agent日志
            await self._update_agent_log(log.id, {
                "status": "completed",
                "output_data": result,
                "completed_at": datetime.now(),
            })

            if self.progress_callback:
                await self.progress_callback({"event": "step_done", "data": {"step": 4, "agent": "Agent D"}})

            return result

        except Exception as e:
            logger.error(f"Agent D 执行失败: {str(e)}", exc_info=True)
            await self._update_agent_log(log.id, {
                "status": "failed",
                "error_message": str(e),
                "completed_at": datetime.now(),
            })
            raise
    
    async def _execute_regeneration(
        self,
        task_id: str,
        result_id: str,
        request: TitleGenerationRequest,
        regeneration_count: int,
        feedback: str,
    ) -> bool:
        """
        执行重生流程
        
        Args:
            task_id: 任务ID
            result_id: 结果ID
            request: 标题生成请求
            regeneration_count: 重生次数
            feedback: 扣分理由反馈
            
        Returns:
            是否成功
        """
        logger.info(f"执行重生流程，第 {regeneration_count} 次")
        
        # 重新执行Agent A（带反馈）
        candidates = await self._execute_agent_a(
            task_id=task_id,
            result_id=result_id,
            request=request,
            feedback=feedback,
        )
        
        if not candidates:
            return False
        
        # 重新执行后续Agent
        return await self._execute_agent_pipeline(
            task_id=task_id,
            result_id=result_id,
            request=request,
            regeneration_count=regeneration_count,
        )
    
    async def _save_recommendations(
        self,
        result_id: str,
        recommendations: List[Dict[str, Any]],
    ) -> None:
        """
        保存最终推荐标题
        
        Args:
            result_id: 结果ID
            recommendations: 推荐标题列表
        """
        for i, rec in enumerate(recommendations):
            recommendation = FinalRecommendation(
                id=str(uuid.uuid4()),
                result_id=result_id,
                rank=i + 1,
                title=rec.get("title", ""),
                word_count=rec.get("word_count", 0),
                method=rec.get("method", ""),
                modifiers=rec.get("modifiers", []),
                b_score=rec.get("b_score", 0),
                c_click_willingness=rec.get("c_click_willingness", 0),
                final_score=rec.get("final_score", 0),
                recommendation_reason=rec.get("recommendation_reason", ""),
            )
            
            self.db.add(recommendation)
        
        await self.db.flush()
    
    async def _create_result(self, task_id: str) -> TitleGenerationResult:
        """创建结果记录"""
        result = TitleGenerationResult(
            id=str(uuid.uuid4()),
            task_id=task_id,
            created_at=datetime.now(),
        )
        
        self.db.add(result)
        await self.db.flush()
        
        return result
    
    async def _update_result(
        self,
        result_id: str,
        data: Dict[str, Any],
    ) -> None:
        """更新结果记录"""
        from sqlalchemy import update
        
        await self.db.execute(
            update(TitleGenerationResult)
            .where(TitleGenerationResult.id == result_id)
            .values(**data)
        )
        await self.db.flush()
    
    async def _update_task_status(
        self,
        task_id: str,
        status: TaskStatus,
        error_message: Optional[str] = None,
    ) -> None:
        """更新任务状态"""
        from sqlalchemy import update
        
        data = {
            "status": status,
            "updated_at": datetime.now(),
        }
        
        if status == TaskStatus.PROCESSING:
            data["started_at"] = datetime.now()
        elif status in (TaskStatus.COMPLETED, TaskStatus.FAILED):
            data["completed_at"] = datetime.now()
        
        if error_message:
            data["error_message"] = error_message
        
        await self.db.execute(
            update(Task).where(Task.id == task_id).values(**data)
        )
        await self.db.flush()
    
    async def _create_agent_log(
        self,
        task_id: str,
        result_id: str,
        agent_type: str,
        agent_name: str,
        agent_role: str,
        execution_order: int,
    ) -> AgentLog:
        """创建Agent日志"""
        log = AgentLog(
            id=str(uuid.uuid4()),
            task_id=task_id,
            result_id=result_id,
            agent_type=agent_type,
            agent_name=agent_name,
            agent_role=agent_role,
            execution_order=execution_order,
            status="running",
            started_at=datetime.now(),
            model_name=(
                settings.ANTHROPIC_MODEL
                if (settings.LLM_PROVIDER or "").lower() == "anthropic"
                else settings.DEEPSEEK_MODEL
            ),
        )
        
        self.db.add(log)
        await self.db.flush()
        
        return log
    
    async def _update_agent_log(
        self,
        log_id: str,
        data: Dict[str, Any],
    ) -> None:
        """更新Agent日志"""
        from sqlalchemy import update
        
        await self.db.execute(
            update(AgentLog).where(AgentLog.id == log_id).values(**data)
        )
        await self.db.flush()
    
    async def _update_candidate_score(
        self,
        candidate_id: str,
        score_data: Dict[str, Any],
    ) -> None:
        """更新候选标题评分"""
        from sqlalchemy import update
        
        await self.db.execute(
            update(TitleCandidate)
            .where(TitleCandidate.id == candidate_id)
            .values(
                b_score=score_data.get("b_score"),
                b_score_details=score_data.get("b_score_details"),
            )
        )
        await self.db.flush()
    
    async def _update_candidate_elimination(
        self,
        candidate_id: str,
        reason: str,
    ) -> None:
        """更新候选标题淘汰状态"""
        from sqlalchemy import update
        
        await self.db.execute(
            update(TitleCandidate)
            .where(TitleCandidate.id == candidate_id)
            .values(
                is_eliminated="1",
                elimination_reason=reason,
            )
        )
        await self.db.flush()
    
    async def _update_candidate_top5(
        self,
        candidate_id: str,
        is_top5: bool,
    ) -> None:
        """更新候选标题Top 5状态"""
        from sqlalchemy import update
        
        await self.db.execute(
            update(TitleCandidate)
            .where(TitleCandidate.id == candidate_id)
            .values(is_top5="1" if is_top5 else "0")
        )
        await self.db.flush()
    
    async def _update_candidate_click_prediction(
        self,
        candidate_id: str,
        prediction: Dict[str, Any],
    ) -> None:
        """更新候选标题点击预测"""
        from sqlalchemy import update
        
        await self.db.execute(
            update(TitleCandidate)
            .where(TitleCandidate.id == candidate_id)
            .values(
                c_click_willingness=prediction.get("click_willingness"),
                c_click_reason=prediction.get("click_reason"),
                c_no_click_reason=prediction.get("no_click_reason"),
                c_improvement_suggestion=prediction.get("improvement_suggestion"),
            )
        )
        await self.db.flush()


# 导出
__all__ = ["TitleGenerationService"]
