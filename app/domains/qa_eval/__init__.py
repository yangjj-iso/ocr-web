"""QA and evaluation domain adapters."""

from .evaluation_service import (
    get_batch_evaluation_ai_report,
    get_batch_evaluation_metrics,
    get_batch_evaluation_truth,
    save_batch_evaluation_truth,
)
from .qa_service import (
    answer_batch_question,
    get_batch_qa_history,
    get_batch_qa_metrics,
    submit_batch_qa_feedback,
)

__all__ = [
    "answer_batch_question",
    "get_batch_evaluation_ai_report",
    "get_batch_evaluation_metrics",
    "get_batch_evaluation_truth",
    "get_batch_qa_history",
    "get_batch_qa_metrics",
    "save_batch_evaluation_truth",
    "submit_batch_qa_feedback",
]

