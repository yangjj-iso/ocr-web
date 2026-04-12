from __future__ import annotations

import socket
import asyncio
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status

from config import (
    CELERY_TASK_QUEUE,
    COMPUTE_WORKER_ID,
    CONTROL_PLANE_INTERNAL_TOKEN,
    MQ_COMMAND_QUEUE,
    WORKER_METRICS_ENABLED,
    WORKER_METRICS_HOST,
    WORKER_METRICS_PORT,
)


router = APIRouter(prefix="/internal/api/v1/worker", tags=["worker-metrics"])


def require_internal_token(request: Request) -> None:
    expected = (CONTROL_PLANE_INTERNAL_TOKEN or "").strip()
    if not expected:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Internal token is not configured.")
    header = request.headers.get("Authorization", "")
    if header != f"Bearer {expected}":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid internal token.")


@router.get("/metrics")
async def worker_metrics(_: None = Depends(require_internal_token)) -> dict[str, Any]:
    celery = await asyncio.to_thread(_inspect_celery_workers)
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "worker": {
            "worker_id": COMPUTE_WORKER_ID,
            "hostname": socket.gethostname(),
            "command_queue": MQ_COMMAND_QUEUE,
            "celery_queue": CELERY_TASK_QUEUE,
        },
        "prometheus_exporter": {
            "enabled": WORKER_METRICS_ENABLED,
            "host": WORKER_METRICS_HOST,
            "port": WORKER_METRICS_PORT,
        },
        "celery": celery,
    }


def _inspect_celery_workers() -> dict[str, Any]:
    default = {
        "available": False,
        "detail": "No Celery workers reported.",
        "worker_count": 0,
        "active_count": 0,
        "reserved_count": 0,
        "scheduled_count": 0,
        "workers": [],
    }
    try:
        from app.infrastructure.queue.celery_app import celery_app
    except Exception as exc:  # noqa: BLE001
        return {**default, "detail": str(exc)}

    try:
        inspector = celery_app.control.inspect(timeout=1)
        active = inspector.active() or {}
        reserved = inspector.reserved() or {}
        scheduled = inspector.scheduled() or {}
    except Exception as exc:  # noqa: BLE001
        return {**default, "detail": str(exc)}

    worker_names = sorted(set(active) | set(reserved) | set(scheduled))
    if not worker_names:
        return default
    workers = [
        {
            "name": name,
            "active_count": len(active.get(name) or []),
            "reserved_count": len(reserved.get(name) or []),
            "scheduled_count": len(scheduled.get(name) or []),
        }
        for name in worker_names
    ]
    return {
        "available": True,
        "detail": "Celery workers inspected.",
        "worker_count": len(workers),
        "active_count": sum(item["active_count"] for item in workers),
        "reserved_count": sum(item["reserved_count"] for item in workers),
        "scheduled_count": sum(item["scheduled_count"] for item in workers),
        "workers": workers,
    }
