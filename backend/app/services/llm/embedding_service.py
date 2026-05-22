"""Embedding 服务：默认走阿里云百炼 OpenAI-compatible 端点。

- 批量调用，单次最多 25 条（DashScope 限制）
- retry：网络错误重试 3 次
- 单条失败不影响其他
"""

import asyncio
import logging
from typing import List, Optional

from openai import AsyncOpenAI, APIError

from app.core.config import settings

logger = logging.getLogger(__name__)


# DashScope text-embedding-v3 OpenAI-compatible 端点的批量上限是 10 条
# （DashScope 原生 SDK 是 25，但 compatible-mode 是 10，已实测）
DASHSCOPE_BATCH_LIMIT = 10


class EmbeddingService:
    """Embedding 客户端：当前只实现 dashscope provider。

    切换 provider：改 settings.EMBEDDING_PROVIDER + 加 if 分支即可。
    """

    def __init__(self):
        self.provider = settings.EMBEDDING_PROVIDER
        self.model = settings.EMBEDDING_MODEL
        self.dim = settings.EMBEDDING_DIM
        self._client: Optional[AsyncOpenAI] = None

    def _get_client(self) -> AsyncOpenAI:
        if self._client is None:
            if not settings.EMBEDDING_API_KEY:
                raise RuntimeError("EMBEDDING_API_KEY 未配置")
            self._client = AsyncOpenAI(
                api_key=settings.EMBEDDING_API_KEY,
                base_url=settings.EMBEDDING_API_BASE,
            )
        return self._client

    async def embed(self, text: str) -> Optional[List[float]]:
        """单条 embedding。失败返回 None。"""
        results = await self.embed_batch([text])
        return results[0] if results else None

    async def embed_batch(
        self,
        texts: List[str],
        *,
        max_retries: int = 3,
        retry_delay: float = 2.0,
    ) -> List[Optional[List[float]]]:
        """批量 embedding。返回顺序对齐输入 texts；失败位为 None。"""
        if not texts:
            return []

        client = self._get_client()
        results: List[Optional[List[float]]] = [None] * len(texts)

        # 按 BATCH_LIMIT 切片
        for offset in range(0, len(texts), DASHSCOPE_BATCH_LIMIT):
            chunk = texts[offset : offset + DASHSCOPE_BATCH_LIMIT]
            # 过滤空文本（API 不接受）
            mapping = [(i + offset, t) for i, t in enumerate(chunk) if t and t.strip()]
            if not mapping:
                continue
            chunk_texts = [t for _, t in mapping]

            for attempt in range(max_retries):
                try:
                    resp = await client.embeddings.create(
                        model=self.model,
                        input=chunk_texts,
                        encoding_format="float",
                    )
                    for (orig_idx, _), data_item in zip(mapping, resp.data):
                        vec = list(data_item.embedding)
                        if len(vec) != self.dim:
                            logger.warning(
                                f"embedding 维度异常: got={len(vec)} expected={self.dim}"
                            )
                        results[orig_idx] = vec
                    break
                except APIError as e:
                    logger.warning(
                        f"embedding API 错误 (attempt {attempt + 1}/{max_retries}): {e}"
                    )
                    if attempt < max_retries - 1:
                        await asyncio.sleep(retry_delay * (2 ** attempt))
                except Exception as e:
                    logger.error(f"embedding 调用异常: {e}")
                    break

        return results


embedding_service = EmbeddingService()
