"""Batch evaluation routes."""

from importlib import import_module

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, raise_service_unavailable, require_auth
from app.core.auth import require_operator_access
from app.schemas.evaluation import (
    BatchEvaluationAiReportResponse,
    BatchEvaluationMetricsResponse,
    BatchEvaluationTruthGetResponse,
    BatchEvaluationTruthPutRequest,
)


def _compat_routes():
    return import_module("app.api.routes")

router = APIRouter(
    prefix="/api/ocr",
    tags=["Evaluation"],
    dependencies=[Depends(require_auth), Depends(require_operator_access)],
)


@router.get("/batches/{batch_id}/evaluation-truth", response_model=BatchEvaluationTruthGetResponse)
async def get_batch_truth(batch_id: str, db: AsyncSession = Depends(get_db)):
    try:
        compat = _compat_routes()
        payload = await compat.get_batch_evaluation_truth(db, batch_id=batch_id)
    except Exception as error:  # noqa: BLE001
        raise_service_unavailable(error, "Evaluation truth service is temporarily unavailable. Please retry later.")
    return payload


@router.put("/batches/{batch_id}/evaluation-truth", response_model=BatchEvaluationTruthGetResponse)
async def put_batch_truth(
    batch_id: str,
    body: BatchEvaluationTruthPutRequest,
    db: AsyncSession = Depends(get_db),
):
    try:
        compat = _compat_routes()
        payload = await compat.save_batch_evaluation_truth(
            db,
            batch_id=batch_id,
            tasks=[item.model_dump(mode="python") for item in body.tasks],
            documents=[item.model_dump(mode="python") for item in body.documents],
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except Exception as error:  # noqa: BLE001
        raise_service_unavailable(error, "Evaluation truth save service is temporarily unavailable.")
    return payload


@router.get("/batches/{batch_id}/evaluation-metrics", response_model=BatchEvaluationMetricsResponse)
async def get_batch_metrics(
    batch_id: str,
    force_refresh: bool = Query(False),
    db: AsyncSession = Depends(get_db),
):
    try:
        compat = _compat_routes()
        payload = await compat.get_batch_evaluation_metrics(
            db,
            batch_id=batch_id,
            force_refresh=force_refresh,
        )
    except Exception as error:  # noqa: BLE001
        raise_service_unavailable(error, "Evaluation metrics service is temporarily unavailable. Please retry later.")

    if not payload:
        raise HTTPException(status_code=404, detail="No eligible completed tasks were found for this batch.")
    return payload


@router.get("/batches/{batch_id}/evaluation-report", response_model=BatchEvaluationAiReportResponse)
async def get_batch_ai_report(
    batch_id: str,
    force_refresh: bool = Query(False),
    db: AsyncSession = Depends(get_db),
):
    try:
        compat = _compat_routes()
        payload = await compat.get_batch_evaluation_ai_report(
            db,
            batch_id=batch_id,
            force_refresh=force_refresh,
        )
    except Exception as error:  # noqa: BLE001
        raise_service_unavailable(error, "Evaluation report service is temporarily unavailable. Please retry later.")

    if not payload:
        raise HTTPException(status_code=404, detail="No eligible completed tasks were found for this batch.")
    return payload
