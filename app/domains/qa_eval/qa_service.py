"""Batch QA service adapters."""

from app.services.batch_qa_service import (
    answer_batch_question as legacy_answer_batch_question,
    get_batch_qa_history,
    get_batch_qa_metrics,
    submit_batch_qa_feedback,
)
from app.shared.contracts import QaAnswerWithEvidence


async def answer_batch_question(*args, **kwargs):
    payload = await legacy_answer_batch_question(*args, **kwargs)
    if not isinstance(payload, dict):
        return payload

    contract = QaAnswerWithEvidence(
        answer=str(payload.get("answer") or ""),
        support_level=payload.get("support_level") or "insufficient",
        confidence=float(payload.get("confidence") or 0),
        evidence=payload.get("evidence") or [],
    )
    normalized = contract.model_dump(mode="json")
    return {**payload, **normalized}
__all__ = [
    "answer_batch_question",
    "get_batch_qa_history",
    "get_batch_qa_metrics",
    "submit_batch_qa_feedback",
]
