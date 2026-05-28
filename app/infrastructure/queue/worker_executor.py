from __future__ import annotations

import asyncio
import gc
import hashlib
import json
import logging
import mimetypes
import os
import sys
import time
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any

if __package__ in {None, ""}:
    PROJECT_ROOT = Path(__file__).resolve().parents[3]
    if str(PROJECT_ROOT) not in sys.path:
        sys.path.insert(0, str(PROJECT_ROOT))

import httpx

from app.infrastructure.metrics import (
    increment_gpu_cache_clears,
    increment_paused_tasks,
    observe_page_processing_seconds,
    task_finished,
    task_started,
)
from app.core.result_validation import normalize_result_pages, serialize_pages_text
from app.services.excel_export import extract_fields as _extract_fields
from app.services.agent_ocr_workflow import run_hierarchical_ocr_detached
from app.services.ocr_service import _run_ocr_document
from config import CALLBACK_INLINE_RESULT_MAX_BYTES, WORKER_TEMP_DIR

try:
    from .callback_client import ControlPlaneCallbackClient, build_progress
    from .contracts import (
        ArchiveFieldsPayload,
        CompletionSummaryPayload,
        FailureErrorPayload,
        OcrTaskCommand,
        ProgressPayload,
        ResultArtifactPayload,
        TaskCompletionPayload,
        TaskEventPayload,
        TaskFailurePayload,
        TaskPausePayload,
    )
except ImportError:  # pragma: no cover - script-mode fallback
    from app.infrastructure.queue.callback_client import ControlPlaneCallbackClient, build_progress
    from app.infrastructure.queue.contracts import (
        ArchiveFieldsPayload,
        CompletionSummaryPayload,
        FailureErrorPayload,
        OcrTaskCommand,
        ProgressPayload,
        ResultArtifactPayload,
        TaskCompletionPayload,
        TaskEventPayload,
        TaskFailurePayload,
        TaskPausePayload,
    )


logger = logging.getLogger(__name__)


def _normalize_mode(command: OcrTaskCommand) -> str:
    if command.execution.mode == "hierarchical_agent":
        return "layout"
    return command.execution.mode or "layout"


def _map_archive_fields(fields: dict[str, Any]) -> ArchiveFieldsPayload:
    payload = {str(key): str(value or "") for key, value in (fields or {}).items()}
    return ArchiveFieldsPayload(
        archive_no=payload.get("档号", ""),
        doc_no=payload.get("文号", ""),
        responsible=payload.get("责任者", ""),
        title=payload.get("题名", ""),
        date=payload.get("日期", ""),
        pages=payload.get("页数", ""),
        classification=payload.get("密级", ""),
        remarks=payload.get("备注", ""),
    )


def _compute_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


async def _stage_input_file(command: OcrTaskCommand) -> tuple[str, bool]:
    if command.file is None:
        raise ValueError("OCR_TASK_SUBMIT requires file payload.")

    # S3/MinIO download path
    if command.file.storage_provider == "s3" and command.file.bucket and command.file.object_key:
        from app.infrastructure.storage.s3_client import download_object

        suffix = Path(command.file.filename).suffix or mimetypes.guess_extension(command.file.content_type or "") or ".bin"
        temp_file = NamedTemporaryFile(delete=False, suffix=suffix, dir=WORKER_TEMP_DIR)
        temp_path = Path(temp_file.name)
        temp_file.close()
        await asyncio.to_thread(download_object, command.file.bucket, command.file.object_key, str(temp_path))
        expected_sha256 = (command.file.sha256 or "").strip().lower()
        if expected_sha256:
            actual_sha256 = _compute_sha256(temp_path)
            if actual_sha256.lower() != expected_sha256:
                temp_path.unlink(missing_ok=True)
                raise ValueError(
                    f"S3 file sha256 mismatch: expected={expected_sha256}, actual={actual_sha256}"
                )
        return str(temp_path), True

    file_url = (command.file.file_url or "").strip()
    if file_url.lower().startswith(("http://", "https://")):
        suffix = Path(command.file.filename).suffix or mimetypes.guess_extension(command.file.content_type or "") or ".bin"
        temp_file = NamedTemporaryFile(delete=False, suffix=suffix, dir=WORKER_TEMP_DIR)
        temp_path = Path(temp_file.name)
        temp_file.close()
        headers: dict[str, str] = {}
        client_token = os.getenv("CONTROL_PLANE_INTERNAL_TOKEN", "").strip()
        if client_token:
            headers["Authorization"] = f"Bearer {client_token}"
        async with httpx.AsyncClient(timeout=command.execution.timeout_seconds) as client:
            response = await client.get(file_url, headers=headers)
            response.raise_for_status()
            temp_path.write_bytes(response.content)
        expected_sha256 = (command.file.sha256 or "").strip().lower()
        if expected_sha256:
            actual_sha256 = _compute_sha256(temp_path)
            if actual_sha256.lower() != expected_sha256:
                temp_path.unlink(missing_ok=True)
                raise ValueError(
                    f"Staged input file sha256 mismatch: expected={expected_sha256}, actual={actual_sha256}"
                )
        return str(temp_path), True
    if command.file.storage_provider == "local" and file_url.startswith("file:///"):
        return str(Path(file_url.removeprefix("file:///")).resolve(strict=False)), False
    if command.file.storage_provider == "local" and file_url:
        return str(Path(file_url).resolve(strict=False)), False

    suffix = Path(command.file.filename).suffix or mimetypes.guess_extension(command.file.content_type or "") or ".bin"
    temp_file = NamedTemporaryFile(delete=False, suffix=suffix, dir=WORKER_TEMP_DIR)
    temp_path = Path(temp_file.name)
    temp_file.close()
    headers: dict[str, str] = {}
    client_token = os.getenv("CONTROL_PLANE_INTERNAL_TOKEN", "").strip()
    if file_url.lower().startswith(("http://", "https://")) and client_token:
        headers["Authorization"] = f"Bearer {client_token}"
    async with httpx.AsyncClient(timeout=command.execution.timeout_seconds) as client:
        response = await client.get(file_url, headers=headers)
        response.raise_for_status()
        temp_path.write_bytes(response.content)
    expected_sha256 = (command.file.sha256 or "").strip().lower()
    if expected_sha256:
        actual_sha256 = _compute_sha256(temp_path)
        if actual_sha256.lower() != expected_sha256:
            temp_path.unlink(missing_ok=True)
            raise ValueError(
                f"Staged input file sha256 mismatch: expected={expected_sha256}, actual={actual_sha256}"
            )
    return str(temp_path), True


