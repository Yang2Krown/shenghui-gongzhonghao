"""
多模型标题创作员

支持同时用多个模型生成标题，用于 A/B 对比测试。
"""

from typing import Dict, Any, List, Optional
import logging
import asyncio

from app.services.title_generation.base import BaseAgent
from app.services.title_generation.agent_a_creator import TitleCreatorAgent
from app.schemas.title_generation import TopicInfo, OutlineInfo

logger = logging.getLogger(__name__)


class MultiModelTitleCreatorAgent:
    """
    多模型标题创作员

    同时调用多个模型生成标题，用于对比不同模型的效果。
    """

    def __init__(self, providers: Optional[List[str]] = None):
        """
        初始化多模型标题创作员

        Args:
            providers: 要使用的 provider 列表，默认 ["deepseek", "aigocode"]
        """
        self.providers = providers or ["deepseek", "aigocode"]
        self.agents = {}

        # 为每个 provider 创建独立的 agent
        for provider in self.providers:
            try:
                agent = TitleCreatorAgent(provider=provider)
                self.agents[provider] = agent
                logger.info(f"初始化 {provider} agent 成功")
            except Exception as e:
                logger.error(f"初始化 {provider} agent 失败: {e}")

    async def generate_titles(
        self,
        topic: TopicInfo,
        outline: OutlineInfo,
        feedback: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        用多个模型并行生成标题

        Args:
            topic: 选题信息
            outline: 大纲信息
            feedback: 反馈（可选）

        Returns:
            各模型的生成结果
        """
        logger.info(f"开始多模型生成，providers: {list(self.agents.keys())}")

        # 并行调用多个模型
        tasks = {}
        for provider, agent in self.agents.items():
            tasks[provider] = self._call_agent(agent, provider, topic, outline, feedback)

        # 等待所有任务完成
        results = {}
        for provider, task in tasks.items():
            try:
                result = await task
                results[provider] = {
                    "success": True,
                    "candidates": result.get("candidates", []),
                    "count": len(result.get("candidates", [])),
                }
                logger.info(f"{provider} 生成了 {len(result.get('candidates', []))} 个标题")
            except Exception as e:
                results[provider] = {
                    "success": False,
                    "error": str(e),
                    "candidates": [],
                    "count": 0,
                }
                logger.error(f"{provider} 生成失败: {e}")

        return results

    async def _call_agent(
        self,
        agent: TitleCreatorAgent,
        provider: str,
        topic: TopicInfo,
        outline: OutlineInfo,
        feedback: Optional[str],
    ) -> Dict[str, Any]:
        """调用单个 agent"""
        try:
            return await agent.generate_titles(
                topic,
                outline,
                feedback,
                min_candidates=8,
                max_candidates=8,
            )
        except Exception as e:
            logger.error(f"Agent {provider} 调用异常: {e}")
            raise

    async def execute(self, **kwargs) -> Dict[str, Any]:
        """
        执行多模型生成任务（兼容 BaseAgent 接口）

        Args:
            topic: 选题信息
            outline: 大纲信息
            feedback: 反馈（可选）

        Returns:
            各模型的生成结果
        """
        topic = kwargs.get("topic")
        outline = kwargs.get("outline")
        feedback = kwargs.get("feedback")

        return await self.generate_titles(topic, outline, feedback)
