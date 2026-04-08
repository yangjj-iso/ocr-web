from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.db.models import BatchBoundaryFeedback, OCRTask
from app.services.document_boundary_engine import BoundaryFeedbackPriors, BoundaryFeedbackStats
from app.services.document_family import infer_document_family_from_text, infer_title_hint
from app.utils.image_sequence_pdf import parse_page_file


@dataclass(slots=True)
class BoundaryFeedbackSample:
    label: str
    page_gap: int
    left_family: str = ""
    right_family: str = ""


def _extract_sequence_parts(filename: str) -> tuple[str, int] | None:
    try:
        return parse_page_file(Path(filename or ""))
    except Exception:
        return None


def _infer_family(task: OCRTask | None) -> str:
    if task is None:
        return ""
    full_text = str(task.full_text or "")
    return infer_document_family_from_text(
        title_hint=infer_title_hint(full_text),
        full_text=full_text,
    )


def _touch(stats_map, key, label: str) -> None:
    stats = stats_map.get(key)
    if stats is None:
        stats = BoundaryFeedbackStats()
        stats_map[key] = stats
    if label == "same":
        stats.same_count += 1
    elif label == "different":
        stats.different_count += 1


def build_boundary_feedback_priors(samples: list[BoundaryFeedbackSample]) -> BoundaryFeedbackPriors:
    priors = BoundaryFeedbackPriors()
    for sample in samples:
        label = str(sample.label or "").strip().lower()
        if label not in {"same", "different"}:
            continue
        page_gap = max(1, int(sample.page_gap or 1))
        left_family = str(sample.left_family or "").strip()
        right_family = str(sample.right_family or "").strip()

        _touch(priors.page_gap, page_gap, label)
        if left_family and right_family and left_family == right_family:
            _touch(priors.family_page_gap, (left_family, page_gap), label)
        elif left_family and right_family:
            _touch(priors.family_transition_gap, (left_family, right_family, page_gap), label)
    return priors


async def load_boundary_feedback_priors(db: AsyncSession) -> BoundaryFeedbackPriors:
    left_task = aliased(OCRTask)
    right_task = aliased(OCRTask)
    stmt = (
        select(BatchBoundaryFeedback, left_task, right_task)
        .join(left_task, left_task.id == BatchBoundaryFeedback.left_task_id)
        .join(right_task, right_task.id == BatchBoundaryFeedback.right_task_id)
        .where(BatchBoundaryFeedback.source == "human")
        .order_by(BatchBoundaryFeedback.updated_at.asc(), BatchBoundaryFeedback.id.asc())
    )
    rows = (await db.execute(stmt)).all()

    samples: list[BoundaryFeedbackSample] = []
    for feedback_row, left_row, right_row in rows:
        left_parts = _extract_sequence_parts(left_row.filename)
        right_parts = _extract_sequence_parts(right_row.filename)
        if not left_parts or not right_parts:
            continue
        left_prefix, left_page_no = left_parts
        right_prefix, right_page_no = right_parts
        if left_prefix != right_prefix:
            continue

        samples.append(
            BoundaryFeedbackSample(
                label=str(feedback_row.label or "").strip().lower(),
                page_gap=max(1, abs(int(right_page_no) - int(left_page_no))),
                left_family=_infer_family(left_row),
                right_family=_infer_family(right_row),
            )
        )

    return build_boundary_feedback_priors(samples)


__all__ = [
    "BoundaryFeedbackSample",
    "build_boundary_feedback_priors",
    "load_boundary_feedback_priors",
]
