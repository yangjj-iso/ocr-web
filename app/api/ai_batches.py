"""AI-facing batch routes: field extraction and smart merge."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, raise_for_error, raise_service_unavailable, require_auth
from app.application.workflows.batches import (
    ai_extract_task_fields,
    get_batch_boundary_analysis,
    get_batch_boundary_truth,
    ai_merge_extract_batch as run_ai_merge_extract_batch,
    save_batch_boundary_truth,
)
from app.schemas.batches import (
    AIBoundaryAnalysisResponse,
    AIBoundaryTruthPutRequest,
    AIBoundaryTruthResponse,
    AIBatchMergeExtractRequest,
    AIBatchMergeExtractResponse,
    AIExtractFieldsRequest,
    AIExtractFieldsResponse,
)


router = APIRouter(
    prefix="/api/ocr",
    tags=["AI Batches"],
    dependencies=[Depends(require_auth)],
)


@router.post("/tasks/{task_id}/ai-extract-fields", response_model=AIExtractFieldsResponse)
async def ai_extract_fields(
    task_id: int,
    body: AIExtractFieldsRequest | None = None,
    db: AsyncSession = Depends(get_db),
):
    body = body or AIExtractFieldsRequest()
    try:
        comparison, state = await ai_extract_task_fields(
            task_id=task_id,
            include_evidence=body.include_evidence,
            persist=body.persist,
            db=db,
        )
    except Exception as error:  # noqa: BLE001
        raise_for_error(error)

    if state == "not_found":
        raise HTTPException(status_code=404, detail="Task not found.")
    if state == "not_done":
        raise HTTPException(status_code=409, detail="AI extraction is only available after OCR is finished.")
    if state == "conflicts":
        raise HTTPException(
            status_code=409,
            detail="AI extraction conflicts with rule extraction. Resolve conflicts before persisting.",
        )
    if comparison is None:
        raise HTTPException(status_code=500, detail="AI extraction failed unexpectedly.")
    return comparison


@router.post("/batches/{batch_id}/ai-merge-extract", response_model=AIBatchMergeExtractResponse)
async def ai_merge_extract_batch(
    batch_id: str,
    body: AIBatchMergeExtractRequest | None = None,
    db: AsyncSession = Depends(get_db),
):
    body = body or AIBatchMergeExtractRequest()
    if body.persist:
        raise HTTPException(
            status_code=400,
            detail="persist=true is not supported for batch AI merge extraction in phase 1.",
        )

    try:
        result = await run_ai_merge_extract_batch(
            batch_id=batch_id,
            include_evidence=body.include_evidence,
            force_refresh=body.force_refresh,
            similarity_threshold=body.similarity_threshold,
            db=db,
        )
    except Exception as error:  # noqa: BLE001
        raise_service_unavailable(error, "Smart merge service is temporarily unavailable. Please retry later.")

    if not result:
        raise HTTPException(status_code=404, detail="No eligible completed tasks were found for this batch.")
    return result


@router.get("/batches/{batch_id}/boundary-analysis", response_model=AIBoundaryAnalysisResponse)
async def batch_boundary_analysis(
    batch_id: str,
    force_refresh: bool = False,
    similarity_threshold: int | None = None,
    db: AsyncSession = Depends(get_db),
):
    try:
        payload = await get_batch_boundary_analysis(
            batch_id=batch_id,
            force_refresh=force_refresh,
            similarity_threshold=similarity_threshold,
            db=db,
        )
    except Exception as error:  # noqa: BLE001
        raise_service_unavailable(error, "Boundary analysis service is temporarily unavailable. Please retry later.")

    if not payload:
        raise HTTPException(status_code=404, detail="No eligible completed tasks were found for this batch.")
    return payload


@router.get("/batches/{batch_id}/boundary-truth", response_model=AIBoundaryTruthResponse)
async def batch_boundary_truth(
    batch_id: str,
    db: AsyncSession = Depends(get_db),
):
    try:
        payload = await get_batch_boundary_truth(batch_id=batch_id, db=db)
    except Exception as error:  # noqa: BLE001
        raise_service_unavailable(error, "Boundary truth service is temporarily unavailable. Please retry later.")
    return payload


@router.put("/batches/{batch_id}/boundary-truth", response_model=AIBoundaryTruthResponse)
async def put_batch_boundary_truth(
    batch_id: str,
    body: AIBoundaryTruthPutRequest,
    db: AsyncSession = Depends(get_db),
):
    try:
        payload = await save_batch_boundary_truth(
            batch_id=batch_id,
            tasks=[item.model_dump(mode="python") for item in body.tasks],
            db=db,
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except Exception as error:  # noqa: BLE001
        raise_service_unavailable(error, "Boundary truth save service is temporarily unavailable.")
    return payload
