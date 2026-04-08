"""File access orchestration."""

from __future__ import annotations

from pathlib import Path

from app.domains.ingestion import task_service
from app.infrastructure.storage import ensure_allowed_path


async def get_task_file_context(*, task_id: int, db) -> tuple[dict | None, str]:
    task = await task_service.get_task_detail(db, task_id)
    if not task:
        return None, "not_found"

    file_path = ensure_allowed_path(task.file_path, expect_file=True)
    return {
        "task": task,
        "file_path": file_path,
        "suffix": Path(file_path).suffix.lower(),
    }, "ok"
