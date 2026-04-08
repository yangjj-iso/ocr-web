"""Batch evaluation orchestration."""

from __future__ import annotations

from app.domains.qa_eval import (
    get_batch_evaluation_ai_report,
    get_batch_evaluation_metrics,
    get_batch_evaluation_truth,
    save_batch_evaluation_truth,
)


async def get_truth(*, batch_id: str, db):
    return await get_batch_evaluation_truth(db, batch_id=batch_id)


async def save_truth(*, batch_id: str, tasks: list[dict], documents: list[dict], db):
    return await save_batch_evaluation_truth(
        db,
        batch_id=batch_id,
        tasks=tasks,
        documents=documents,
    )


async def get_metrics(*, batch_id: str, force_refresh: bool, db):
    return await get_batch_evaluation_metrics(
        db,
        batch_id=batch_id,
        force_refresh=force_refresh,
    )


async def get_ai_report(*, batch_id: str, force_refresh: bool, db):
    return await get_batch_evaluation_ai_report(
        db,
        batch_id=batch_id,
        force_refresh=force_refresh,
    )

