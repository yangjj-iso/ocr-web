from __future__ import annotations

import logging
import socket
from typing import Any

import httpx

from config import (
    COMPUTE_WORKER_ID,
    CONTROL_PLANE_BASE_URL,
    CONTROL_PLANE_CALLBACK_TIMEOUT_SECONDS,
    CONTROL_PLANE_INTERNAL_TOKEN,
    CONTROL_PLANE_VERIFY_TLS,
    MQ_COMMAND_QUEUE,
)

from .contracts import (
    OcrTaskCommand,
    ProgressPayload,
    TaskCompletionPayload,
    TaskEventPayload,
    TaskFailurePayload,
    TaskPausePayload,
    WorkerIdentity,
)


logger = logging.getLogger(__name__)


class ControlPlaneCallbackClient:
    def __init__(self, *, base_url: str, token: str, verify: bool, timeout_seconds: float) -> None:
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.verify = verify
        self.timeout_seconds = timeout_seconds

    @classmethod
    def from_command(cls, command: OcrTaskCommand) -> "ControlPlaneCallbackClient":
        return cls(
            base_url=command.callback.base_url or CONTROL_PLANE_BASE_URL,
            token=CONTROL_PLANE_INTERNAL_TOKEN,
            verify=CONTROL_PLANE_VERIFY_TLS,
            timeout_seconds=CONTROL_PLANE_CALLBACK_TIMEOUT_SECONDS,
        )

    @staticmethod
    def build_worker_identity(*, retry_count: int = 0) -> WorkerIdentity:
        return WorkerIdentity(
            worker_id=COMPUTE_WORKER_ID,
            hostname=socket.gethostname(),
            queue=MQ_COMMAND_QUEUE,
            retry_count=max(0, int(retry_count)),
        )

    async def _post(self, path: str, payload: dict[str, Any], *, idempotency_key: str, trace_id: str) -> dict[str, Any]:
        headers = {
            "X-Trace-Id": trace_id,
            "Idempotency-Key": idempotency_key,
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"

        async with httpx.AsyncClient(
            base_url=self.base_url,
            verify=self.verify,
            timeout=self.timeout_seconds,
        ) as client:
            response = await client.post(path, json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()
            if not bool(data.get("accepted", True)):
                raise RuntimeError(f"Control plane rejected callback: path={path}, body={data}")
            return data

    async def send_event(self, payload: TaskEventPayload) -> dict[str, Any]:
        logger.info(
            "Callback event -> control plane: task_id=%s, event_type=%s",
            payload.task_id,
            payload.event_type,
        )
        return await self._post(
            f"/internal/api/v1/ocr/tasks/{payload.task_id}/events",
            payload.model_dump(mode="json"),
            idempotency_key=payload.event_id,
            trace_id=payload.trace_id,
        )

    async def send_completion(self, payload: TaskCompletionPayload) -> dict[str, Any]:
        logger.info("Callback completion -> control plane: task_id=%s", payload.task_id)
        data = await self._post(
            f"/internal/api/v1/ocr/tasks/{payload.task_id}/completion",
            payload.model_dump(mode="json"),
            idempotency_key=payload.event_id,
            trace_id=payload.trace_id,
        )
        if not bool(data.get("persisted", False)):
            raise RuntimeError(f"Control plane did not persist task completion: {data}")
        return data

    async def send_pause(self, payload: TaskPausePayload) -> dict[str, Any]:
        logger.info("Callback pause -> control plane: task_id=%s", payload.task_id)
        data = await self._post(
            f"/internal/api/v1/ocr/tasks/{payload.task_id}/pause",
            payload.model_dump(mode="json"),
            idempotency_key=payload.event_id,
            trace_id=payload.trace_id,
        )
        if not bool(data.get("persisted", False)):
            raise RuntimeError(f"Control plane did not persist task pause: {data}")
        return data

    async def send_failure(self, payload: TaskFailurePayload) -> dict[str, Any]:
        logger.warning("Callback failure -> control plane: task_id=%s", payload.task_id)
        data = await self._post(
            f"/internal/api/v1/ocr/tasks/{payload.task_id}/failure",
            payload.model_dump(mode="json"),
            idempotency_key=payload.event_id,
            trace_id=payload.trace_id,
        )
        if not bool(data.get("persisted", False)):
            raise RuntimeError(f"Control plane did not persist task failure: {data}")
        return data


def build_progress(current_page: int, total_pages: int) -> ProgressPayload:
    normalized_total = max(0, int(total_pages))
    normalized_current = max(0, min(int(current_page), normalized_total or int(current_page)))
    percent = 0.0
    if normalized_total > 0:
        percent = round((normalized_current / normalized_total) * 100.0, 2)
    return ProgressPayload(current_page=normalized_current, total_pages=normalized_total, percent=percent)
