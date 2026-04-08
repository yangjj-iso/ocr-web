"""Shared API dependencies and HTTP error helpers."""

import logging

from fastapi import HTTPException, status

from app.core.auth import require_auth  # noqa: F401
from app.core.exceptions import AppError
from app.core.path_security import PathSecurityError as LegacyPathSecurityError
from app.core.path_security import ensure_allowed_path  # noqa: F401
from app.core.redis_cache import (  # noqa: F401
    LIST_TTL,
    SEARCH_TTL,
    TASK_TTL,
    cache_delete,
    cache_delete_pattern,
    cache_get,
    cache_set,
    invalidate_lists,
    invalidate_task,
)
from app.core.result_validation import ResultValidationError as LegacyResultValidationError
from app.db.database import get_db  # noqa: F401

logger = logging.getLogger(__name__)

TERMINAL_STATUSES = {"done", "failed"}


def raise_for_error(error: Exception) -> None:
    """Convert domain and legacy exceptions into HTTP exceptions."""
    if isinstance(error, AppError):
        raise HTTPException(status_code=error.status_code, detail=error.detail) from error

    if isinstance(error, LegacyPathSecurityError):
        code = (
            status.HTTP_403_FORBIDDEN
            if "outside allowed roots" in str(error)
            else status.HTTP_400_BAD_REQUEST
        )
        raise HTTPException(status_code=code, detail=str(error)) from error

    if isinstance(error, LegacyResultValidationError):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error

    if hasattr(error, "status_code") and hasattr(error, "detail"):
        raise HTTPException(status_code=error.status_code, detail=error.detail) from error

    raise error


def raise_service_unavailable(error: Exception, detail: str) -> None:
    """Map unexpected dependency failures to 503 while preserving business errors."""
    try:
        raise_for_error(error)
    except HTTPException:
        raise
    except Exception:
        logger.exception(detail)
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=detail) from error
