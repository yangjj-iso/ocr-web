from __future__ import annotations

import logging
from typing import Any

from .celery_app import celery_app
from .worker_executor import process_task_command_sync


logger = logging.getLogger(__name__)


@celery_app.task(
    bind=True,
    name="ocr.compute.execute_command",
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_jitter=True,
    retry_kwargs={"max_retries": 3},
)
def execute_ocr_command(self, payload: dict[str, Any]) -> dict[str, Any]:
    logger.info("Celery compute task received: retries=%s", getattr(self.request, "retries", 0))
    return process_task_command_sync(payload, retry_count=int(getattr(self.request, "retries", 0)))
