"""LLM / Embedding 服务统一入口。

embedding_service：阿里云百炼 OpenAI-compatible
llm_client：抽象 + 工厂；支持 DeepSeek / Anthropic / AIGoCode
"""

from app.services.llm.embedding_service import embedding_service
from app.services.llm.llm_client import get_llm_client, LLMClient

__all__ = ["embedding_service", "get_llm_client", "LLMClient"]
