"""Batch AI domain operations."""

from __future__ import annotations

from app.services import batch_cache_service as legacy_batch_cache_service
from app.services import batch_merge_extraction_service as legacy_batch_merge_service
from app.shared.contracts import DocumentMergeGroup


def invalidate_batch_ai_cache(batch_ids: set[str] | list[str] | tuple[str, ...]) -> None:
    legacy_batch_cache_service.invalidate_batch_ai_cache(set(batch_ids or []))


def normalize_batch_ids(batch_ids) -> set[str]:
    return legacy_batch_cache_service.normalize_batch_ids(batch_ids)


async def get_batch_merge_extract_result(db, *, batch_id: str, include_evidence: bool, force_refresh: bool):
    payload = await legacy_batch_merge_service.get_batch_merge_extract_result(
        db,
        batch_id=batch_id,
        include_evidence=include_evidence,
        force_refresh=force_refresh,
    )
    groups = [
        DocumentMergeGroup.model_validate(group).model_dump(mode="json")
        for group in payload.get("groups", [])
        if isinstance(group, dict)
    ]
    return {**payload, "groups": groups}


__all__ = [
    "get_batch_merge_extract_result",
    "invalidate_batch_ai_cache",
    "normalize_batch_ids",
]
