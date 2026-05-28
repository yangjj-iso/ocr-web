"""AI-only router registry and compatibility re-exports.

The Python web surface exposes only AI-facing APIs. Business/control-plane
responsibilities live in the Java control plane.
"""

from fastapi import APIRouter, FastAPI

from app.api.ai_batches import router as ai_batches_router
from app.api.evaluation import router as evaluation_router
from app.api.files import router as files_router
from app.api.qa import router as qa_router
from app.api.tasks import router as tasks_router

# --- Router registry (replaces app.interfaces.api.ai.router_registry) ---

AI_ROUTERS = (
    tasks_router,
    ai_batches_router,
    qa_router,
    evaluation_router,
    files_router,
)


def include_ai_routers(app: FastAPI) -> None:
    """Register all AI-facing routers on the FastAPI app."""
    for r in AI_ROUTERS:
        app.include_router(r)


# --- Legacy compatibility router ---

router = APIRouter()
router.include_router(tasks_router)
router.include_router(ai_batches_router)
router.include_router(qa_router)
router.include_router(evaluation_router)
router.include_router(files_router)

# --- Re-exports used by worker and other internal modules ---

from app.services.archive_service import save_archive_record  # noqa: E402
from app.services.batch_evaluation_service import (  # noqa: E402
    get_batch_evaluation_ai_report,
    get_batch_evaluation_metrics,
    get_batch_evaluation_truth,
    save_batch_evaluation_truth,
)
from app.services.batch_merge_extraction_service import get_batch_merge_extract_result  # noqa: E402
from app.services.batch_qa_service import (  # noqa: E402
    answer_batch_question,
    get_batch_qa_history,
    get_batch_qa_metrics,
    submit_batch_qa_feedback,
)
from app.services.llm_field_extraction_service import compare_rule_and_llm_fields  # noqa: E402
from app.services.ocr_service import get_task_detail  # noqa: E402

__all__ = [
    "answer_batch_question",
    "compare_rule_and_llm_fields",
    "get_batch_evaluation_ai_report",
    "get_batch_evaluation_metrics",
    "get_batch_evaluation_truth",
    "get_batch_merge_extract_result",
    "get_batch_qa_history",
    "get_batch_qa_metrics",
    "get_task_detail",
    "include_ai_routers",
    "router",
    "save_archive_record",
    "save_batch_evaluation_truth",
    "submit_batch_qa_feedback",
]
