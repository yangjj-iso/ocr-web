"""
API Controller Layer: OCR Task Routes
处理 OCR 任务的上传、列表、详情、更新、删除及进度查询等 HTTP 接口。

架构说明：
这里的 API 层职责极为“轻量化”（Thin Controllers），它只负责：
1. 接收 HTTP 请求（解析 Query, Form, JSON Body）。
2. 执行基础的 HTTP 级别校验（如文件大小限制 `MAX_FILE_SIZE`、枚举值 `mode` 的正则约束）。
3. 解析依赖注入（如从 FastAPI 拿到 `db: AsyncSession`、`require_auth` 的鉴权状态）。
4. 【核心】将请求委托给 Application 层（即 `app.application.workflows.tasks`）执行真正的业务逻辑（Use Cases）。
5. 捕获异常并映射为标准的 FastAPI HTTPException（如 400, 404, 409）。
"""

import logging

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from fastapi.responses import JSONResponse, PlainTextResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import (
    cache_delete,
    cache_delete_pattern,
    get_db,
    invalidate_lists,
    invalidate_task,
    raise_for_error,
    raise_service_unavailable,
    require_auth,
)
from app.application.workflows.tasks import (
    build_task_export_payload,
    build_task_progress_response,
    delete_task_with_cache_context,
    delete_tasks_by_folder_with_cache_context,
    extract_fields_from_task,
    list_folder_summaries,
    list_task_payloads,
    load_task_detail_payload,
    search_task_payloads,
    submit_path_task,
    submit_upload_task,
    task_payload,
    update_task_result,
)
from app.schemas.tasks import (
    OCRTaskDetail,
    TaskProgressRequest,
    TaskProgressResponse,
)
from app.domains.batch_ai import batch_ai_service
from config import MAX_FILE_SIZE

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/ocr",
    tags=["Tasks"],
    dependencies=[Depends(require_auth)],
)


