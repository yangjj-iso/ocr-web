"""AI-facing batch routes: field extraction and smart merge."""

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, raise_for_error, raise_service_unavailable, require_auth
from app.db.models import ArchiveRecord
from app.infrastructure.persistence import tasks as task_repository
from app.services.archive_service import save_archive_record
from app.services.batch_merge_extraction_service import (
    get_batch_boundary_analysis_result,
    get_batch_merge_extract_result,
)
from app.services.document_boundary_feedback_service import (
    get_batch_boundary_truth as load_batch_boundary_truth,
    save_batch_boundary_truth as persist_batch_boundary_truth,
)
from app.services.llm_field_extraction_service import compare_rule_and_llm_fields
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
        task = await task_repository.get_task_detail(db, task_id)
        if not task:
            raise HTTPException(status_code=404, detail="Task not found.")
        if task.status != "done":
            raise HTTPException(status_code=409, detail="AI extraction is only available after OCR is finished.")

        comparison = await compare_rule_and_llm_fields(task, include_evidence=body.include_evidence)
        if body.persist:
            if comparison["conflicts"]:
                raise HTTPException(
                    status_code=409,
                    detail="AI extraction conflicts with rule extraction. Resolve conflicts before persisting.",
                )
            existing_record = (
                await db.execute(select(ArchiveRecord).where(ArchiveRecord.task_id == task.id))
            ).scalar_one_or_none()
            await save_archive_record(
                db,
                task.id,
                existing_record.batch_id if existing_record else "",
                existing_record.batch_folder if existing_record else str(Path(task.file_path).parent),
                comparison["recommended_fields"],
            )
    except HTTPException:
        raise
    except Exception as error:  # noqa: BLE001
        raise_for_error(error)

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
        result = await get_batch_merge_extract_result(
            db,
            batch_id=batch_id,
            include_evidence=body.include_evidence,
            force_refresh=body.force_refresh,
            similarity_threshold=body.similarity_threshold,
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
        payload = await get_batch_boundary_analysis_result(
            db,
            batch_id=batch_id,
            force_refresh=force_refresh,
            similarity_threshold=similarity_threshold,
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
        payload = await load_batch_boundary_truth(db, batch_id=batch_id)
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
        payload = await persist_batch_boundary_truth(
            db,
            batch_id=batch_id,
            tasks=[item.model_dump(mode="python") for item in body.tasks],
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except Exception as error:  # noqa: BLE001
        raise_service_unavailable(error, "Boundary truth save service is temporarily unavailable.")
    return payload
