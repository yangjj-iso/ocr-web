"""Task and ingestion domain operations."""

from __future__ import annotations

from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import OCRTask
from app.infrastructure.persistence import tasks as task_repository
from app.infrastructure.storage import save_upload_file as store_upload_file


async def save_upload_file(filename: str, content: bytes, relative_path: str = "") -> tuple[str, str]:
    return await store_upload_file(filename, content, relative_path)


async def create_task(
    db: AsyncSession,
    filename: str,
    file_path: str,
    file_type: str,
    mode: str = "layout",
) -> OCRTask:
    return await task_repository.create_task(db, filename, file_path, file_type, mode=mode)


async def get_task_detail(db: AsyncSession, task_id: int) -> OCRTask | None:
    return await task_repository.get_task_detail(db, task_id)


async def get_task_list(
    db: AsyncSession,
    page: int = 1,
    page_size: int = 20,
    folder: str = "",
) -> tuple[list[OCRTask], int]:
    return await task_repository.get_task_list(db, page, page_size, folder=folder)


async def search_tasks(
    db: AsyncSession,
    keyword: str,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[OCRTask], int]:
    return await task_repository.search_tasks(db, keyword, page, page_size)


async def delete_task(db: AsyncSession, task_id: int) -> bool:
    return await task_repository.delete_task(db, task_id)


async def delete_tasks_by_folder(db: AsyncSession, folder: str) -> int:
    return await task_repository.delete_tasks_by_folder(db, folder)


async def list_terminal_folders(db: AsyncSession) -> list[tuple[int, str, object]]:
    return await task_repository.list_terminal_folders(db)


async def list_folder_batch_pairs(db: AsyncSession) -> list[tuple[str, str]]:
    return await task_repository.list_folder_batch_pairs(db)


async def get_progress_tasks(db: AsyncSession, task_ids: list[int]) -> list[OCRTask]:
    return await task_repository.get_progress_tasks(db, task_ids)


async def list_task_ids_by_folder(db: AsyncSession, folder: str) -> list[int]:
    return await task_repository.list_task_ids_by_folder(db, folder)


def build_search_snippet(task: OCRTask, keyword: str, context: int = 50) -> str:
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


def folder_from_task_path(file_path: str) -> str:
    return str(Path(file_path).parent)


def _cut_around(text: str, keyword: str, context: int = 50) -> str:
    index = text.lower().index(keyword)
    start = max(0, index - context)
    end = min(len(text), index + len(keyword) + context)
    snippet = text[start:end].replace("\n", " ")
    prefix = "..." if start > 0 else ""
    suffix = "..." if end < len(text) else ""
    return f"{prefix}{snippet}{suffix}"


__all__ = [
    "build_search_snippet",
    "create_task",
    "delete_task",
    "delete_tasks_by_folder",
    "folder_from_task_path",
    "get_progress_tasks",
    "get_task_detail",
    "get_task_list",
    "list_folder_batch_pairs",
    "list_task_ids_by_folder",
    "list_terminal_folders",
    "save_upload_file",
    "search_tasks",
]