@router.post("/upload", response_model=OCRTaskDetail, status_code=status.HTTP_202_ACCEPTED)
async def upload_and_enqueue(
    file: UploadFile = File(...),
    relative_path: str = Form(""),
    mode: str = Query("vl", pattern="^(baidu_vl|vl|layout|ocr)$"),
    excel_path: str = Query(""),
    excel_init: int = Query(0),
    output_dir: str = Query(""),
    batch_id: str = Query(""),
    db: AsyncSession = Depends(get_db),
):
    if not file.filename:
        raise HTTPException(status_code=400, detail="Missing file name.")

    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail=f"File exceeds {MAX_FILE_SIZE // 1024 // 1024}MB.")

    try:
        task = await submit_upload_task(
            filename=file.filename,
            content=content,
            relative_path=relative_path,
            mode=mode,
            excel_path=excel_path,
            excel_init=excel_init,
            output_dir=output_dir,
            batch_id=batch_id,
            db=db,
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except Exception as error:  # noqa: BLE001
        raise_service_unavailable(error, "Task submit service is temporarily unavailable. Please retry later.")
    invalidate_lists()
    return task_payload(task)


@router.post("/upload-from-path", response_model=OCRTaskDetail, status_code=status.HTTP_202_ACCEPTED)
async def upload_from_path(
    body: dict,
    mode: str = Query("vl", pattern="^(baidu_vl|vl|layout|ocr)$"),
    excel_path: str = Query(""),
    excel_init: int = Query(0),
    output_dir: str = Query(""),
    batch_id: str = Query(""),
    db: AsyncSession = Depends(get_db),
):
    from app.api.deps import ensure_allowed_path

    try:
        file_path = ensure_allowed_path(body.get("file_path", ""), expect_file=True)
    except Exception as error:  # noqa: BLE001
        raise_for_error(error)

    file_type = file_path.suffix.lower()
    if file_type not in {".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".tif", ".pdf"}:
        raise HTTPException(status_code=400, detail=f"Unsupported file type: {file_type}")

    try:
        task = await submit_path_task(
            file_path=str(file_path),
            mode=mode,
            excel_path=excel_path,
            excel_init=excel_init,
            output_dir=output_dir,
            batch_id=batch_id,
            db=db,
        )
    except Exception as error:  # noqa: BLE001
        raise_service_unavailable(error, "Path task submit service is temporarily unavailable. Please retry later.")
    invalidate_lists()
    return task_payload(task)


@router.get("/tasks/search")
async def search_tasks_api(
    q: str = Query("", min_length=1),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    return await search_task_payloads(keyword=q, page=page, page_size=page_size, db=db)


@router.get("/tasks/folders")
async def list_folders(db: AsyncSession = Depends(get_db)):
    try:
        return await list_folder_summaries(db=db)
    except Exception as error:  # noqa: BLE001
        raise_service_unavailable(error, "Folder service is temporarily unavailable. Please retry later.")


@router.get("/tasks")
async def list_tasks(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=1000),
    folder: str = Query(""),
    db: AsyncSession = Depends(get_db),
):
    return await list_task_payloads(page=page, page_size=page_size, folder=folder, db=db)


@router.post("/tasks/progress", response_model=TaskProgressResponse)
async def get_tasks_progress(body: TaskProgressRequest, db: AsyncSession = Depends(get_db)):
    return await build_task_progress_response(task_ids=body.task_ids, db=db)


@router.get("/tasks/{task_id}", response_model=OCRTaskDetail)
async def get_task(task_id: int, db: AsyncSession = Depends(get_db)):
    payload, state = await load_task_detail_payload(task_id=task_id, db=db)
    if state == "not_found":
        raise HTTPException(status_code=404, detail="Task not found.")
    return payload


@router.put("/tasks/{task_id}", response_model=OCRTaskDetail)
async def update_task(task_id: int, body: dict, db: AsyncSession = Depends(get_db)):
    try:
        task, state = await update_task_result(task_id=task_id, body=body, db=db)
    except Exception as error:  # noqa: BLE001
        raise_for_error(error)

    if state == "not_found":
        raise HTTPException(status_code=404, detail="Task not found.")
    if state == "not_terminal":
        raise HTTPException(status_code=409, detail="Task result cannot be edited while it is still processing.")

    invalidate_task(task_id)
    return task_payload(task)


@router.delete("/tasks/{task_id}")
async def remove_task(task_id: int, db: AsyncSession = Depends(get_db)):
    deleted, affected_batch_ids = await delete_task_with_cache_context(task_id=task_id, db=db)
    if not deleted:
        raise HTTPException(status_code=404, detail="Task not found.")
    invalidate_task(task_id)
    batch_ai_service.invalidate_batch_ai_cache(affected_batch_ids)
    return {"message": "Deleted"}


@router.delete("/tasks/by-folder")
async def delete_tasks_for_folder(
    folder: str = Query(...),
    db: AsyncSession = Depends(get_db),
):
    deleted, affected_batch_ids = await delete_tasks_by_folder_with_cache_context(folder=folder, db=db)
    cache_delete_pattern("task:*")
    invalidate_lists()
    if deleted:
        batch_ai_service.invalidate_batch_ai_cache(affected_batch_ids)
    return {"deleted": deleted, "folder": folder}


@router.get("/tasks/{task_id}/export")
async def export_task(
    task_id: int,
    fmt: str = Query("txt", pattern="^(txt|json)$"),
    db: AsyncSession = Depends(get_db),
):
    payload, payload_type = await build_task_export_payload(task_id=task_id, fmt=fmt, db=db)
    if payload_type == "not_found":
        raise HTTPException(status_code=404, detail="Task not found.")

    if payload_type == "txt":
        return PlainTextResponse(
            content=str(payload.get("content", "") if isinstance(payload, dict) else payload or ""),
            headers={"Content-Disposition": f'attachment; filename="{payload["filename"]}.txt"'},
        )

    return JSONResponse(
        content=payload,
        headers={"Content-Disposition": f'attachment; filename="{payload["filename"]}.json"'},
    )


@router.get("/tasks/{task_id}/extract-fields")
async def get_task_extracted_fields(task_id: int, db: AsyncSession = Depends(get_db)):
    payload, state = await extract_fields_from_task(task_id=task_id, db=db)
    if state == "not_found":
        raise HTTPException(status_code=404, detail="Task not found.")
    if state == "not_done":
        raise HTTPException(status_code=409, detail="Field extraction requires a completed task.")
    return payload
