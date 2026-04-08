from collections.abc import Iterable

from app.core.redis_cache import cache_delete_pattern

MERGE_CACHE_PREFIX = "batch_ai_merge:"
METRICS_CACHE_PREFIX = "batch_eval_metrics:"
REPORT_CACHE_PREFIX = "batch_eval_ai_report:"


def normalize_batch_ids(batch_ids: Iterable[str | None]) -> set[str]:
    return {str(batch_id).strip() for batch_id in batch_ids if str(batch_id or "").strip()}


def invalidate_batch_ai_cache(batch_ids: Iterable[str | None]) -> None:
    for batch_id in normalize_batch_ids(batch_ids):
        cache_delete_pattern(f"{MERGE_CACHE_PREFIX}{batch_id}*")
        cache_delete_pattern(f"{METRICS_CACHE_PREFIX}{batch_id}:*")
        cache_delete_pattern(f"{REPORT_CACHE_PREFIX}{batch_id}:*")

