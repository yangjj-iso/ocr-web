"""
Application Layer: Task Use-Case Orchestration
基于“整洁架构（Clean Architecture）”的应用层工作流（Use Cases）。

架构说明：
1. 这里不处理任何 HTTP/Web 级别的逻辑（没有 FastAPI 的 Request/Response, HTTPException），保证核心业务与框架解耦。
2. 职责是充当“编排者（Orchestrator）”：
   - 接收来自 API 层的标准化 DTO（如 `submit_upload_task` 的参数）。
   - 调度多个 `app.domains` 中的业务领域服务（如 `task_service`, `archive_service`, `field_service`）。
   - 操作基础设施层设施（如 Redis 缓存更新 `cache_set`, Celery/Redis 队列入队 `enqueue_task`）。
   - 最后返回核心的领域实体（Entity）或包含核心状态的 Payload 字典供 API 层序列化。
"""

from __future__ import annotations

from datetime import datetime, timezone
import logging
from pathlib import Path

from sqlalchemy import func, or_, select

from app.core.result_validation import normalize_result_pages, serialize_pages_text
from app.db.models import ArchiveRecord, OCRTask
from app.domains.archive import archive_service
from app.domains.batch_ai import batch_ai_service
from app.domains.extraction import field_service
from app.domains.ingestion import task_service
from app.infrastructure.cache import (
    LIST_TTL,
    SEARCH_TTL,
    TASK_TTL,
    cache_delete,
    cache_get,
    cache_set,
)
from app.infrastructure.queue import OCRJob, enqueue_task
from app.schemas.tasks import OCRTaskDetail, OCRTaskOut, TaskProgressItem, TaskProgressResponse
from app.shared.contracts import TaskProgressSnapshot

TERMINAL_STATUSES = {"done", "failed"}
logger = logging.getLogger(__name__)


def task_payload(task: OCRTask) -> dict:
    return OCRTaskDetail.model_validate(task).model_dump(mode="json")


async def submit_upload_task(
    *,
    filename: str,
    content: bytes,
    relative_path: str,
    mode: str,
    excel_path: str,
    excel_init: int,
    output_dir: str,
    batch_id: str,
    db,
):
    """Store file, create task, and enqueue OCR processing."""
    file_path, file_type = await task_service.save_upload_file(filename, content, relative_path)
    task = await task_service.create_task(db, filename, file_path, file_type, mode=mode)
    logger.info(
        "submit_upload_task created task: id=%s, mode=%s, file=%s",
        task.id,
        mode,
        file_path,
    )
    await enqueue_task(
        OCRJob(
            task_id=task.id,
            mode=mode,
            filename=task.filename,
            file_path=task.file_path,
            file_type=task.file_type,
            excel_path=excel_path,
            excel_init=excel_init,
            output_dir=output_dir,
            batch_id=batch_id,
        )
    )
    logger.info("submit_upload_task enqueued task: id=%s, mode=%s", task.id, mode)
    return task


async def submit_path_task(
    *,
    file_path: str,
    mode: str,
    excel_path: str,
    excel_init: int,
    output_dir: str,
    batch_id: str,
    db,
):
    """Create task from an allowed local path and enqueue OCR processing."""
    path_obj = Path(file_path)
    task = await task_service.create_task(
        db,
        path_obj.name,
        file_path,
        path_obj.suffix.lower(),
        mode=mode,
    )
    logger.info(
        "submit_path_task created task: id=%s, mode=%s, file=%s",
        task.id,
        mode,
        file_path,
    )
    await enqueue_task(
        OCRJob(
            task_id=task.id,
            mode=mode,
            filename=task.filename,
            file_path=task.file_path,
            file_type=task.file_type,
            excel_path=excel_path,
            excel_init=excel_init,
            output_dir=output_dir,
            batch_id=batch_id,
        )
    )
    logger.info("submit_path_task enqueued task: id=%s, mode=%s", task.id, mode)
    return task


