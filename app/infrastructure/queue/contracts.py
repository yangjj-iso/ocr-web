from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class CommandFilePayload(BaseModel):
    storage_provider: str = "local"
    bucket: str = ""
    object_key: str = ""
    file_url: str = ""
    filename: str
    content_type: str = "application/octet-stream"
    sha256: str = ""
    size_bytes: int = 0
    page_hint: int | None = None


class CommandExecutionPayload(BaseModel):
    mode: str = "layout"
    ocr_backend: str = "paddleocr"
    llm_backend: str = "local"
    llm_model: str = ""
    vision_enabled: bool = False
    processing_strategy: str = "auto"
    max_retries: int = 2
    confidence_threshold: float = 0.85
    human_review_threshold_low: float = 0.60
    human_review_threshold_high: float = 0.85
    timeout_seconds: int = 1800
    gpu_profile: str = "single_gpu"
    langgraph_graph: str = "archive_main"


class CommandBusinessPayload(BaseModel):
    submitted_by: str = ""
    source_system: str = "ocr-web"
    archive_context: dict[str, Any] = Field(default_factory=dict)


class CommandCallbackPayload(BaseModel):
    contract: str = "java-internal-v1"
    base_url: str = ""
    result_mode: Literal["inline", "inline_or_url", "url"] = "inline_or_url"


class OcrTaskCommand(BaseModel):
    schema_version: str = "v1"
    command: Literal["OCR_TASK_SUBMIT", "OCR_TASK_RESUME"] = "OCR_TASK_SUBMIT"
    command_id: str = Field(default_factory=lambda: str(uuid4()))
    trace_id: str = Field(default_factory=lambda: str(uuid4()))
    task_id: int
    batch_id: str = ""
    tenant_id: str = "default"
    submitted_at: str = Field(default_factory=utc_now_iso)
    priority: int = 5
    file: CommandFilePayload | None = None
    execution: CommandExecutionPayload = Field(default_factory=CommandExecutionPayload)
    business: CommandBusinessPayload = Field(default_factory=CommandBusinessPayload)
    callback: CommandCallbackPayload = Field(default_factory=CommandCallbackPayload)
    workflow_thread_id: str = ""
    resume_payload: dict[str, Any] = Field(default_factory=dict)
    resume_reason: str = ""


class WorkerIdentity(BaseModel):
    worker_id: str
    hostname: str
    queue: str = ""
    retry_count: int = 0


class ProgressPayload(BaseModel):
    current_page: int = 0
    total_pages: int = 0
    percent: float = 0.0


class TaskEventPayload(BaseModel):
    schema_version: str = "v1"
    event_id: str = Field(default_factory=lambda: str(uuid4()))
    trace_id: str
    task_id: int
    batch_id: str = ""
    event_type: str
    occurred_at: str = Field(default_factory=utc_now_iso)
    worker: WorkerIdentity
    progress: ProgressPayload = Field(default_factory=ProgressPayload)
    payload: dict[str, Any] = Field(default_factory=dict)


class ResultArtifactPayload(BaseModel):
    storage_provider: str = "local"
    bucket: str = ""
    object_key: str = ""
    file_url: str = ""
    sha256: str = ""
    size_bytes: int = 0


class CompletionSummaryPayload(BaseModel):
    status: Literal["COMPLETED"] = "COMPLETED"
    total_pages: int = 0
    duration_ms: int = 0
    overall_confidence: float = 0.0
    human_review_required: bool = False
    result_mode: Literal["inline", "url"] = "inline"


class PauseSummaryPayload(BaseModel):
    status: Literal["PAUSED"] = "PAUSED"
    total_pages: int = 0
    processed_pages: int = 0
    duration_ms: int = 0
    human_review_required: bool = True


class ArchiveFieldsPayload(BaseModel):
    archive_no: str = ""
    doc_no: str = ""
    responsible: str = ""
    title: str = ""
    date: str = ""
    pages: str = ""
    classification: str = ""
    storage_path: str = ""
    remarks: str = ""


class TaskCompletionPayload(BaseModel):
    schema_version: str = "v1"
    event_id: str = Field(default_factory=lambda: str(uuid4()))
    trace_id: str
    task_id: int
    batch_id: str = ""
    completed_at: str = Field(default_factory=utc_now_iso)
    worker: WorkerIdentity
    summary: CompletionSummaryPayload
    archive_fields: ArchiveFieldsPayload = Field(default_factory=ArchiveFieldsPayload)
    quality_metrics: dict[str, Any] = Field(default_factory=dict)
    agent_meta: dict[str, Any] = Field(default_factory=dict)
    full_text: str = ""
    result: dict[str, Any] | None = None
    result_artifact: ResultArtifactPayload | None = None


class TaskPausePayload(BaseModel):
    schema_version: str = "v1"
    event_id: str = Field(default_factory=lambda: str(uuid4()))
    trace_id: str
    task_id: int
    batch_id: str = ""
    paused_at: str = Field(default_factory=utc_now_iso)
    worker: WorkerIdentity
    progress: ProgressPayload = Field(default_factory=ProgressPayload)
    summary: PauseSummaryPayload = Field(default_factory=PauseSummaryPayload)
    workflow_thread_id: str
    review_status: str = "pending_human_review"
    review_reason: str = ""
    interrupt_payload: dict[str, Any] = Field(default_factory=dict)
    quality_metrics: dict[str, Any] = Field(default_factory=dict)
    agent_meta: dict[str, Any] = Field(default_factory=dict)
    full_text: str = ""
    result: dict[str, Any] | None = None
    result_artifact: ResultArtifactPayload | None = None


class FailureErrorPayload(BaseModel):
    code: str = "UNEXPECTED_ERROR"
    message: str = ""
    stage: str = ""
    retryable: bool = True


class TaskFailurePayload(BaseModel):
    schema_version: str = "v1"
    event_id: str = Field(default_factory=lambda: str(uuid4()))
    trace_id: str
    task_id: int
    batch_id: str = ""
    failed_at: str = Field(default_factory=utc_now_iso)
    worker: WorkerIdentity
    progress: ProgressPayload = Field(default_factory=ProgressPayload)
    error: FailureErrorPayload
    partial_result_artifact: ResultArtifactPayload | None = None
