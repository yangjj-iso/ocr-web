"""AI-facing batch routes: field extraction and smart merge."""

from importlib import import_module
import shutil
import tempfile
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, raise_for_error, raise_service_unavailable, require_auth
from app.api.admin_users import write_operation_log
from app.core.auth import require_operator_access
from app.db.models import ArchiveRecord
from app.schemas.batches import (
    AIBoundaryAnalysisResponse,
    AIBoundaryTruthPutRequest,
    AIBoundaryTruthResponse,
    AIBatchMergeExtractRequest,
    AIBatchMergeExtractResponse,
    AIExtractFieldsRequest,
    AIExtractFieldsResponse,
)


def _compat_routes():
    return import_module("app.api.routes")


def _safe_export_filename(batch_id: str) -> str:
    normalized = ''.join(ch if ch.isalnum() or ch in {'-', '_'} else '_' for ch in str(batch_id or ''))
    normalized = normalized.strip('_') or 'batch'
    return f"{normalized}_archive.xlsx"


router = APIRouter(
    prefix="/api/ocr",
    tags=["AI Batches"],
    dependencies=[Depends(require_auth), Depends(require_operator_access)],
)


@router.post("/tasks/{task_id}/ai-extract-fields", response_model=AIExtractFieldsResponse)
async def ai_extract_fields(
    task_id: int,
    body: AIExtractFieldsRequest | None = None,
    db: AsyncSession = Depends(get_db),
):
    body = body or AIExtractFieldsRequest()
    try:
        compat = _compat_routes()
        task = await compat.get_task_detail(db, task_id)
    except Exception as error:  # noqa: BLE001
        raise_for_error(error)

    if not task:
        raise HTTPException(status_code=404, detail="Task not found.")
    if str(getattr(task, "status", "") or "").lower() not in {"done", "completed"}:
        raise HTTPException(status_code=409, detail="AI extraction is only available after OCR is finished.")

    try:
        compat = _compat_routes()
        comparison = await compat.compare_rule_and_llm_fields(task, include_evidence=body.include_evidence)
    except Exception as error:  # noqa: BLE001
        raise_for_error(error)

    if comparison is None:
        raise HTTPException(status_code=500, detail="AI extraction failed unexpectedly.")
    if body.persist:
        conflicts = comparison.get("conflicts") or {}
        if conflicts:
            raise HTTPException(
                status_code=409,
                detail="AI extraction conflicts with rule extraction. Resolve conflicts before persisting.",
            )
        existing_record = (
            await db.execute(select(ArchiveRecord).where(ArchiveRecord.task_id == task_id))
        ).scalar_one_or_none()
        batch_id = str(getattr(existing_record, "batch_id", "") or getattr(task, "batch_id", "") or "").strip()
        batch_folder = str(getattr(existing_record, "batch_folder", "") or "").strip()
        if not batch_folder:
            task_file_path = Path(str(getattr(task, "file_path", "") or ""))
            batch_folder = str(task_file_path.parent) if str(task_file_path) else ""
        try:
            compat = _compat_routes()
            await compat.save_archive_record(
                db,
                task_id,
                batch_id,
                batch_folder,
                comparison.get("recommended_fields") or {},
            )
        except Exception as error:  # noqa: BLE001
            raise_for_error(error)

    await write_operation_log(
        db,
        user_id=None,
        username="",
        action_type="ai_extract_fields",
        detail={"task_id": task_id, "persist": body.persist},
    )
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
        compat = _compat_routes()
        result = await compat.get_batch_merge_extract_result(
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


@router.get("/batches/{batch_id}/ai-merge-export")
async def export_batch_merge_excel(
    batch_id: str,
    background_tasks: BackgroundTasks,
    force_refresh: bool = False,
    similarity_threshold: int | None = None,
    db: AsyncSession = Depends(get_db),
):
    export_dir = Path(tempfile.mkdtemp(prefix="ocr-merge-export-"))
    export_file = export_dir / _safe_export_filename(batch_id)
    try:
        from app.application.workflows.batches import export_batch_ai_merge_excel

        file_path = await export_batch_ai_merge_excel(
            batch_id=batch_id,
            force_refresh=force_refresh,
            output_path=str(export_file),
            similarity_threshold=similarity_threshold,
            db=db,
        )
    except Exception as error:  # noqa: BLE001
        shutil.rmtree(export_dir, ignore_errors=True)
        raise_service_unavailable(error, "Smart merge export service is temporarily unavailable. Please retry later.")

    if not file_path:
        shutil.rmtree(export_dir, ignore_errors=True)
        raise HTTPException(status_code=404, detail="No merged archive documents were generated for this batch.")

    background_tasks.add_task(shutil.rmtree, export_dir, True)
    await write_operation_log(db, user_id=None, username="", action_type="export_archive", detail=f"batch_id={batch_id}")
    return FileResponse(
        path=file_path,
        filename=Path(file_path).name,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


@router.get("/batches/{batch_id}/boundary-analysis", response_model=AIBoundaryAnalysisResponse)
async def batch_boundary_analysis(
    batch_id: str,
    force_refresh: bool = False,
    similarity_threshold: int | None = None,
    db: AsyncSession = Depends(get_db),
):
    try:
        compat = _compat_routes()
        payload = await compat.get_batch_boundary_analysis_result(
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
        compat = _compat_routes()
        payload = await compat.get_batch_boundary_truth(db, batch_id=batch_id)
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
        compat = _compat_routes()
        payload = await compat.save_batch_boundary_truth(
            db,
            batch_id=batch_id,
            tasks=[item.model_dump(mode="python") for item in body.tasks],
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except Exception as error:  # noqa: BLE001
        raise_service_unavailable(error, "Boundary truth save service is temporarily unavailable.")
    await write_operation_log(
        db,
        user_id=None,
        username="",
        action_type="save_boundary_truth",
        detail={"batch_id": batch_id, "tasks": len(body.tasks)},
    )
    return payload
