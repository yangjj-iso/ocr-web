from __future__ import annotations

import asyncio
import hashlib
import logging
import mimetypes
import socket
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from config import (
    COMPUTE_WORKER_ID,
    CONFIDENCE_THRESHOLD,
    CONTROL_PLANE_BASE_URL,
    HUMAN_REVIEW_MAX_CONFIDENCE,
    HUMAN_REVIEW_MIN_CONFIDENCE,
    MAX_RETRIES,
    MINIMAX_ENABLED,
    MINIMAX_MODEL,
    MQ_BROKER_URL,
    MQ_COMMAND_DLQ,
    MQ_COMMAND_DLX,
    MQ_COMMAND_EXCHANGE,
    MQ_COMMAND_QUEUE,
    MQ_COMMAND_ROUTING_KEY,
    MQ_PUBLISH_RETRY_MAX,
    OCR_LAYOUT_BACKEND,
    OCR_VL_BACKEND,
)

from .contracts import (
    CommandBusinessPayload,
    CommandCallbackPayload,
    CommandExecutionPayload,
    CommandFilePayload,
    OcrTaskCommand,
)


logger = logging.getLogger(__name__)


@dataclass(slots=True)
class OCRJob:
    task_id: int
    mode: str
    filename: str
    file_path: str
    file_type: str
    excel_path: str = ""
    excel_init: int = 0
    output_dir: str = ""
    batch_id: str = ""
    priority: int = 5
    submitted_by: str = ""
    source_system: str = "python-fastapi-legacy"


def _hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _guess_ocr_backend(mode: str) -> str:
    normalized_mode = (mode or "").strip().lower()
    if normalized_mode in {"layout", "ocr"}:
        return "aistudio_paddleocr_api" if OCR_LAYOUT_BACKEND == "api" else "paddleocr"
    if normalized_mode in {"vl", "baidu_vl"}:
        return "vision_local" if OCR_VL_BACKEND == "local" else f"vision_{OCR_VL_BACKEND}"
    return "aistudio_paddleocr_api" if OCR_LAYOUT_BACKEND == "api" else "paddleocr"


def _build_command(job: OCRJob) -> OcrTaskCommand:
    file_path = Path(job.file_path).resolve(strict=False)
    file_payload = CommandFilePayload(
        storage_provider="local",
        file_url=file_path.as_uri(),
        filename=job.filename,
        content_type=mimetypes.guess_type(job.filename)[0] or "application/octet-stream",
        sha256=_hash_file(file_path),
        size_bytes=file_path.stat().st_size if file_path.exists() else 0,
    )
    execution_payload = CommandExecutionPayload(
        mode=job.mode,
        ocr_backend=_guess_ocr_backend(job.mode),
        llm_backend="minimax" if MINIMAX_ENABLED else "local",
        llm_model=MINIMAX_MODEL if MINIMAX_ENABLED else "",
        vision_enabled=job.mode in {"vl", "baidu_vl"},
        max_retries=MAX_RETRIES,
        confidence_threshold=CONFIDENCE_THRESHOLD,
        human_review_threshold_low=HUMAN_REVIEW_MIN_CONFIDENCE,
        human_review_threshold_high=HUMAN_REVIEW_MAX_CONFIDENCE,
        langgraph_graph="archive_main",
    )
    return OcrTaskCommand(
        task_id=int(job.task_id),
        batch_id=job.batch_id,
        priority=max(0, min(int(job.priority), 9)),
        file=file_payload,
        execution=execution_payload,
        business=CommandBusinessPayload(
            submitted_by=job.submitted_by,
            source_system=job.source_system,
            archive_context={
                "excel_path": job.excel_path,
                "excel_init": job.excel_init,
                "output_dir": job.output_dir,
                "folder_path": str(file_path.parent),
            },
        ),
        callback=CommandCallbackPayload(
            base_url=CONTROL_PLANE_BASE_URL,
            result_mode="inline_or_url",
        ),
    )


def _publish(payload: dict[str, Any]) -> None:
    try:
        from kombu import Connection, Exchange, Producer, Queue
    except ImportError as exc:  # pragma: no cover - depends on runtime extras
        raise RuntimeError("Queue publishing requires kombu/celery to be installed.") from exc

    exchange = Exchange(MQ_COMMAND_EXCHANGE, type="direct", durable=True)
    dead_letter_exchange = Exchange(MQ_COMMAND_DLX, type="direct", durable=True)
    queue = Queue(
        MQ_COMMAND_QUEUE,
        exchange=exchange,
        routing_key=MQ_COMMAND_ROUTING_KEY,
        durable=True,
        queue_arguments={"x-dead-letter-exchange": MQ_COMMAND_DLX},
    )
    dead_letter_queue = Queue(
        MQ_COMMAND_DLQ,
        exchange=dead_letter_exchange,
        routing_key=MQ_COMMAND_DLQ,
        durable=True,
    )
    with Connection(MQ_BROKER_URL) as connection:
        with connection.channel() as channel:
            producer = Producer(channel)
            queue(channel).declare()
            dead_letter_queue(channel).declare()
            producer.publish(
                payload,
                exchange=exchange,
                routing_key=MQ_COMMAND_ROUTING_KEY,
                serializer="json",
                delivery_mode=2,
                declare=[queue, dead_letter_exchange, dead_letter_queue],
                retry=True,
                retry_policy={
                    "max_retries": MQ_PUBLISH_RETRY_MAX,
                    "interval_start": 0,
                    "interval_step": 1,
                    "interval_max": 3,
                },
                headers={
                    "x-schema-version": payload.get("schema_version", "v1"),
                    "x-task-id": str(payload.get("task_id", "")),
                    "x-batch-id": str(payload.get("batch_id", "")),
                    "x-producer-host": socket.gethostname(),
                    "x-producer-worker": COMPUTE_WORKER_ID,
                },
                correlation_id=payload.get("trace_id", ""),
                message_id=payload.get("command_id", ""),
                content_type="application/json",
                content_encoding="utf-8",
            )


async def enqueue_task(job: OCRJob) -> OcrTaskCommand:
    command = _build_command(job)
    await asyncio.to_thread(_publish, command.model_dump(mode="json"))
    logger.info(
        "Published OCR command to MQ: task_id=%s, batch_id=%s, mode=%s, queue=%s",
        command.task_id,
        command.batch_id,
        command.execution.mode,
        MQ_COMMAND_QUEUE,
    )
    return command


async def start_task_worker() -> None:
    logger.warning(
        "Local asyncio OCR worker has been retired. Start app/main_worker.py or a Celery worker instead."
    )


async def stop_task_worker() -> None:
    logger.info("No in-process OCR worker is attached to the web service anymore.")
