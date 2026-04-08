"""Business-facing batch routes: scan folder and manage batch identity."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import (
    ensure_allowed_path,
    get_db,
    invalidate_lists,
    raise_for_error,
    require_auth,
)
from app.application.workflows.batches import ensure_batch_for_folder, scan_allowed_folder


router = APIRouter(
    prefix="/api/ocr",
    tags=["Business Batches"],
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
