"""
Agent基类

提供所有Agent的通用功能和接口。
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
import logging
import json

from anthropic import AsyncAnthropic
from openai import AsyncOpenAI

from app.core.config import settings

logger = logging.getLogger(__name__)


class BaseAgent(ABC):
    """
    Agent基类
    
    提供AI模型调用的通用功能。
    """
    
    def __init__(self):
        """初始化Agent"""
        self.anthropic_client = AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY) if settings.ANTHROPIC_API_KEY else None
        self.openai_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY) if settings.OPENAI_API_KEY else None
        
        # 选择使用的模型
        if settings.USE_PRIMARY_MODEL and self.anthropic_client:
            self.model = settings.PRIMARY_MODEL
            self.use_anthropic = True
        elif self.openai_client:
            self.model = settings.FALLBACK_MODEL
            self.use_anthropic = False
        else:
            raise ValueError("未配置任何AI模型API密钥")
    
    async def call_ai_model(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = None,
        max_tokens: int = None,
    ) -> str:
        """
        调用AI模型
        
        Args:
            prompt: 用户提示词
            system_prompt: 系统提示词（可选）
            temperature: 温度参数（可选）
            max_tokens: 最大token数（可选）
            
        Returns:
            模型响应文本
        """
        temperature = temperature or settings.MODEL_TEMPERATURE
        max_tokens = max_tokens or settings.MODEL_MAX_TOKENS
        
        try:
            if self.use_anthropic:
                return await self._call_anthropic(prompt, system_prompt, temperature, max_tokens)
            else:
                return await self._call_openai(prompt, system_prompt, temperature, max_tokens)
        except Exception as e:
            logger.error(f"AI模型调用失败: {str(e)}", exc_info=True)
            raise
    
    async def _call_anthropic(
        self,
        prompt: str,
        system_prompt: Optional[str],
        temperature: float,
        max_tokens: int,
    ) -> str:
        """调用Anthropic Claude模型"""
        messages = [{"role": "user", "content": prompt}]
        
        kwargs = {
            "model": self.model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": messages,
        }
        
        if system_prompt:
            kwargs["system"] = system_prompt
        
        response = await self.anthropic_client.messages.create(**kwargs)
        
        # 提取响应文本
        if response.content and len(response.content) > 0:
            return response.content[0].text
        
        return ""
    
    async def _call_openai(
        self,
        prompt: str,
        system_prompt: Optional[str],
        temperature: float,
        max_tokens: int,
    ) -> str:
        """调用OpenAI GPT模型"""
        messages = []
        
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        
        messages.append({"role": "user", "content": prompt})
        
        response = await self.openai_client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        
        # 提取响应文本
        if response.choices and len(response.choices) > 0:
            return response.choices[0].message.content
        
        return ""
    
    def parse_json_response(self, response: str) -> Dict[str, Any]:
        """
        解析JSON响应
        
        Args:
            response: 模型响应文本
            
        Returns:
            解析后的字典
        """
        try:
            # 尝试直接解析
            return json.loads(response)
        except json.JSONDecodeError:
            # 尝试提取JSON部分
            try:
                # 查找JSON开始和结束位置
                start = response.find('{')
                end = response.rfind('}') + 1
                
                if start != -1 and end > start:
                    json_str = response[start:end]
                    return json.loads(json_str)
            except (json.JSONDecodeError, ValueError):
                pass
            
            # 如果都失败，返回空字典
            logger.warning(f"无法解析JSON响应: {response[:200]}...")
            return {}
    
    @abstractmethod
    async def execute(self, **kwargs) -> Dict[str, Any]:
        """
        执行Agent任务
        
        子类必须实现此方法。
        """
        pass
