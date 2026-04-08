"""Compatibility router shell.

This module keeps backward compatibility for historical imports such as:
    from app.api.routes import router

New code should import routers from dedicated modules under ``app.api`` or use
``app.interfaces.api.v1.include_v1_routers`` from ``main.py``.
"""

from fastapi import APIRouter

from app.api.ai_batches import router as ai_batches_router
from app.api.archives import router as archives_router
from app.api.auth_routes import router as auth_router
from app.api.business_batches import router as business_batches_router
from app.api.evaluation import router as evaluation_router
from app.api.files import router as files_router
from app.api.qa import router as qa_router
from app.api.tasks import router as tasks_router
from app.services.archive_service import save_archive_record
from app.services.batch_evaluation_service import (
    get_batch_evaluation_ai_report,
    get_batch_evaluation_metrics,
    get_batch_evaluation_truth,
    save_batch_evaluation_truth,
)
from app.services.batch_merge_extraction_service import get_batch_merge_extract_result
from app.services.batch_qa_service import (
    answer_batch_question,
    get_batch_qa_history,
    get_batch_qa_metrics,
    submit_batch_qa_feedback,
)
from app.services.llm_field_extraction_service import compare_rule_and_llm_fields
from app.services.ocr_service import get_task_detail

router = APIRouter()
router.include_router(auth_router)
router.include_router(tasks_router)
router.include_router(archives_router)
router.include_router(business_batches_router)
router.include_router(ai_batches_router)
router.include_router(qa_router)
router.include_router(evaluation_router)
router.include_router(files_router)

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
    "router",
    "save_archive_record",
    "save_batch_evaluation_truth",
    "submit_batch_qa_feedback",
]