async def search_task_payloads(*, keyword: str, page: int, page_size: int, db, tenant_id: str = "") -> dict:
    cache_key = f"search:{tenant_id}:{keyword}:{page}:{page_size}"
    cached = cache_get(cache_key)
    if cached:
        return cached

    tasks, total = await task_service.search_tasks(db, keyword, page, page_size, tenant_id=tenant_id)
    payload = {
        "total": total,
        "tasks": [
            {
                **OCRTaskOut.model_validate(task).model_dump(mode="json"),
                "snippet": task_service.build_search_snippet(task, keyword),
            }
            for task in tasks
        ],
    }
    cache_set(cache_key, payload, SEARCH_TTL)
    return payload


async def list_folder_summaries(*, db, tenant_id: str = "") -> list[dict]:
    cache_key = f"folders:terminal:{tenant_id}"
    cached = cache_get(cache_key)
    if cached:
        return cached

    rows = await task_service.list_terminal_folders(db, tenant_id=tenant_id)
    folders: dict[str, dict] = {}
    for task_id, file_path, created_at in rows:
        if not file_path:
            continue
        folder = task_service.folder_from_task_path(file_path)
        current = folders.setdefault(
            folder,
            {
                "folder": folder,
                "count": 0,
                "last_time": None,
                "latest_task_id": task_id,
                "batch_ids": [],
            },
        )
        current["count"] += 1
        if created_at and (current["last_time"] is None or created_at > current["last_time"]):
            current["last_time"] = created_at
            current["latest_task_id"] = task_id

    try:
        archive_rows = await task_service.list_folder_batch_pairs(db, tenant_id=tenant_id)
        folder_batches: dict[str, list[str]] = {}
        for batch_folder, batch_id in archive_rows:
            if not batch_folder:
                continue
            normalized_folder = str(batch_folder).rstrip("/\\")
            folder_batches.setdefault(normalized_folder, [])
            if batch_id not in folder_batches[normalized_folder]:
                folder_batches[normalized_folder].append(batch_id)
        for folder_data in folders.values():
            folder_data["batch_ids"] = folder_batches.get(folder_data["folder"], [])
    except Exception:
        for folder_data in folders.values():
            folder_data["batch_ids"] = []

    epoch = datetime.min.replace(tzinfo=timezone.utc)
    result = sorted(folders.values(), key=lambda item: item["last_time"] or epoch, reverse=True)
    cache_set(cache_key, result, LIST_TTL)
    return result


async def list_task_payloads(*, page: int, page_size: int, folder: str, db, tenant_id: str = "") -> dict:
    cache_key = f"list:{tenant_id}:{page}:{page_size}:{folder}"
    cached = cache_get(cache_key)
    if cached:
        return cached

    tasks, total = await task_service.get_task_list(db, page, page_size, folder=folder, tenant_id=tenant_id)
    payload = {
        "total": total,
        "tasks": [OCRTaskOut.model_validate(task).model_dump(mode="json") for task in tasks],
    }
    cache_set(cache_key, payload, LIST_TTL)
    return payload


async def build_task_progress_response(*, task_ids: list[int], db, tenant_id: str = "") -> TaskProgressResponse:
    requested_ids = [int(task_id) for task_id in task_ids if task_id is not None]
    if not requested_ids:
        snapshot = TaskProgressSnapshot()
        return TaskProgressResponse(tasks=[], **snapshot.model_dump())

    rows = await task_service.get_progress_tasks(db, requested_ids, tenant_id=tenant_id)
    task_map = {task.id: task for task in rows}
    items: list[TaskProgressItem] = []
    counts = {"done": 0, "failed": 0, "processing": 0, "pending": 0}

    for task_id in requested_ids:
        task = task_map.get(task_id)
        if task is None:
            status_value = "failed"
            error_message = "Task not found."
        else:
            status_value = task.status or "pending"
            error_message = task.error_message

        if status_value not in counts:
            status_value = "processing"
        counts[status_value] += 1
        items.append(TaskProgressItem(id=task_id, status=status_value, error_message=error_message))

    snapshot = TaskProgressSnapshot(
        total=len(requested_ids),
        done_count=counts["done"],
        failed_count=counts["failed"],
        processing_count=counts["processing"],
        pending_count=counts["pending"],
    )
    return TaskProgressResponse(tasks=items, **snapshot.model_dump())


