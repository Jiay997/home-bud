# -*- coding: utf-8 -*-
"""Embedding 客户端模块（spec rag-llamaindex-migration）。

检索层向量表征的统一入口，双 provider 显式切换：
- `zhipu`：智谱 BigModel embedding-3（OpenAI 兼容 `/embeddings`，境内已备案，
  维度 1-2048）；httpx 同步调用，单批 ≤64 条（智谱接口上限），失败抛
  EmbeddingError 由调用方降级；
- `mock`：确定性本地 mock（mock_embed_2048）——字符 3-gram MD5 折叠到
  embedding_dimensions 维、权重 1+ln(tf)、L2 归一化，跨进程结果一致，
  供联调/CI/测试（conftest 强制 mock 保证测试不触网）。

降级语义：provider=zhipu 但 ZHIPU_API_KEY 为空 → 启动级告警（仅首次）并
自动降级 mock，不阻断业务；key 在 .env 配置即恢复真实通道。
"""
import hashlib
import logging
import math
from typing import List, Optional

import httpx

from ..core.config import get_settings

logger = logging.getLogger("jiaban.embed")

# 智谱 embeddings 单批 input 上限（接口约束，超限 4xx）
ZHIPU_BATCH_SIZE = 64

# mock 降级告警只发一次（进程级）
_mock_fallback_warned = False


class EmbeddingError(Exception):
    """Embedding 调用异常（网络失败/非 2xx/响应结构缺失/超时）。"""

    pass


def mock_embed_2048(text: str) -> List[float]:
    """生成确定性 mock 稠密向量（跨进程一致）。

    算法：字符 3-gram 滑窗 → 每个 3-gram 取 MD5 整数模维度得落点 →
    按词频累计权重 w=1+ln(tf)（常见片段权重更高）→ L2 归一化。
    与降级链 hashing_embed 的表征语义同源（n-gram hashing 家族），
    同一文本恒得同一向量，用于 mock/联调/测试链路的确定性。

    Args:
        text: 输入文本（title+content 拼接或查询问题）。

    Returns:
        embedding_dimensions 维、L2 归一化后的浮点向量。
    """
    settings = get_settings()
    dim = settings.embedding_dimensions
    vec = [0.0] * dim
    text = text or ""
    # 字符 3-gram 计数（短于 3 字符退化为整串 1 个单元）
    grams = [text[i:i + 3] for i in range(max(1, len(text) - 2))] if len(text) >= 3 else [text]
    tf: dict = {}
    for g in grams:
        tf[g] = tf.get(g, 0) + 1
    for gram, count in tf.items():
        digest = hashlib.md5(gram.encode("utf-8")).hexdigest()
        idx = int(digest, 16) % dim
        vec[idx] += 1.0 + math.log(count)
    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [v / norm for v in vec]


def _zhipu_embed_batch(texts: List[str], api_key: str, timeout: float) -> List[List[float]]:
    """调用智谱 embeddings 接口处理一批文本（≤64 条）。

    Args:
        texts: 本批文本（长度 ≤ ZHIPU_BATCH_SIZE）。
        api_key: 智谱 API Key（Bearer）。
        timeout: 请求超时秒数。

    Returns:
        与输入顺序一致的向量列表。

    Raises:
        EmbeddingError: 网络失败/非 2xx/响应结构缺失/维度不符。
    """
    settings = get_settings()
    try:
        resp = httpx.post(
            f"{settings.zhipu_base_url.rstrip('/')}/embeddings",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={
                "model": settings.zhipu_model,
                "input": texts,
                "dimensions": settings.embedding_dimensions,
            },
            timeout=timeout,
        )
    except httpx.HTTPError as exc:
        raise EmbeddingError(f"zhipu embeddings request failed: {exc}") from exc
    if resp.status_code != 200:
        raise EmbeddingError(f"zhipu embeddings http {resp.status_code}: {resp.text[:200]}")
    payload = resp.json()
    items = (payload or {}).get("data") or []
    if len(items) != len(texts):
        raise EmbeddingError(f"zhipu embeddings item count mismatch: {len(items)} != {len(texts)}")
    items.sort(key=lambda it: it.get("index", 0))
    vectors = [it.get("embedding") for it in items]
    if any(not v or len(v) != settings.embedding_dimensions for v in vectors):
        raise EmbeddingError("zhipu embeddings dim mismatch")
    return vectors  # type: ignore[return-value]


def embed_texts(texts: List[str], timeout: float = 8.0) -> List[List[float]]:
    """批量生成文本向量（provider 显式切换 + key 空自动降级 mock）。

    Args:
        texts: 文本列表（允许空列表，返回空列表）。
        timeout: zhipu 单批请求超时秒数。

    Returns:
        与输入顺序一致的向量列表（维度 = settings.embedding_dimensions）。

    Raises:
        EmbeddingError: zhipu 通道调用失败（调用方决定降级策略）。
    """
    global _mock_fallback_warned

    if not texts:
        return []
    settings = get_settings()
    provider = (settings.embedding_provider or "zhipu").strip().lower()
    api_key: Optional[str] = (settings.zhipu_api_key or "").strip() or None

    if provider == "zhipu" and api_key:
        out: List[List[float]] = []
        for i in range(0, len(texts), ZHIPU_BATCH_SIZE):
            out.extend(_zhipu_embed_batch(texts[i:i + ZHIPU_BATCH_SIZE], api_key, timeout))
        return out

    if provider == "zhipu" and not api_key and not _mock_fallback_warned:
        # key 缺失：一次性告警并自动降级 mock（配置即恢复，不阻断业务）
        _mock_fallback_warned = True
        logger.warning(
            "embedding provider=zhipu but ZHIPU_API_KEY empty, "
            "fallback to deterministic mock (fill .env to enable real channel)"
        )
    return [mock_embed_2048(t) for t in texts]
