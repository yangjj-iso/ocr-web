"""Batch QA orchestration."""

from __future__ import annotations

from app.domains.qa_eval import (
    answer_batch_question,
    get_batch_qa_history,
    get_batch_qa_metrics,
    submit_batch_qa_feedback,
)


async def answer_question(*, batch_id: str, question: str, top_k: int, persist: bool, db):
    return await answer_batch_question(
        db,
        batch_id=batch_id,
        question=question,
        top_k=top_k,
        persist=persist,
    )


async def list_history(*, batch_id: str, page: int, page_size: int, db):
    return await get_batch_qa_history(
        db,
        batch_id=batch_id,
        page=page,
        page_size=page_size,
    )


async def submit_feedback(
    *,
    batch_id: str,
    qa_id: int,
    rating: str,
    reason: str | None,
    comment: str | None,
    corrected_answer: str | None,
    corrected_evidence: list[dict],
    db,
):
    return await submit_batch_qa_feedback(
        db,
        batch_id=batch_id,
        qa_id=qa_id,
        rating=rating,
        reason=reason,
        comment=comment,
        corrected_answer=corrected_answer,
        corrected_evidence=corrected_evidence,
    )


async def get_metrics(*, batch_id: str, db):
    return await get_batch_qa_metrics(db, batch_id=batch_id)

