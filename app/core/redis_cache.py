"""Cache helpers with graceful Redis fallback."""

import json
import logging
from typing import Any

from config import REDIS_URL

logger = logging.getLogger(__name__)

try:
    import redis
except ImportError:  # pragma: no cover - depends on environment
    redis = None


_redis_client: Any | None = None
_redis_unavailable = False

PREFIX = "ocr:"
TASK_TTL = 3600
LIST_TTL = 30
SEARCH_TTL = 120


def get_redis() -> Any | None:
    """Return a singleton Redis client when the dependency and service are available."""
    global _redis_client, _redis_unavailable

    if _redis_unavailable:
        return None
    if _redis_client is not None:
        return _redis_client
    if redis is None:
        logger.warning("Redis package is not installed; caching is disabled.")
        _redis_unavailable = True
        return None

    try:
        _redis_client = redis.from_url(
            REDIS_URL,
            decode_responses=True,
            socket_connect_timeout=2,
        )
        _redis_client.ping()
        logger.info("Connected to Redis: %s", REDIS_URL)
        return _redis_client
    except Exception as error:  # noqa: BLE001
        logger.warning("Redis is unavailable; caching is disabled. %s", error)
        _redis_unavailable = True
        _redis_client = None
        return None


def cache_get(key: str) -> Any | None:
    client = get_redis()
    if not client:
        return None
    try:
        value = client.get(f"{PREFIX}{key}")
        if value:
            return json.loads(value)
    except Exception as error:  # noqa: BLE001
        logger.debug("Redis get failed: %s", error)
    return None


def cache_set(key: str, data: Any, ttl: int = TASK_TTL) -> None:
    client = get_redis()
    if not client:
        return
    try:
        client.setex(f"{PREFIX}{key}", ttl, json.dumps(data, ensure_ascii=False, default=str))
    except Exception as error:  # noqa: BLE001
        logger.debug("Redis set failed: %s", error)


def cache_delete(key: str) -> None:
    client = get_redis()
    if not client:
        return
    try:
        client.delete(f"{PREFIX}{key}")
    except Exception as error:  # noqa: BLE001
        logger.debug("Redis delete failed: %s", error)


def cache_delete_pattern(pattern: str) -> None:
    client = get_redis()
    if not client:
        return
    try:
        keys = client.keys(f"{PREFIX}{pattern}")
        if keys:
            client.delete(*keys)
    except Exception as error:  # noqa: BLE001
        logger.debug("Redis delete pattern failed: %s", error)


def invalidate_task(task_id: int) -> None:
    cache_delete(f"task:{task_id}")
    cache_delete_pattern("list:*")
    cache_delete_pattern("search:*")
    cache_delete("folders")
    cache_delete("folders:terminal")


def invalidate_lists() -> None:
    cache_delete_pattern("list:*")
    cache_delete_pattern("search:*")
    cache_delete("folders")
    cache_delete("folders:terminal")
