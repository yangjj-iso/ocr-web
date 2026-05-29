"""
Embedding 服务 — 调用 OpenAI-compatible /v1/embeddings 端点生成文本向量

特性:
- 支持批量 embedding（一次最多 EMBEDDING_BATCH_SIZE 条）
- LRU 缓存避免重复计算
- 降级：embedding 服务不可用时返回 None，由调用方回退到词法匹配
"""

from __future__ import annotations

import hashlib
import logging
from collections import OrderedDict
from typing import Any

logger = logging.getLogger(__name__)

try:
    import httpx
except ImportError:
    httpx = None

# LRU cache for embeddings (text hash → vector)
_CACHE_MAX_SIZE = 1000
_embedding_cache: OrderedDict[str, list[float]] = OrderedDict()


def _cache_key(text: str) -> str:
    return hashlib.md5(text.encode("utf-8")).hexdigest()


def _cache_get(text: str) -> list[float] | None:
    key = _cache_key(text)
    if key in _embedding_cache:
        _embedding_cache.move_to_end(key)
        return _embedding_cache[key]
    return None


def _cache_put(text: str, vector: list[float]) -> None:
    key = _cache_key(text)
    _embedding_cache[key] = vector
    _embedding_cache.move_to_end(key)
    while len(_embedding_cache) > _CACHE_MAX_SIZE:
        _embedding_cache.popitem(last=False)


def _get_config() -> dict[str, Any]:
    from app.config import (
        EMBEDDING_BASE_URL,
        EMBEDDING_API_KEY,
        EMBEDDING_MODEL,
        EMBEDDING_DIMENSIONS,
        EMBEDDING_BATCH_SIZE,
    )
    return {
        "base_url": EMBEDDING_BASE_URL,
        "api_key": EMBEDDING_API_KEY,
        "model": EMBEDDING_MODEL,
        "dimensions": EMBEDDING_DIMENSIONS,
        "batch_size": EMBEDDING_BATCH_SIZE,
    }


def is_embedding_available() -> bool:
    """检查 embedding 服务是否已配置"""
    cfg = _get_config()
    return bool(cfg["base_url"] and cfg["model"])


async def embed_texts(texts: list[str]) -> list[list[float] | None]:
    """
    批量生成 embedding 向量。

    返回与输入等长的列表，每个元素为 float 向量或 None（失败时）。
    对已缓存的文本直接返回缓存结果，仅对未缓存的调用 API。
    """
    if not texts:
        return []

    if httpx is None:
        logger.warning("httpx not installed, embedding unavailable.")
        return [None] * len(texts)

    cfg = _get_config()
    if not cfg["base_url"] or not cfg["model"]:
        return [None] * len(texts)

    # 分离已缓存和未缓存
    results: list[list[float] | None] = [None] * len(texts)
    uncached_indices: list[int] = []
    uncached_texts: list[str] = []

    for i, text in enumerate(texts):
        cached = _cache_get(text)
        if cached is not None:
            results[i] = cached
        else:
            uncached_indices.append(i)
            uncached_texts.append(text)

    if not uncached_texts:
        return results

    # 批量调用 API
    batch_size = cfg["batch_size"]
    for batch_start in range(0, len(uncached_texts), batch_size):
        batch = uncached_texts[batch_start:batch_start + batch_size]
        vectors = await _call_embedding_api(batch, cfg)
        if vectors is None:
            continue
        for j, vec in enumerate(vectors):
            idx = uncached_indices[batch_start + j]
            results[idx] = vec
            if vec is not None:
                _cache_put(batch[j], vec)

    return results


async def embed_single(text: str) -> list[float] | None:
    """单条文本 embedding，返回向量或 None"""
    results = await embed_texts([text])
    return results[0] if results else None


async def _call_embedding_api(
    texts: list[str],
    cfg: dict[str, Any],
) -> list[list[float] | None] | None:
    """调用 OpenAI-compatible /v1/embeddings 端点"""
    url = f"{cfg['base_url'].rstrip('/')}/embeddings"
    headers: dict[str, str] = {"Content-Type": "application/json"}
    if cfg["api_key"]:
        headers["Authorization"] = f"Bearer {cfg['api_key']}"

    payload: dict[str, Any] = {
        "model": cfg["model"],
        "input": texts,
    }
    # 部分 API 支持 dimensions 参数
    if cfg["dimensions"]:
        payload["dimensions"] = cfg["dimensions"]

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, headers=headers, json=payload)

        if response.status_code != 200:
            logger.warning(
                "Embedding API returned HTTP %d: %s",
                response.status_code,
                response.text[:200],
            )
            return None

        data = response.json()
        embeddings_data = data.get("data", [])
        # 按 index 排序确保顺序正确
        embeddings_data.sort(key=lambda x: x.get("index", 0))
        return [item.get("embedding") for item in embeddings_data]

    except httpx.TimeoutException:
        logger.warning("Embedding API request timed out.")
        return None
    except Exception as exc:
        logger.warning("Embedding API call failed: %s", exc)
        return None
