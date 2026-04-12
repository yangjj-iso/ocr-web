"""Batch QA routes."""

from importlib import import_module

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, raise_for_error, require_auth
from app.core.auth import require_operator_access
from app.schemas.qa import (
    BatchQAFeedbackRequest,
    BatchQAFeedbackResponse,
    BatchQAHistoryResponse,
    BatchQAMetricsResponse,
    BatchQARequest,
    BatchQAResponse,
)


def _compat_routes():
    return import_module("app.api.routes")

router = APIRouter(
    prefix="/api/ocr",
    tags=["QA"],
    dependencies=[Depends(require_auth), Depends(require_operator_access)],
)


@router.post("/batches/{batch_id}/qa", response_model=BatchQAResponse)
async def batch_qa(
    batch_id: str,
    body: BatchQARequest,
    db: AsyncSession = Depends(get_db),
):
    question = (body.question or "").strip()
    if not question:
        raise HTTPException(status_code=400, detail="question must not be empty.")

    try:
        compat = _compat_routes()
        payload = await compat.answer_batch_question(
            db,
            batch_id=batch_id,
            question=question,
            top_k=body.top_k,
            persist=body.persist,
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except Exception as error:  # noqa: BLE001
        raise_for_error(error)

    if not payload:
        raise HTTPException(status_code=404, detail="No eligible completed tasks were found for this batch.")
    return payload


@router.get("/batches/{batch_id}/qa/history", response_model=BatchQAHistoryResponse)
async def batch_qa_history(
    batch_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    try:
        compat = _compat_routes()
        payload = await compat.get_batch_qa_history(
            db,
            batch_id=batch_id,
            page=page,
            page_size=page_size,
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except Exception as error:  # noqa: BLE001
        raise_for_error(error)
    return payload


@router.post("/batches/{batch_id}/qa/{qa_id}/feedback", response_model=BatchQAFeedbackResponse)
async def batch_qa_feedback(
    batch_id: str,
    qa_id: int,
    body: BatchQAFeedbackRequest,
    db: AsyncSession = Depends(get_db),
):
    try:
        compat = _compat_routes()
        payload = await compat.submit_batch_qa_feedback(
            db,
            batch_id=batch_id,
            qa_id=qa_id,
            rating=body.rating,
            reason=body.reason,
            comment=body.comment,
            corrected_answer=body.corrected_answer,
            corrected_evidence=[item.model_dump(mode="python") for item in body.corrected_evidence],
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except Exception as error:  # noqa: BLE001
        raise_for_error(error)

    if not payload:
        raise HTTPException(status_code=404, detail="QA record not found for this batch.")
    return payload


@router.get("/batches/{batch_id}/qa/metrics", response_model=BatchQAMetricsResponse)
async def batch_qa_metrics(batch_id: str, db: AsyncSession = Depends(get_db)):
    try:
        compat = _compat_routes()
        payload = await compat.get_batch_qa_metrics(db, batch_id=batch_id)
    except Exception as error:  # noqa: BLE001
        raise_for_error(error)
    return payload

