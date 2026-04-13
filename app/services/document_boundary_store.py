from __future__ import annotations

from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import BatchBoundaryDecision, BatchDocumentGroup, BatchPageSequence
from app.services.document_boundary_engine import BoundaryResult


def _coerce_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    if value is None:
        return []
    return [value]


def _dedupe_rows(rows: list[dict[str, Any]], key_fields: tuple[str, ...]) -> list[dict[str, Any]]:
    keyed: dict[tuple[Any, ...], dict[str, Any]] = {}
    for row in rows:
        keyed[tuple(row[field] for field in key_fields)] = row
    return list(keyed.values())


async def _upsert_rows(
    db: AsyncSession,
    model: Any,
    rows: list[dict[str, Any]],
    *,
    index_elements: tuple[str, ...],
    update_columns: tuple[str, ...],
) -> None:
    if not rows:
        return

    values = _dedupe_rows(rows, index_elements)
    statement = pg_insert(model).values(values)
    excluded = statement.excluded
    update_values = {column: getattr(excluded, column) for column in update_columns}
    update_values["updated_at"] = func.now()
    await db.execute(
        statement.on_conflict_do_update(
            index_elements=list(index_elements),
            set_=update_values,
        )
    )


async def save_boundary_analysis(
    db: AsyncSession,
    *,
    batch_id: str,
    sequences: list[dict[str, Any]],
    boundary_result: BoundaryResult,
) -> None:
    try:
        await db.execute(delete(BatchPageSequence).where(BatchPageSequence.batch_id == batch_id))
        await db.execute(delete(BatchBoundaryDecision).where(BatchBoundaryDecision.batch_id == batch_id))
        await db.execute(delete(BatchDocumentGroup).where(BatchDocumentGroup.batch_id == batch_id))

        await _upsert_rows(
            db,
            BatchPageSequence,
            [
                {
                    "batch_id": batch_id,
                    "prefix": str(sequence.get("prefix", "") or ""),
                    "task_ids_json": _coerce_list(sequence.get("task_ids")),
                    "filenames_json": _coerce_list(sequence.get("filenames")),
                }
                for sequence in sequences
            ],
            index_elements=("batch_id", "prefix"),
            update_columns=("task_ids_json", "filenames_json"),
        )

        await _upsert_rows(
            db,
            BatchBoundaryDecision,
            [
                {
                    "batch_id": batch_id,
                    "left_task_id": decision.left_task_id,
                    "right_task_id": decision.right_task_id,
                    "prefix": decision.prefix,
                    "left_page_no": decision.left_page_no,
                    "right_page_no": decision.right_page_no,
                    "same_document_score": decision.same_document_score,
                    "should_merge": decision.should_merge,
                    "is_ambiguous": decision.is_ambiguous,
                    "strong_split": decision.strong_split,
                    "reason": decision.reason,
                    "signals_json": decision.signals,
                }
                for decision in boundary_result.adjacent_decisions
            ],
            index_elements=("batch_id", "left_task_id", "right_task_id"),
            update_columns=(
                "prefix",
                "left_page_no",
                "right_page_no",
                "same_document_score",
                "should_merge",
                "is_ambiguous",
                "strong_split",
                "reason",
                "signals_json",
            ),
        )

        await _upsert_rows(
            db,
            BatchDocumentGroup,
            [
                {
                    "batch_id": batch_id,
                    "group_key": group.group_id,
                    "prefix": group.prefix,
                    "task_ids_json": group.task_ids,
                    "filenames_json": group.filenames,
                    "start_page": group.start_page,
                    "end_page": group.end_page,
                    "confidence": group.confidence,
                    "reasons_json": group.reasons,
                }
                for group in boundary_result.groups
            ],
            index_elements=("batch_id", "group_key"),
            update_columns=(
                "prefix",
                "task_ids_json",
                "filenames_json",
                "start_page",
                "end_page",
                "confidence",
                "reasons_json",
            ),
        )

        await db.commit()
    except SQLAlchemyError:
        await db.rollback()
        raise


async def load_boundary_analysis(
    db: AsyncSession,
    *,
    batch_id: str,
) -> dict[str, Any] | None:
    sequences = (
        await db.execute(
            select(BatchPageSequence).where(BatchPageSequence.batch_id == batch_id).order_by(BatchPageSequence.prefix.asc())
        )
    ).scalars().all()
    decisions = (
        await db.execute(
            select(BatchBoundaryDecision)
            .where(BatchBoundaryDecision.batch_id == batch_id)
            .order_by(BatchBoundaryDecision.prefix.asc(), BatchBoundaryDecision.left_page_no.asc())
        )
    ).scalars().all()
    groups = (
        await db.execute(
            select(BatchDocumentGroup)
            .where(BatchDocumentGroup.batch_id == batch_id)
            .order_by(BatchDocumentGroup.prefix.asc(), BatchDocumentGroup.start_page.asc())
        )
    ).scalars().all()

    if not sequences and not decisions and not groups:
        return None

    grouped_task_ids: dict[int, str] = {}
    for group in groups:
        for task_id in _coerce_list(group.task_ids_json):
            try:
                grouped_task_ids[int(task_id)] = group.group_key
            except (TypeError, ValueError):
                continue

    return {
        "batch_id": batch_id,
        "sequences": [
            {
                "prefix": sequence.prefix,
                "task_ids": _coerce_list(sequence.task_ids_json),
                "filenames": _coerce_list(sequence.filenames_json),
            }
            for sequence in sequences
        ],
        "decisions": [
            {
                "left_task_id": decision.left_task_id,
                "right_task_id": decision.right_task_id,
                "prefix": decision.prefix,
                "left_page_no": decision.left_page_no,
                "right_page_no": decision.right_page_no,
                "same_document_score": decision.same_document_score,
                "should_merge": decision.should_merge,
                "is_ambiguous": decision.is_ambiguous,
                "strong_split": decision.strong_split,
                "reason": decision.reason,
                "signals": decision.signals_json or {},
            }
            for decision in decisions
        ],
        "groups": [
            {
                "group_id": group.group_key,
                "prefix": group.prefix,
                "task_ids": _coerce_list(group.task_ids_json),
                "filenames": _coerce_list(group.filenames_json),
                "start_page": group.start_page,
                "end_page": group.end_page,
                "confidence": group.confidence,
                "reasons": _coerce_list(group.reasons_json),
            }
            for group in groups
        ],
        "task_to_group": grouped_task_ids,
        "summary": {
            "sequence_count": len(sequences),
            "decision_count": len(decisions),
            "group_count": len(groups),
        },
    }


__all__ = ["load_boundary_analysis", "save_boundary_analysis"]