async def load_task_detail_payload(*, task_id: int, db, tenant_id: str = "") -> tuple[dict | None, str]:
    cached = cache_get(f"task:{task_id}")
    if cached and cached.get("status") in TERMINAL_STATUSES:
        return cached, "ok"

    task = await task_service.get_task_detail(db, task_id, tenant_id=tenant_id)
    if not task:
        return None, "not_found"

    payload = task_payload(task)
    if task.status in TERMINAL_STATUSES:
        cache_set(f"task:{task_id}", payload, TASK_TTL)
    else:
        cache_delete(f"task:{task_id}")
    return payload, "ok"


async def build_task_export_payload(*, task_id: int, fmt: str, db, tenant_id: str = "") -> tuple[dict | str | None, str]:
    task = await task_service.get_task_detail(db, task_id, tenant_id=tenant_id)
    if not task:
        return None, "not_found"

    if fmt == "txt":
        return {"filename": task.filename, "content": task.full_text or ""}, "txt"

    return {
        "filename": task.filename,
        "page_count": task.page_count,
        "full_text": task.full_text,
        "result_json": task.result_json,
    }, "json"


async def collect_affected_batch_ids(*, task_ids: list[int], db) -> set[str]:
    normalized_ids = sorted({int(task_id) for task_id in task_ids if task_id is not None})
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
    return batch_ai_service.normalize_batch_ids(rows)


async def delete_task_with_cache_context(*, task_id: int, db, tenant_id: str = "") -> tuple[bool, set[str]]:
    affected_batch_ids = await collect_affected_batch_ids(task_ids=[task_id], db=db)
    deleted = await task_service.delete_task(db, task_id, tenant_id=tenant_id)
    return deleted, affected_batch_ids


async def delete_tasks_by_folder_with_cache_context(*, folder: str, db, tenant_id: str = "") -> tuple[int, set[str]]:
    task_id_rows = await task_service.list_task_ids_by_folder(db, folder, tenant_id=tenant_id)
    affected_batch_ids = await collect_affected_batch_ids(task_ids=task_id_rows, db=db)
    deleted = await task_service.delete_tasks_by_folder(db, folder, tenant_id=tenant_id)
    return deleted, affected_batch_ids


async def update_task_result(*, task_id: int, body: dict, db, tenant_id: str = "") -> tuple[OCRTask | None, str]:
    task = await task_service.get_task_detail(db, task_id, tenant_id=tenant_id)
    if not task:
        return None, "not_found"
    if task.status not in TERMINAL_STATUSES:
        return None, "not_terminal"

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
        fields = field_service.extract_fields(task.filename, task.full_text or "", task.result_json, task.page_count)
        await archive_service.save_archive_record(
            db,
            task.id,
            existing_record.batch_id if existing_record else "",
            existing_record.batch_folder if existing_record else str(Path(task.file_path).parent),
            fields,
        )

    return task, "ok"


async def extract_fields_from_task(*, task_id: int, db, tenant_id: str = "") -> tuple[dict | None, str]:
    task = await task_service.get_task_detail(db, task_id, tenant_id=tenant_id)
    if not task:
        return None, "not_found"
    if task.status != "done":
        return None, "not_done"

    fields = field_service.extract_fields(task.filename, task.full_text or "", task.result_json, task.page_count)
    contract = field_service.build_field_extraction_result(fields)
    return {
        "task_id": task_id,
        "fields": contract.fields,
        "confidence": contract.confidence,
        "review_recommendation": contract.review_recommendation,
    }, "ok"
