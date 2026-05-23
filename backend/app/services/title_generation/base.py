"""
Agent基类

提供所有Agent的通用功能和接口。
统一走项目标准 LLMClient（由 settings.LLM_PROVIDER 决定 provider）。
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
import logging
import json

from app.core.config import settings
from app.services.llm import get_llm_client
from app.services.llm.llm_client import ChatMessage, parse_json_loose

logger = logging.getLogger(__name__)


class BaseAgent(ABC):
    """
    Agent基类

    提供AI模型调用的通用功能。
    """

    def __init__(self):
        """初始化Agent"""
        self.llm_client = get_llm_client()
        self.model: Optional[str] = None  # 由具体 provider 默认决定，子类可覆盖

    async def call_ai_model(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        json_mode: bool = False,
    ) -> str:
        """
        调用AI模型

        Args:
            prompt: 用户提示词
            system_prompt: 系统提示词（可选）
            temperature: 温度参数
            max_tokens: 最大token数
            json_mode: 是否要求 JSON 输出

        Returns:
            模型响应文本
        """
        messages = []
        if system_prompt:
            messages.append(ChatMessage(role="system", content=system_prompt))
        messages.append(ChatMessage(role="user", content=prompt))

        try:
            result = await self.llm_client.chat(
                messages=messages,
                model=self.model,
                temperature=temperature,
                max_tokens=max_tokens,
                json_mode=json_mode,
            )
            return result.text or ""
        except Exception as e:
            logger.error(f"AI模型调用失败: {str(e)}", exc_info=True)
            raise

    def parse_json_response(self, response: str) -> Dict[str, Any]:
        """
        解析JSON响应
        """
        parsed = parse_json_loose(response)
        if parsed is not None:
            return parsed
        try:
            return json.loads(response)
        except (json.JSONDecodeError, TypeError):
            preview = (response or "")[:1200] if response else "<EMPTY>"
            logger.warning(
                f"无法解析JSON响应 (len={len(response or '')}): {preview!r}"
            )
            return {}

    @abstractmethod
    async def execute(self, **kwargs) -> Dict[str, Any]:
        """
        执行Agent任务

        子类必须实现此方法。
        """
        pass
