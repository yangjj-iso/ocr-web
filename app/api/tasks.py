"""OCR Task routes — upload, list, detail, update, delete, progress, export, field extraction."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Response, UploadFile, status
from fastapi.responses import JSONResponse, PlainTextResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import (
    cache_delete,
    cache_delete_pattern,
    cache_get,
    cache_set,
    ensure_allowed_path,
    get_db,
    invalidate_lists,
    invalidate_task,
    raise_for_error,
    raise_service_unavailable,
    require_auth,
    LIST_TTL,
    SEARCH_TTL,
    TASK_TTL,
)
from app.core.result_validation import normalize_result_pages, serialize_pages_text
from app.db.models import ArchiveRecord, OCRTask
from app.infrastructure.persistence import tasks as task_repository
from app.infrastructure.queue import OCRJob, enqueue_task
from app.infrastructure.storage import save_upload_file as store_upload_file
from app.schemas.tasks import (
    OCRTaskDetail,
    OCRTaskOut,
    TaskProgressItem,
    TaskProgressRequest,
    TaskProgressResponse,
)
from app.services.archive_service import save_archive_record
from app.services.batch_cache_service import invalidate_batch_ai_cache, normalize_batch_ids
from app.services.excel_export import extract_fields
from app.services.llm_field_extraction_service import compare_rule_and_llm_fields
from app.shared.contracts import FieldExtractionResult, TaskProgressSnapshot
from config import MAX_FILE_SIZE

logger = logging.getLogger(__name__)
TERMINAL_STATUSES = {"done", "failed"}

router = APIRouter(
    prefix="/api/ocr",
    tags=["Tasks"],
    dependencies=[Depends(require_auth)],
)


# ---------------------------------------------------------------------------
# Helpers (inlined from former application/workflows/tasks.py)
# ---------------------------------------------------------------------------


def _task_payload(task: OCRTask) -> dict:
    return OCRTaskDetail.model_validate(task).model_dump(mode="json")


def _build_search_snippet(task: OCRTask, keyword: str, context: int = 50) -> str:
    lowered = keyword.lower()
    if task.full_text and lowered in task.full_text.lower():
        return _cut_around(task.full_text, lowered, context)
    if task.result_json:
        pages = task.result_json if isinstance(task.result_json, list) else [task.result_json]
        for page in pages:
            if not isinstance(page, dict):
                continue
            for region in page.get("regions", []):
                content = str(region.get("content", "") or "")
                if lowered in content.lower():
                    return _cut_around(content, lowered, context)
            for line in page.get("lines", []):
                text = str(line.get("text", "") or "")
                if lowered in text.lower():
                    return _cut_around(text, lowered, context)
    if lowered in (task.filename or "").lower():
        return f"Filename match: {task.filename}"
    return ""


def _cut_around(text: str, keyword: str, context: int = 50) -> str:
    index = text.lower().index(keyword)
    start = max(0, index - context)
    end = min(len(text), index + len(keyword) + context)
    snippet = text[start:end].replace("\n", " ")
    prefix = "..." if start > 0 else ""
    suffix = "..." if end < len(text) else ""
    return f"{prefix}{snippet}{suffix}"


async def _collect_affected_batch_ids(task_ids: list[int], db) -> set[str]:
    normalized_ids = sorted({int(tid) for tid in task_ids if tid is not None})
    if not normalized_ids:
        return set()
    rows = (
        await db.execute(
            select(ArchiveRecord.batch_id)
            .where(
                ArchiveRecord.task_id.in_(normalized_ids),
                ArchiveRecord.batch_id.is_not(None),
                ArchiveRecord.batch_id != "",
            )
            .distinct()
        )
    ).scalars().all()
    return normalize_batch_ids(rows)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.post("/upload", response_model=OCRTaskDetail, status_code=status.HTTP_202_ACCEPTED)
async def upload_and_enqueue(
    file: UploadFile = File(...),
    relative_path: str = Form(""),
    mode: str = Query("vl", pattern="^(baidu_vl|vl|layout|ocr)$"),
    excel_path: str = Query(""),
    excel_init: int = Query(0),
    output_dir: str = Query(""),
    batch_id: str = Query(""),
    response: Response = None,
    db: AsyncSession = Depends(get_db),
):
    logger.warning(
        "Deprecated compatibility endpoint used: POST /api/ocr/upload. "
        "Prefer java-control-plane /api/ocr/upload for control-plane ownership."
    )
    if response is not None:
        response.headers["Deprecation"] = "true"
        response.headers["Warning"] = '299 - "Deprecated compatibility endpoint. Use java-control-plane /api/ocr/upload."'

    if not file.filename:
        raise HTTPException(status_code=400, detail="Missing file name.")

    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail=f"File exceeds {MAX_FILE_SIZE // 1024 // 1024}MB.")

    try:
        file_path, file_type = await store_upload_file(file.filename, content, relative_path)
        task = await task_repository.create_task(db, file.filename, file_path, file_type, mode=mode)
        await enqueue_task(
            OCRJob(
                task_id=task.id, mode=mode, filename=task.filename,
                file_path=task.file_path, file_type=task.file_type,
                excel_path=excel_path, excel_init=excel_init,
                output_dir=output_dir, batch_id=batch_id,
            )
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except Exception as error:  # noqa: BLE001
        raise_service_unavailable(error, "Task submit service is temporarily unavailable. Please retry later.")
    invalidate_lists()
    return _task_payload(task)


@router.post("/upload-from-path", response_model=OCRTaskDetail, status_code=status.HTTP_202_ACCEPTED)
async def upload_from_path(
    body: dict,
    mode: str = Query("vl", pattern="^(baidu_vl|vl|layout|ocr)$"),
    excel_path: str = Query(""),
    excel_init: int = Query(0),
    output_dir: str = Query(""),
    batch_id: str = Query(""),
    response: Response = None,
    db: AsyncSession = Depends(get_db),
):
    logger.warning(
        "Deprecated compatibility endpoint used: POST /api/ocr/upload-from-path. "
        "Prefer java-control-plane /api/ocr/upload-from-path for control-plane ownership."
    )
    if response is not None:
        response.headers["Deprecation"] = "true"
        response.headers["Warning"] = '299 - "Deprecated compatibility endpoint. Use java-control-plane /api/ocr/upload-from-path."'

    try:
        file_path = ensure_allowed_path(body.get("file_path", ""), expect_file=True)
    except Exception as error:  # noqa: BLE001
        raise_for_error(error)

    file_type = file_path.suffix.lower()
    if file_type not in {".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".tif", ".pdf"}:
        raise HTTPException(status_code=400, detail=f"Unsupported file type: {file_type}")

    try:
        task = await task_repository.create_task(db, file_path.name, str(file_path), file_type, mode=mode)
        await enqueue_task(
            OCRJob(
                task_id=task.id, mode=mode, filename=task.filename,
                file_path=task.file_path, file_type=task.file_type,
                excel_path=excel_path, excel_init=excel_init,
                output_dir=output_dir, batch_id=batch_id,
            )
        )
    except Exception as error:  # noqa: BLE001
        raise_service_unavailable(error, "Path task submit service is temporarily unavailable. Please retry later.")
    invalidate_lists()
    return _task_payload(task)


@router.get("/tasks/search")
async def search_tasks_api(
    q: str = Query("", min_length=1),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    cache_key = f"search:{q}:{page}:{page_size}"
    cached = cache_get(cache_key)
    if cached:
        return cached

    tasks, total = await task_repository.search_tasks(db, q, page, page_size)
    payload = {
        "total": total,
        "tasks": [
            {**OCRTaskOut.model_validate(t).model_dump(mode="json"), "snippet": _build_search_snippet(t, q)}
            for t in tasks
        ],
    }
    cache_set(cache_key, payload, SEARCH_TTL)
    return payload


@router.get("/tasks/folders")
async def list_folders(db: AsyncSession = Depends(get_db)):
    try:
        cache_key = "folders:terminal"
        cached = cache_get(cache_key)
        if cached:
            return cached

        rows = await task_repository.list_terminal_folders(db)
        folders: dict[str, dict] = {}
        for task_id, file_path, created_at in rows:
            if not file_path:
                continue
            folder = str(Path(file_path).parent)
            current = folders.setdefault(
                folder,
                {"folder": folder, "count": 0, "last_time": None, "latest_task_id": task_id, "batch_ids": []},
            )
            current["count"] += 1
            if created_at and (current["last_time"] is None or created_at > current["last_time"]):
                current["last_time"] = created_at
                current["latest_task_id"] = task_id

        try:
            archive_rows = await task_repository.list_folder_batch_pairs(db)
            folder_batches: dict[str, list[str]] = {}
            for batch_folder, bid in archive_rows:
                if not batch_folder:
                    continue
                normalized_folder = str(batch_folder).rstrip("/\\")
                folder_batches.setdefault(normalized_folder, [])
                if bid not in folder_batches[normalized_folder]:
                    folder_batches[normalized_folder].append(bid)
            for folder_data in folders.values():
                folder_data["batch_ids"] = folder_batches.get(folder_data["folder"], [])
        except Exception:
            for folder_data in folders.values():
                folder_data["batch_ids"] = []

        epoch = datetime.min.replace(tzinfo=timezone.utc)
        result = sorted(folders.values(), key=lambda item: item["last_time"] or epoch, reverse=True)
        cache_set(cache_key, result, LIST_TTL)
        return result
    except Exception as error:  # noqa: BLE001
        raise_service_unavailable(error, "Folder service is temporarily unavailable. Please retry later.")


@router.get("/tasks")
async def list_tasks(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=1000),
    folder: str = Query(""),
    db: AsyncSession = Depends(get_db),
):
    cache_key = f"list:{page}:{page_size}:{folder}"
    cached = cache_get(cache_key)
    if cached:
        return cached

    tasks, total = await task_repository.get_task_list(db, page, page_size, folder=folder)
    payload = {
        "total": total,
        "tasks": [OCRTaskOut.model_validate(t).model_dump(mode="json") for t in tasks],
    }
    cache_set(cache_key, payload, LIST_TTL)
    return payload


@router.post("/tasks/progress", response_model=TaskProgressResponse)
async def get_tasks_progress(body: TaskProgressRequest, db: AsyncSession = Depends(get_db)):
    requested_ids = [int(tid) for tid in body.task_ids if tid is not None]
    if not requested_ids:
        snapshot = TaskProgressSnapshot()
        return TaskProgressResponse(tasks=[], **snapshot.model_dump())

    rows = await task_repository.get_progress_tasks(db, requested_ids)
    task_map = {t.id: t for t in rows}
    items: list[TaskProgressItem] = []
    counts = {"done": 0, "failed": 0, "processing": 0, "pending": 0}

    for tid in requested_ids:
        task = task_map.get(tid)
        if task is None:
            status_value = "failed"
            error_message = "Task not found."
        else:
            status_value = task.status or "pending"
            error_message = task.error_message
        if status_value not in counts:
            status_value = "processing"
        counts[status_value] += 1
        items.append(TaskProgressItem(id=tid, status=status_value, error_message=error_message))

    snapshot = TaskProgressSnapshot(
        total=len(requested_ids),
        done_count=counts["done"],
        failed_count=counts["failed"],
        processing_count=counts["processing"],
        pending_count=counts["pending"],
    )
    return TaskProgressResponse(tasks=items, **snapshot.model_dump())


@router.get("/tasks/{task_id}", response_model=OCRTaskDetail)
async def get_task(task_id: int, db: AsyncSession = Depends(get_db)):
    cached = cache_get(f"task:{task_id}")
    if cached and cached.get("status") in TERMINAL_STATUSES:
        return cached

    task = await task_repository.get_task_detail(db, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found.")

    payload = _task_payload(task)
    if task.status in TERMINAL_STATUSES:
        cache_set(f"task:{task_id}", payload, TASK_TTL)
    else:
        cache_delete(f"task:{task_id}")
    return payload


@router.put("/tasks/{task_id}", response_model=OCRTaskDetail)
async def update_task(task_id: int, body: dict, db: AsyncSession = Depends(get_db)):
    try:
        task = await task_repository.get_task_detail(db, task_id)
        if not task:
            raise HTTPException(status_code=404, detail="Task not found.")
        if task.status not in TERMINAL_STATUSES:
            raise HTTPException(status_code=409, detail="Task result cannot be edited while it is still processing.")

        if "result_json" in body:
            pages = normalize_result_pages(body["result_json"])
            task.result_json = pages
            task.full_text = serialize_pages_text(pages)
            task.page_count = len(pages)
        elif "full_text" in body:
            task.full_text = str(body["full_text"] or "")

        await db.commit()
        await db.refresh(task)

        if task.result_json:
            existing_record = (
                await db.execute(select(ArchiveRecord).where(ArchiveRecord.task_id == task.id))
            ).scalar_one_or_none()
            fields = extract_fields(task.filename, task.full_text or "", task.result_json, task.page_count)
            fields = {str(k): str(v or "") for k, v in (fields or {}).items()}
            await save_archive_record(
                db,
                task.id,
                existing_record.batch_id if existing_record else "",
                existing_record.batch_folder if existing_record else str(Path(task.file_path).parent),
                fields,
            )
    except HTTPException:
        raise
    except Exception as error:  # noqa: BLE001
        raise_for_error(error)

    invalidate_task(task_id)
    return _task_payload(task)


@router.delete("/tasks/{task_id}")
async def remove_task(task_id: int, db: AsyncSession = Depends(get_db)):
    affected_batch_ids = await _collect_affected_batch_ids([task_id], db)
    deleted = await task_repository.delete_task(db, task_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Task not found.")
    invalidate_task(task_id)
    invalidate_batch_ai_cache(affected_batch_ids)
    return {"message": "Deleted"}


@router.delete("/tasks/by-folder")
async def delete_tasks_for_folder(
    folder: str = Query(...),
    db: AsyncSession = Depends(get_db),
):
    task_id_rows = await task_repository.list_task_ids_by_folder(db, folder)
    affected_batch_ids = await _collect_affected_batch_ids(task_id_rows, db)
    deleted = await task_repository.delete_tasks_by_folder(db, folder)
    cache_delete_pattern("task:*")
    invalidate_lists()
    if deleted:
        invalidate_batch_ai_cache(affected_batch_ids)
    return {"deleted": deleted, "folder": folder}


@router.get("/tasks/{task_id}/export")
async def export_task(
    task_id: int,
    fmt: str = Query("txt", pattern="^(txt|json)$"),
    db: AsyncSession = Depends(get_db),
):
    task = await task_repository.get_task_detail(db, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found.")

    if fmt == "txt":
        return PlainTextResponse(
            content=task.full_text or "",
            headers={"Content-Disposition": f'attachment; filename="{task.filename}.txt"'},
        )

    return JSONResponse(
        content={
            "filename": task.filename,
            "page_count": task.page_count,
            "full_text": task.full_text,
            "result_json": task.result_json,
        },
        headers={"Content-Disposition": f'attachment; filename="{task.filename}.json"'},
    )


@router.get("/tasks/{task_id}/extract-fields")
async def get_task_extracted_fields(task_id: int, db: AsyncSession = Depends(get_db)):
    task = await task_repository.get_task_detail(db, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found.")
    if task.status != "done":
        raise HTTPException(status_code=409, detail="Field extraction requires a completed task.")

    fields = extract_fields(task.filename, task.full_text or "", task.result_json, task.page_count)
    fields = {str(k): str(v or "") for k, v in (fields or {}).items()}
    review_recommendation = {k: "review" if not str(v or "").strip() else "accepted" for k, v in fields.items()}
    return {
        "task_id": task_id,
        "fields": fields,
        "confidence": {},
        "review_recommendation": review_recommendation,
    }