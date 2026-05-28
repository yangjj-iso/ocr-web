"""Batch routes: folder scan, ensure batch id, AI extraction."""

import os
from pathlib import Path
from time import time

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, text as sa_text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import (
    ensure_allowed_path,
    get_db,
    invalidate_lists,
    raise_for_error,
    raise_service_unavailable,
    require_auth,
)
from app.db.models import ArchiveRecord
from app.infrastructure.persistence import tasks as task_repository
from app.services.archive_service import save_archive_record
from app.services.batch_merge_extraction_service import get_batch_merge_extract_result
from app.services.excel_export import extract_fields
from app.services.llm_field_extraction_service import compare_rule_and_llm_fields
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


def _scan_allowed_folder(folder: Path) -> dict:
    """Walk folder and return supported image/PDF files."""
    files = []
    for root, directories, filenames in os.walk(folder):
        directories.sort()
        for filename in sorted(filenames):
            full_path = Path(root) / filename
            extension = full_path.suffix.lower()
            if extension not in {".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".tif", ".pdf"}:
                continue
            files.append(
                {
                    "name": filename,
                    "path": str(full_path),
                    "rel_path": str(full_path.relative_to(folder)),
                    "size": full_path.stat().st_size,
                }
            )
    return {"folder": str(folder), "count": len(files), "files": files}


async def _ensure_batch_for_folder(folder: str, db) -> tuple[str, bool]:
    """Find or create a batch_id for the given folder."""
    existing = (
        await db.execute(
            sa_text(
                "SELECT DISTINCT batch_id FROM archive_records "
                "WHERE batch_folder = :folder AND batch_id IS NOT NULL AND batch_id != ''"
            ).bindparams(folder=folder)
        )
    ).scalars().all()
    if existing:
        return existing[0], False

    rows = (
        await db.execute(
            sa_text(
                "SELECT id FROM archive_records "
                "WHERE batch_folder = :folder AND (batch_id IS NULL OR batch_id = '')"
            ).bindparams(folder=folder)
        )
    ).scalars().all()

    batch_id = f"batch_{int(time())}_{os.urandom(3).hex()}"
    if not rows:
        base = folder.rstrip("/\\")
        task_rows = (
            await db.execute(
                sa_text(
                    "SELECT id, file_path, full_text, result_json, page_count, status "
                    "FROM ocr_tasks WHERE status = 'done' AND ("
                    "  file_path LIKE :pat_fwd OR file_path LIKE :pat_back"
                    ")"
                ).bindparams(pat_fwd=base + "/%", pat_back=base + "\\%")
            )
        ).fetchall()
        if not task_rows:
            return "", False

        for task_id, file_path, full_text, result_json, page_count, _status in task_rows:
            fields = extract_fields(Path(file_path).name, full_text or "", result_json, page_count or 0)
            fields = {str(k): str(v or "") for k, v in (fields or {}).items()}
            await save_archive_record(db, task_id, batch_id, folder, fields)
        return batch_id, True

    await db.execute(
        sa_text(
            "UPDATE archive_records SET batch_id = :bid "
            "WHERE batch_folder = :folder AND (batch_id IS NULL OR batch_id = '')"
        ).bindparams(bid=batch_id, folder=folder)
    )
    await db.commit()
    return batch_id, True

router = APIRouter(
    prefix="/api/ocr",
    tags=["Batches"],
    dependencies=[Depends(require_auth)],
)


@router.get("/scan-folder")
async def scan_folder(path: str = Query(..., description="Absolute path under an allowed root.")):
    try:
        folder = ensure_allowed_path(path, expect_dir=True)
        return _scan_allowed_folder(folder)
    except Exception as error:  # noqa: BLE001
        raise_for_error(error)


@router.post("/folders/ensure-batch")
async def ensure_folder_batch(body: dict, db: AsyncSession = Depends(get_db)):
    folder = str(body.get("folder", "")).strip()
    if not folder:
        raise HTTPException(status_code=400, detail="Missing folder.")

    batch_id, created = await _ensure_batch_for_folder(folder, db)
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
        )
    except Exception as error:  # noqa: BLE001
        raise_service_unavailable(error, "Smart merge service is temporarily unavailable. Please retry later.")

    if not result:
        raise HTTPException(status_code=404, detail="No eligible completed tasks were found for this batch.")
    return result