def _persist_large_result(task_id: int, payload: dict[str, Any]) -> ResultArtifactPayload:
    target = WORKER_TEMP_DIR / f"task_{task_id}_result.json"
    content = json.dumps(payload, ensure_ascii=False, indent=2)
    target.write_text(content, encoding="utf-8")

    # Attempt to upload to MinIO; fall back to local storage on failure
    try:
        from app.infrastructure.storage.s3_client import get_default_bucket, upload_object

        bucket = get_default_bucket()
        object_key = f"results/task_{task_id}_result.json"
        upload_object(bucket, object_key, str(target), content_type="application/json")
        return ResultArtifactPayload(
            storage_provider="s3",
            bucket=bucket,
            object_key=object_key,
            sha256=_compute_sha256(target),
            size_bytes=target.stat().st_size,
        )
    except Exception:
        logger.debug("MinIO upload failed for task %s result; using local storage.", task_id, exc_info=True)
        return ResultArtifactPayload(
            storage_provider="local",
            file_url=target.as_uri(),
            sha256=_compute_sha256(target),
            size_bytes=target.stat().st_size,
        )


def _cleanup_runtime_memory() -> None:
    gc.collect()
    try:
        import torch

        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            increment_gpu_cache_clears("torch")
    except Exception:
        pass
    try:
        import paddle

        paddle.device.cuda.empty_cache()
        increment_gpu_cache_clears("paddle")
    except Exception:
        pass


async def _send_event(
    client: ControlPlaneCallbackClient,
    command: OcrTaskCommand,
    *,
    event_type: str,
    payload: dict[str, Any] | None = None,
    progress: ProgressPayload | None = None,
    retry_count: int = 0,
) -> None:
    event = TaskEventPayload(
        trace_id=command.trace_id,
        task_id=command.task_id,
        batch_id=command.batch_id,
        event_type=event_type,
        worker=client.build_worker_identity(retry_count=retry_count),
        progress=progress or ProgressPayload(),
        payload=payload or {},
    )
    await client.send_event(event)


async def _execute_non_hierarchical(command: OcrTaskCommand, file_path: str) -> dict[str, Any]:
    mode = _normalize_mode(command)
    result = await asyncio.to_thread(_run_ocr_document, file_path, mode)
    pages = normalize_result_pages(result.get("pages") or [])
    full_text = serialize_pages_text(pages)
    fields_raw = _extract_fields(
        command.file.filename,
        full_text,
        pages,
        int(result.get("page_count") or len(pages)),
    )
    return {
        "pages": pages,
        "full_text": full_text,
        "page_count": int(result.get("page_count") or len(pages)),
        "final_fields": {str(key): str(value or "") for key, value in (fields_raw or {}).items()},
        "overall_confidence": 0.75 if full_text else 0.0,
        "issues": [],
        "human_review": False,
        "review_status": "approved",
        "review_reason": "",
        "quality_metrics": {},
        "rag_examples": [],
        "consistency": {},
        "page_outputs": [],
    }


