"""Batch QA routes."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, raise_for_error, require_auth
from app.application.workflows.qa import (
    answer_question,
    get_metrics,
    list_history,
    submit_feedback,
)
from app.schemas.qa import (
    BatchQAFeedbackRequest,
    BatchQAFeedbackResponse,
    BatchQAHistoryResponse,
    BatchQAMetricsResponse,
    BatchQARequest,
    BatchQAResponse,
)

router = APIRouter(
    prefix="/api/ocr",
    tags=["QA"],
    dependencies=[Depends(require_auth)],
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
        payload = await answer_question(
            batch_id=batch_id,
            question=question,
            top_k=body.top_k,
            persist=body.persist,
            db=db,
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
        payload = await list_history(
            batch_id=batch_id,
            page=page,
            page_size=page_size,
            db=db,
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
        payload = await submit_feedback(
            batch_id=batch_id,
            qa_id=qa_id,
            rating=body.rating,
            reason=body.reason,
            comment=body.comment,
            corrected_answer=body.corrected_answer,
            corrected_evidence=[item.model_dump(mode="python") for item in body.corrected_evidence],
            db=db,
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
        payload = await get_metrics(batch_id=batch_id, db=db)
    except Exception as error:  # noqa: BLE001
        raise_for_error(error)
    return payload

