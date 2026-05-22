"""预处理 pipeline：RawInfo → InfoCluster。

模块拆分：
- pipeline：编排主流程
- embedder：批量生成 embedding
- clusterer：pgvector cosine 聚类
- enricher：LLM 调用（信息类型 + 6 要素）
- rules：规则计算（freshness / heat_score / low_fan_hit）
"""

from app.services.preprocess.pipeline import preprocess_pipeline

__all__ = ["preprocess_pipeline"]
