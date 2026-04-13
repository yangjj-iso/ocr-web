from __future__ import annotations

import logging
from typing import Any

from .celery_app import celery_app
from .worker_executor import process_task_command_sync


logger = logging.getLogger(__name__)


class NonRetryableError(Exception):
    """Errors that should not be retried (invalid input, unsupported format, etc.)."""


class RetryableError(Exception):
    """Errors that are transient and can be retried (network timeout, service unavailable)."""


@celery_app.task(
    bind=True,
    name="ocr.compute.execute_command",
    autoretry_for=(RetryableError, ConnectionError, TimeoutError, OSError),
    dont_autoretry_for=(NonRetryableError, ValueError, KeyError),
    retry_backoff=True,
    retry_jitter=True,
    retry_kwargs={"max_retries": 3},
)
def execute_ocr_command(self, payload: dict[str, Any]) -> dict[str, Any]:
    logger.info("Celery compute task received: retries=%s", getattr(self.request, "retries", 0))
    try:
        return process_task_command_sync(payload, retry_count=int(getattr(self.request, "retries", 0)))
    except (ValueError, KeyError) as exc:
        logger.error("Non-retryable error in OCR task: %s", exc)
        raise NonRetryableError(str(exc)) from exc
    except (ConnectionError, TimeoutError, OSError) as exc:
        logger.warning("Retryable error in OCR task (attempt %d): %s", self.request.retries, exc)
        raise RetryableError(str(exc)) from exc
