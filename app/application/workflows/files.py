"""File access orchestration."""

from __future__ import annotations

from pathlib import Path

from app.core.result_validation import normalize_result_pages
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


async def get_task_region_context(
    *,
    task_id: int,
    page_num: int,
    region_index: int,
    db,
) -> tuple[dict | None, str]:
    context, state = await get_task_file_context(task_id=task_id, db=db)
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

    return {
        **context,
        "page": page,
        "page_num": page_num,
        "region": region,
        "region_index": region_index,
    }, "ok"
