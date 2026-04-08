"""Archive routes: list, export, import, delete."""

import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import ensure_allowed_path, get_db, raise_for_error, require_auth
from app.application.workflows.archives import (
    delete_archive_records as run_delete_archive_records,
    export_archive_records_to_temp_file,
    import_archive_records,
    list_archive_records as run_list_archive_records,
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/ocr",
    tags=["Archives"],
    dependencies=[Depends(require_auth)],
)


@router.get("/archive-records/export")
async def export_archive_records(
    folder: str = Query(""),
    batch_id: str = Query(""),
    db: AsyncSession = Depends(get_db),
):
    temp_path = await export_archive_records_to_temp_file(folder=folder, batch_id=batch_id, db=db)
    if not temp_path:
        raise HTTPException(status_code=404, detail="No archive records found.")

    return FileResponse(
        temp_path,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename="archive_records.xlsx",
    )


@router.get("/archive-records")
async def list_archive_records(
    folder: str = Query(""),
    batch_id: str = Query(""),
    page: int = Query(1, ge=1),
    page_size: int = Query(200, ge=1, le=1000),
    db: AsyncSession = Depends(get_db),
):
    records, total = await run_list_archive_records(
        folder=folder,
        batch_id=batch_id,
        page=page,
        page_size=page_size,
        db=db,
    )
    return {
        "total": total,
        "records": [
            {
                "id": record.id,
                "task_id": record.task_id,
                "batch_id": record.batch_id,
                "batch_folder": record.batch_folder,
                "archive_no": record.archive_no,
                "doc_no": record.doc_no,
                "responsible": record.responsible,
                "title": record.title,
                "date": record.date,
                "pages": record.pages,
                "classification": record.classification,
                "remarks": record.remarks,
                "created_at": record.created_at.isoformat() if record.created_at else None,
            }
            for record in records
        ],
    }


@router.post("/archive-records/import-excel")
async def import_archive_from_excel(body: dict, db: AsyncSession = Depends(get_db)):
    file_path = body.get("file_path", "")
    batch_id = body.get("batch_id", "")
    if not file_path:
        raise HTTPException(status_code=400, detail="file_path is required.")

    try:
        safe_path = ensure_allowed_path(file_path, expect_file=True)
    except Exception as error:  # noqa: BLE001
        raise_for_error(error)
    try:
        count = await import_archive_records(db=db, file_path=str(safe_path), batch_id=batch_id)
    except FileNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except (ImportError, ValueError) as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except Exception as error:  # noqa: BLE001
        logger.exception("Import archive from excel failed.")
        raise HTTPException(status_code=500, detail="Import failed.") from error

    return {"imported": count, "file_path": str(safe_path)}


@router.delete("/archive-records")
async def delete_archive_records(
    folder: str = Query(""),
    batch_id: str = Query(""),
    db: AsyncSession = Depends(get_db),
):
    deleted = await run_delete_archive_records(folder=folder, batch_id=batch_id, db=db)
    return {"deleted": deleted}
