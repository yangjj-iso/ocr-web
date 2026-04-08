"""Batch routes: folder scan, ensure batch id, AI extraction."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import (
    ensure_allowed_path,
    get_db,
    invalidate_lists,
    raise_for_error,
    raise_service_unavailable,
    require_auth,
)
from app.application.workflows.batches import (
    ai_extract_task_fields,
    ai_merge_extract_batch as run_ai_merge_extract_batch,
    ensure_batch_for_folder,
    scan_allowed_folder,
)
from app.schemas.batches import (
    AIBatchMergeExtractRequest,
    AIBatchMergeExtractResponse,
    AIExtractFieldsRequest,
    AIExtractFieldsResponse,
)

router = APIRouter(
    prefix="/api/ocr",
    tags=["Batches"],
    dependencies=[Depends(require_auth)],
)


@router.get("/scan-folder")
async def scan_folder(path: str = Query(..., description="Absolute path under an allowed root.")):
    try:
        folder = ensure_allowed_path(path, expect_dir=True)
        return scan_allowed_folder(folder)
    except Exception as error:  # noqa: BLE001
        raise_for_error(error)


@router.post("/folders/ensure-batch")
async def ensure_folder_batch(body: dict, db: AsyncSession = Depends(get_db)):
    folder = str(body.get("folder", "")).strip()
    if not folder:
        raise HTTPException(status_code=400, detail="Missing folder.")

    batch_id, created = await ensure_batch_for_folder(folder=folder, db=db)
    if not batch_id and not created:
        raise HTTPException(status_code=404, detail="No completed tasks found in this folder.")

    if created:
        invalidate_lists()
    return {"batch_id": batch_id, "created": created}


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
            db=db,
        )
    except Exception as error:  # noqa: BLE001
        raise_service_unavailable(error, "Smart merge service is temporarily unavailable. Please retry later.")

    if not result:
        raise HTTPException(status_code=404, detail="No eligible completed tasks were found for this batch.")
    return result
