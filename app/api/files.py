"""File routes for original downloads, thumbnails, PDF page previews, and region crops."""

import logging

from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, raise_for_error, require_auth
from app.application.workflows.files import get_task_file_context, get_task_region_context
from app.core.preview import build_pdf_page_preview, build_region_preview, build_thumbnail

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/ocr",
    tags=["Files"],
    dependencies=[Depends(require_auth)],
)


@router.get("/tasks/{task_id}/file")
async def get_task_file(task_id: int, db: AsyncSession = Depends(get_db)):
    try:
        context, state = await get_task_file_context(task_id=task_id, db=db)
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
        context, state = await get_task_file_context(task_id=task_id, db=db)
    except Exception as error:  # noqa: BLE001
        raise_for_error(error)

    if state == "not_found":
        raise HTTPException(status_code=404, detail="Task not found.")

    return Response(content=build_thumbnail(context["file_path"]), media_type="image/png")


@router.get("/tasks/{task_id}/pages/{page_num}/image")
async def get_task_page_image(task_id: int, page_num: int, db: AsyncSession = Depends(get_db)):
    try:
        context, state = await get_task_file_context(task_id=task_id, db=db)
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
        context, state = await get_task_region_context(
            task_id=task_id,
            page_num=page_num,
            region_index=region_index,
            db=db,
        )
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
