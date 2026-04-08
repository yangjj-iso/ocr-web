"""Persistence adapters (database models/sessions)."""

from app.db.database import get_db, init_db
from app.infrastructure.persistence.tasks import (
    create_task,
    delete_task,
    delete_tasks_by_folder,
    get_progress_tasks,
    get_task_detail,
    get_task_list,
    list_folder_batch_pairs,
    list_task_ids_by_folder,
    list_terminal_folders,
    search_tasks,
)

__all__ = [
    "create_task",
    "delete_task",
    "delete_tasks_by_folder",
    "get_db",
    "get_progress_tasks",
    "get_task_detail",
    "get_task_list",
    "init_db",
    "list_folder_batch_pairs",
    "list_task_ids_by_folder",
    "list_terminal_folders",
    "search_tasks",
]
