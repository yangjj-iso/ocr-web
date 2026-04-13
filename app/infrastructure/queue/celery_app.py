from __future__ import annotations

from config import (
    CELERY_BROKER_URL,
    CELERY_RESULT_BACKEND,
    CELERY_TASK_EXCHANGE,
    CELERY_TASK_QUEUE,
    CELERY_TASK_ROUTING_KEY,
    MQ_PREFETCH_COUNT,
)

try:  # pragma: no cover - exercised in deployment environments
    from celery import Celery
except ImportError as exc:  # pragma: no cover - depends on optional runtime extras
    raise RuntimeError("Celery is required for the compute worker runtime.") from exc


celery_app = Celery(
    "ocr_compute_worker",
    broker=CELERY_BROKER_URL,
    backend=CELERY_RESULT_BACKEND,
    include=["app.infrastructure.queue.celery_tasks"],
)

celery_app.conf.update(
    task_default_queue=CELERY_TASK_QUEUE,
    task_default_exchange=CELERY_TASK_EXCHANGE,
    task_default_exchange_type="direct",
    task_default_routing_key=CELERY_TASK_ROUTING_KEY,
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="Asia/Shanghai",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    task_acks_on_failure_or_timeout=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=MQ_PREFETCH_COUNT,
    broker_connection_retry_on_startup=True,
    broker_transport_options={"confirm_publish": True},
    # Worker concurrency & memory management
    worker_max_tasks_per_child=50,
    worker_max_memory_per_child=2_000_000,  # 2GB
)
