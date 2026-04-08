from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy import delete as sa_delete
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.redis_cache import cache_delete
from app.db.models import (
    ArchiveRecord,
    BatchBoundaryFeedback,
    BatchBoundaryTruthTaskMap,
    OCRTask,
)
from app.utils.image_sequence_pdf import parse_page_file


MERGE_CACHE_PREFIX = "batch_ai_merge:v2:"


def _coerce_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _pair_key(left_task_id: int, right_task_id: int) -> tuple[int, int]:
    return (left_task_id, right_task_id) if left_task_id <= right_task_id else (right_task_id, left_task_id)


def _extract_visual_sequence_parts(filename: str) -> tuple[str, int] | None:
    try:
        return parse_page_file(Path(filename or ""))
    except Exception:
        return None


async def _load_valid_batch_tasks(db: AsyncSession, *, batch_id: str) -> list[OCRTask]:
    stmt = (
        select(OCRTask)
        .join(ArchiveRecord, ArchiveRecord.task_id == OCRTask.id)
        .where(ArchiveRecord.batch_id == batch_id)
        .order_by(OCRTask.created_at.asc(), OCRTask.id.asc())
    )
    rows = (await db.execute(stmt)).scalars().all()
    unique_tasks: list[OCRTask] = []
    seen: set[int] = set()
    for task in rows:
        if task.id in seen:
            continue
        seen.add(task.id)
        unique_tasks.append(task)
    return unique_tasks


def _build_adjacent_feedback_rows(
    *,
    batch_id: str,
    tasks: list[OCRTask],
    truth_task_to_doc_key: dict[int, str],
) -> list[BatchBoundaryFeedback]:
    sequences: dict[str, list[tuple[int, int]]] = defaultdict(list)
    for task in tasks:
        sequence = _extract_visual_sequence_parts(task.filename)
        if not sequence:
            continue
        prefix, page_no = sequence
        sequences[prefix].append((page_no, task.id))

    rows: list[BatchBoundaryFeedback] = []
    for prefix in sorted(sequences):
        ordered = sorted(sequences[prefix], key=lambda item: (item[0], item[1]))
        for (_, left_task_id), (_, right_task_id) in zip(ordered, ordered[1:]):
            left_doc_key = truth_task_to_doc_key.get(left_task_id, "")
            right_doc_key = truth_task_to_doc_key.get(right_task_id, "")
            if not left_doc_key or not right_doc_key:
                continue
            label = "same" if left_doc_key == right_doc_key else "different"
            rows.append(
                BatchBoundaryFeedback(
                    batch_id=batch_id,
                    left_task_id=min(left_task_id, right_task_id),
                    right_task_id=max(left_task_id, right_task_id),
                    label=label,
                    source="human",
                    note=f"derived_from_doc_key:{prefix}",
                )
            )
    return rows


async def get_batch_boundary_truth(db: AsyncSession, *, batch_id: str) -> dict[str, Any]:
    task_rows = (
        await db.execute(
            select(BatchBoundaryTruthTaskMap)
            .where(BatchBoundaryTruthTaskMap.batch_id == batch_id)
            .order_by(BatchBoundaryTruthTaskMap.task_id.asc())
        )
    ).scalars().all()
    feedback_rows = (
        await db.execute(
            select(BatchBoundaryFeedback)
            .where(BatchBoundaryFeedback.batch_id == batch_id)
            .order_by(BatchBoundaryFeedback.left_task_id.asc(), BatchBoundaryFeedback.right_task_id.asc())
        )
    ).scalars().all()

    updated_times: list[datetime] = []
    updated_times.extend([row.updated_at for row in task_rows if row.updated_at])
    updated_times.extend([row.updated_at for row in feedback_rows if row.updated_at])
    truth_updated_at = max(updated_times).isoformat() if updated_times else None

    return {
        "batch_id": batch_id,
        "tasks": [
            {
                "task_id": int(row.task_id),
                "doc_key": row.doc_key,
                "source": row.source,
                "note": row.note,
            }
            for row in task_rows
        ],
        "feedback": [
            {
                "left_task_id": int(row.left_task_id),
                "right_task_id": int(row.right_task_id),
                "label": row.label,
                "source": row.source,
                "note": row.note,
            }
            for row in feedback_rows
        ],
        "truth_updated_at": truth_updated_at,
    }


async def save_batch_boundary_truth(
    db: AsyncSession,
    *,
    batch_id: str,
    tasks: list[dict[str, Any]],
) -> dict[str, Any]:
    valid_tasks = await _load_valid_batch_tasks(db, batch_id=batch_id)
    valid_task_ids = {int(task.id) for task in valid_tasks}

    normalized_tasks: list[dict[str, Any]] = []
    truth_task_to_doc_key: dict[int, str] = {}
    for item in tasks:
        try:
            task_id = int(item.get("task_id"))
        except (TypeError, ValueError) as error:
            raise ValueError("Boundary truth requires a numeric task_id.") from error
        doc_key = _coerce_text(item.get("doc_key"))
        if task_id not in valid_task_ids:
            raise ValueError(f"Task #{task_id} does not belong to batch {batch_id}.")
        if not doc_key:
            raise ValueError(f"Task #{task_id} requires a non-empty doc_key.")
        if task_id in truth_task_to_doc_key:
            continue
        truth_task_to_doc_key[task_id] = doc_key
        normalized_tasks.append(
            {
                "task_id": task_id,
                "doc_key": doc_key,
                "source": _coerce_text(item.get("source")) or "human",
                "note": _coerce_text(item.get("note")) or None,
            }
        )

    await db.execute(sa_delete(BatchBoundaryTruthTaskMap).where(BatchBoundaryTruthTaskMap.batch_id == batch_id))
    await db.execute(sa_delete(BatchBoundaryFeedback).where(BatchBoundaryFeedback.batch_id == batch_id))

    for item in normalized_tasks:
        db.add(
            BatchBoundaryTruthTaskMap(
                batch_id=batch_id,
                task_id=item["task_id"],
                doc_key=item["doc_key"],
                source=item["source"],
                note=item["note"],
            )
        )

    for row in _build_adjacent_feedback_rows(
        batch_id=batch_id,
        tasks=valid_tasks,
        truth_task_to_doc_key=truth_task_to_doc_key,
    ):
        db.add(row)

    await db.commit()
    cache_delete(f"{MERGE_CACHE_PREFIX}{batch_id}")
    return await get_batch_boundary_truth(db, batch_id=batch_id)


__all__ = [
    "get_batch_boundary_truth",
    "save_batch_boundary_truth",
]
