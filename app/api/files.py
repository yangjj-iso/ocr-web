"""File routes for original downloads, thumbnails, PDF page previews, and region crops."""

import logging
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import ensure_allowed_path, get_db, raise_for_error, require_auth
from app.core.preview import build_pdf_page_preview, build_region_preview, build_thumbnail
from app.core.result_validation import normalize_result_pages
from app.infrastructure.persistence import tasks as task_repository

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/ocr",
    tags=["Files"],
    dependencies=[Depends(require_auth)],
)


async def _get_task_file_context(task_id: int, db) -> tuple[dict | None, str]:
    """Load task and resolve its file path."""
    task = await task_repository.get_task_detail(db, task_id)
    if not task:
        return None, "not_found"
    file_path = ensure_allowed_path(task.file_path, expect_file=True)
    return {"task": task, "file_path": file_path, "suffix": Path(file_path).suffix.lower()}, "ok"


async def _get_task_region_context(task_id: int, page_num: int, region_index: int, db) -> tuple[dict | None, str]:
    """Load task, validate page/region indices, and return region bbox context."""
    context, state = await _get_task_file_context(task_id, db)
    if state != "ok" or not context:
        return context, state

    task = context["task"]
    raw_pages = task.result_json if isinstance(task.result_json, list) else [task.result_json] if task.result_json else []
    if not raw_pages:
        return None, "result_not_found"

    try:
        pages = normalize_result_pages(raw_pages)
    except Exception:
        pages = raw_pages

    page_index = int(page_num) - 1
    if page_index < 0:
        return None, "invalid_page"
    if page_index >= len(pages):
        return None, "page_not_found"

    page = pages[page_index] if isinstance(pages[page_index], dict) else {}
    regions = page.get("regions") if isinstance(page, dict) else []
    if not isinstance(regions, list):
        return None, "region_not_found"
    if region_index < 0 or region_index >= len(regions):
        return None, "region_not_found"

    region = regions[region_index] if isinstance(regions[region_index], dict) else {}
    bbox = region.get("layout_bbox") or region.get("bbox") or []
    if not bbox:
        return None, "bbox_not_found"

    return {**context, "page": page, "page_num": page_num, "region": region, "region_index": region_index}, "ok"


@router.get("/tasks/{task_id}/file")
async def get_task_file(task_id: int, db: AsyncSession = Depends(get_db)):
    try:
        context, state = await _get_task_file_context(task_id, db)
    except Exception as error:  # noqa: BLE001
        raise_for_error(error)

    if state == "not_found":
        raise HTTPException(status_code=404, detail="Task not found.")

    file_path = context["file_path"]
    media_types = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".bmp": "image/bmp",
        ".tiff": "image/tiff",
        ".tif": "image/tiff",
        ".pdf": "application/pdf",
    }
    return FileResponse(file_path, media_type=media_types.get(file_path.suffix.lower(), "application/octet-stream"))


@router.get("/tasks/{task_id}/thumbnail")
async def get_task_thumbnail(task_id: int, db: AsyncSession = Depends(get_db)):
    try:
        context, state = await _get_task_file_context(task_id, db)
    except Exception as error:  # noqa: BLE001
        raise_for_error(error)

    if state == "not_found":
        raise HTTPException(status_code=404, detail="Task not found.")

    return Response(content=build_thumbnail(context["file_path"]), media_type="image/png")


@router.get("/tasks/{task_id}/pages/{page_num}/image")
async def get_task_page_image(task_id: int, page_num: int, db: AsyncSession = Depends(get_db)):
    try:
        context, state = await _get_task_file_context(task_id, db)
    except Exception as error:  # noqa: BLE001
        raise_for_error(error)

    if state == "not_found":
        raise HTTPException(status_code=404, detail="Task not found.")

    file_path = context["file_path"]
    if file_path.suffix.lower() != ".pdf":
        raise HTTPException(status_code=400, detail="Task file is not a PDF.")

    if page_num < 1:
        raise HTTPException(status_code=400, detail="page_num must be greater than 0.")

    try:
        return Response(content=build_pdf_page_preview(file_path, page_num), media_type="image/png")
    except IndexError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except Exception as error:  # noqa: BLE001
        raise_for_error(error)


@router.get("/tasks/{task_id}/pages/{page_num}/regions/{region_index}/image")
async def get_task_region_image(
    task_id: int,
    page_num: int,
    region_index: int,
    db: AsyncSession = Depends(get_db),
):
    try:
        context, state = await _get_task_region_context(task_id, page_num, region_index, db)
    except Exception as error:  # noqa: BLE001
        raise_for_error(error)

    if state == "not_found":
        raise HTTPException(status_code=404, detail="Task not found.")
    if state in {"invalid_page", "page_not_found"}:
        raise HTTPException(status_code=404, detail="Page not found.")
    if state == "region_not_found":
        raise HTTPException(status_code=404, detail="Region not found.")
    if state == "result_not_found":
        raise HTTPException(status_code=404, detail="Task result not found.")
    if state == "bbox_not_found":
        raise HTTPException(status_code=400, detail="Region bbox not found.")

    region = context["region"]
    bbox = region.get("layout_bbox") or region.get("bbox") or []
    region_type = str(region.get("type") or "").strip().lower()

    try:
        return Response(
            content=build_region_preview(
                context["file_path"],
                bbox,
                page_num=page_num,
                isolate_red=(region_type == "seal"),
            ),
            media_type="image/png",
        )
    except IndexError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except Exception as error:  # noqa: BLE001
        raise_for_error(error)
