"""File routes for original downloads, thumbnails, and PDF page previews."""

import logging

from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, raise_for_error, require_auth
from app.application.workflows.files import get_task_file_context
from app.core.preview import build_pdf_page_preview, build_thumbnail

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