async def process_task_command(command: OcrTaskCommand, *, retry_count: int = 0) -> dict[str, Any]:
    started_at = time.perf_counter()
    client = ControlPlaneCallbackClient.from_command(command)
    staged_file_path = ""
    should_cleanup_staged_file = False
    page_hint = 0 if command.file is None else int(command.file.page_hint or 0)
    progress = build_progress(0, page_hint)
    command_mode = command.execution.mode or "layout"
    page_started_at = started_at
    task_started(command_mode)

    async def graph_event_callback(event_type: str, payload: dict[str, Any], event_progress: dict[str, Any]) -> None:
        nonlocal progress, page_started_at
        progress = ProgressPayload(
            current_page=int(event_progress.get("current_page") or 0),
            total_pages=int(event_progress.get("total_pages") or 0),
            percent=float(event_progress.get("percent") or 0.0),
        )
        if event_type == "PAGE_COMPLETED":
            now = time.perf_counter()
            observe_page_processing_seconds(command_mode, now - page_started_at)
            page_started_at = now
        await _send_event(
            client,
            command,
            event_type=event_type,
            payload=payload,
            progress=progress,
            retry_count=retry_count,
        )

    await _send_event(
        client,
        command,
        event_type="WORKER_ACCEPTED",
        payload={
            "command_id": command.command_id,
            "mode": command.execution.mode,
            "command": command.command,
            "workflow_thread_id": command.workflow_thread_id,
        },
        progress=progress,
        retry_count=retry_count,
    )

    try:
        if command.command == "OCR_TASK_SUBMIT":
            staged_file_path, should_cleanup_staged_file = await _stage_input_file(command)
        await _send_event(
            client,
            command,
            event_type="TASK_STARTED",
            payload={
                "file_path": staged_file_path,
                "mode": command.execution.mode,
                "command": command.command,
                "workflow_thread_id": command.workflow_thread_id,
            },
            progress=progress,
            retry_count=retry_count,
        )

        if command.execution.enable_hierarchical_agent or command.execution.mode == "hierarchical_agent":
            workflow_result = await run_hierarchical_ocr_detached(
                task_id=command.task_id,
                batch_id=command.batch_id,
                filename=command.file.filename if command.file is not None else "",
                file_path=staged_file_path,
                mode=_normalize_mode(command),
                event_callback=graph_event_callback,
                workflow_thread_id=command.workflow_thread_id,
                resume_payload=command.resume_payload or None,
            )
        else:
            workflow_result = await _execute_non_hierarchical(command, staged_file_path)
            progress = build_progress(
                int(workflow_result.get("page_count") or 0),
                int(workflow_result.get("page_count") or 0),
            )
            observe_page_processing_seconds(command_mode, time.perf_counter() - page_started_at)
            await _send_event(
                client,
                command,
                event_type="PROGRESS_UPDATED",
                payload={"note": "Non-hierarchical OCR completed"},
                progress=progress,
                retry_count=retry_count,
            )

        if str(workflow_result.get("status") or "").upper() == "INTERRUPTED":
            pages = normalize_result_pages(workflow_result.get("pages") or [])
            partial_result = {"pages": pages}
            partial_result_artifact = None
            summary_result_mode = "inline"
            serialized_partial = json.dumps(partial_result, ensure_ascii=False).encode("utf-8")
            if len(serialized_partial) > CALLBACK_INLINE_RESULT_MAX_BYTES:
                partial_result_artifact = _persist_large_result(command.task_id, partial_result)
                partial_result = None
                summary_result_mode = "url"
            pause_payload = TaskPausePayload(
                trace_id=command.trace_id,
                task_id=command.task_id,
                batch_id=command.batch_id,
                worker=client.build_worker_identity(retry_count=retry_count),
                progress=build_progress(
                    int(progress.current_page or workflow_result.get("page_count") or 0),
                    int(progress.total_pages or workflow_result.get("page_count") or 0),
                ),
                summary={
                    "status": "PAUSED",
                    "total_pages": int(workflow_result.get("page_count") or 0),
                    "processed_pages": int(progress.current_page or workflow_result.get("page_count") or 0),
                    "duration_ms": int((time.perf_counter() - started_at) * 1000),
                    "human_review_required": True,
                },
                workflow_thread_id=str(
                    workflow_result.get("workflow_thread_id")
                    or command.workflow_thread_id
                    or f"ocr-task-{command.task_id}"
                ),
                review_status=str(workflow_result.get("review_status") or "pending_human_review"),
                review_reason=str(workflow_result.get("review_reason") or ""),
                interrupt_payload=dict(workflow_result.get("interrupt_payload") or {}),
                quality_metrics=dict(workflow_result.get("quality_metrics") or {}),
                agent_meta={
                    "workflow": command.execution.langgraph_graph,
                    "ocr_backend": command.execution.ocr_backend,
                    "llm_backend": command.execution.llm_backend,
                    "llm_model": command.execution.llm_model,
                    "review_status": workflow_result.get("review_status") or "pending_human_review",
                    "review_reason": workflow_result.get("review_reason") or "",
                    "issues": list(workflow_result.get("issues") or []),
                    "workflow_thread_id": workflow_result.get("workflow_thread_id") or command.workflow_thread_id,
                    "result_mode": summary_result_mode,
                },
                full_text=str(workflow_result.get("full_text") or ""),
                result=partial_result,
                result_artifact=partial_result_artifact,
            )
            await client.send_pause(pause_payload)
            increment_paused_tasks(command_mode)
            logger.info("Compute task paused for human review and was persisted by control plane: task_id=%s", command.task_id)
            return workflow_result

        pages = normalize_result_pages(workflow_result.get("pages") or [])
        archive_fields = _map_archive_fields(workflow_result.get("final_fields") or {})
        quality_metrics = dict(workflow_result.get("quality_metrics") or {})
        agent_meta = {
            "workflow": command.execution.langgraph_graph
            if command.execution.enable_hierarchical_agent
            else "single_route_ocr",
            "ocr_backend": command.execution.ocr_backend,
            "llm_backend": command.execution.llm_backend,
            "llm_model": command.execution.llm_model,
            "review_status": workflow_result.get("review_status") or "approved",
            "review_reason": workflow_result.get("review_reason") or "",
            "issues": list(workflow_result.get("issues") or []),
        }
        result_payload = {"pages": pages}
        result_artifact = None
        summary_result_mode = "inline"
        serialized_result = json.dumps(result_payload, ensure_ascii=False).encode("utf-8")
        if len(serialized_result) > CALLBACK_INLINE_RESULT_MAX_BYTES:
            result_artifact = _persist_large_result(command.task_id, result_payload)
            result_payload = None
            summary_result_mode = "url"

        completion = TaskCompletionPayload(
            trace_id=command.trace_id,
            task_id=command.task_id,
            batch_id=command.batch_id,
            worker=client.build_worker_identity(retry_count=retry_count),
            summary=CompletionSummaryPayload(
                total_pages=int(workflow_result.get("page_count") or len(pages)),
                duration_ms=int((time.perf_counter() - started_at) * 1000),
                overall_confidence=float(workflow_result.get("overall_confidence") or 0.0),
                human_review_required=bool(workflow_result.get("human_review")),
                result_mode=summary_result_mode,
            ),
            archive_fields=archive_fields,
            quality_metrics=quality_metrics,
            agent_meta=agent_meta,
            full_text=str(workflow_result.get("full_text") or ""),
            result=result_payload,
            result_artifact=result_artifact,
        )
        await client.send_completion(completion)
        logger.info("Compute task completed and acknowledged by control plane: task_id=%s", command.task_id)
        return workflow_result
    except Exception as exc:  # noqa: BLE001
        error_payload = TaskFailurePayload(
            trace_id=command.trace_id,
            task_id=command.task_id,
            batch_id=command.batch_id,
            worker=client.build_worker_identity(retry_count=retry_count),
            progress=progress,
            error=FailureErrorPayload(
                code=type(exc).__name__.upper(),
                message=str(exc),
                stage="compute_worker",
                retryable=True,
            ),
        )
        try:
            await client.send_failure(error_payload)
            logger.exception("Compute task failed and failure status was persisted: task_id=%s", command.task_id)
            return {"status": "FAILED", "error": str(exc)}
        except Exception:
            logger.exception("Compute task failed and failure callback could not be persisted: task_id=%s", command.task_id)
            raise
    finally:
        if should_cleanup_staged_file and staged_file_path:
            try:
                Path(staged_file_path).unlink(missing_ok=True)
            except Exception:
                logger.warning("Failed to cleanup staged input file: %s", staged_file_path, exc_info=True)
        _cleanup_runtime_memory()
        task_finished(command_mode)


def process_task_command_sync(payload: dict[str, Any], *, retry_count: int = 0) -> dict[str, Any]:
    command = OcrTaskCommand.model_validate(payload)
    return asyncio.run(process_task_command(command, retry_count=retry_count))


def run_worker_entrypoint() -> None:
    from app.infrastructure.metrics import start_worker_metrics_server
    from app.infrastructure.queue.rabbitmq_consumer import run_command_consumer

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    logger.info("worker_executor.py started directly; delegating to RabbitMQ worker entrypoint.")
    start_worker_metrics_server()
    run_command_consumer()


if __name__ == "__main__":
    run_worker_entrypoint()
