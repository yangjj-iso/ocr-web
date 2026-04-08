from __future__ import annotations

import logging
from threading import Lock

from config import WORKER_METRICS_ENABLED, WORKER_METRICS_HOST, WORKER_METRICS_PORT

logger = logging.getLogger(__name__)

try:
    from prometheus_client import Counter, Gauge, Histogram, start_http_server
except ImportError:  # pragma: no cover - optional runtime dependency
    Counter = Gauge = Histogram = None
    start_http_server = None


_server_started = False
_server_lock = Lock()

if Counter is not None and Gauge is not None and Histogram is not None:
    _QUEUE_DEPTH = Gauge(
        "ocr_compute_worker_queue_depth",
        "Current RabbitMQ command queue depth observed by the worker.",
        labelnames=("queue",),
    )
    _INFLIGHT_TASKS = Gauge(
        "ocr_compute_worker_inflight_tasks",
        "Number of OCR commands currently executing in this worker process.",
        labelnames=("mode",),
    )
    _PAUSED_TASKS_TOTAL = Counter(
        "ocr_compute_worker_paused_tasks_total",
        "Total number of tasks paused for human review by this worker process.",
        labelnames=("mode",),
    )
    _PAGE_PROCESSING_SECONDS = Histogram(
        "ocr_compute_worker_page_processing_seconds",
        "Observed end-to-end latency for a single processed page.",
        labelnames=("mode",),
        buckets=(0.25, 0.5, 1, 2, 5, 10, 20, 30, 60, 120, 300),
    )
    _GPU_CACHE_CLEARS_TOTAL = Counter(
        "ocr_compute_worker_gpu_cache_clears_total",
        "Total number of GPU cache clear operations performed by the worker.",
        labelnames=("backend",),
    )
else:  # pragma: no cover - executed only when dependency is absent
    _QUEUE_DEPTH = None
    _INFLIGHT_TASKS = None
    _PAUSED_TASKS_TOTAL = None
    _PAGE_PROCESSING_SECONDS = None
    _GPU_CACHE_CLEARS_TOTAL = None


def start_worker_metrics_server() -> bool:
    global _server_started
    if not WORKER_METRICS_ENABLED or start_http_server is None:
        return False
    with _server_lock:
        if _server_started:
            return False
        start_http_server(WORKER_METRICS_PORT, addr=WORKER_METRICS_HOST)
        _server_started = True
        logger.info(
            "Prometheus metrics exporter started for OCR worker: http://%s:%s/metrics",
            WORKER_METRICS_HOST,
            WORKER_METRICS_PORT,
        )
        return True


def set_queue_depth(queue_name: str, depth: int) -> None:
    if _QUEUE_DEPTH is None:
        return
    _QUEUE_DEPTH.labels(queue=queue_name).set(max(0, int(depth)))


def task_started(mode: str) -> None:
    if _INFLIGHT_TASKS is None:
        return
    _INFLIGHT_TASKS.labels(mode=_safe_label(mode)).inc()


def task_finished(mode: str) -> None:
    if _INFLIGHT_TASKS is None:
        return
    _INFLIGHT_TASKS.labels(mode=_safe_label(mode)).dec()


def increment_paused_tasks(mode: str) -> None:
    if _PAUSED_TASKS_TOTAL is None:
        return
    _PAUSED_TASKS_TOTAL.labels(mode=_safe_label(mode)).inc()


def observe_page_processing_seconds(mode: str, duration_seconds: float) -> None:
    if _PAGE_PROCESSING_SECONDS is None:
        return
    _PAGE_PROCESSING_SECONDS.labels(mode=_safe_label(mode)).observe(max(0.0, float(duration_seconds)))


def increment_gpu_cache_clears(backend: str) -> None:
    if _GPU_CACHE_CLEARS_TOTAL is None:
        return
    _GPU_CACHE_CLEARS_TOTAL.labels(backend=_safe_label(backend)).inc()


def _safe_label(value: str) -> str:
    text = str(value or "").strip().lower()
    return text or "unknown"
