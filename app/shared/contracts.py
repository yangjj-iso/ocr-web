"""Cross-layer contract models used during architecture migration."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class TaskProgressSnapshot(BaseModel):
    total: int = 0
    done_count: int = 0
    failed_count: int = 0
    processing_count: int = 0
    pending_count: int = 0


class FieldExtractionResult(BaseModel):
    fields: dict[str, str] = Field(default_factory=dict)
    confidence: dict[str, float] = Field(default_factory=dict)
    review_recommendation: dict[str, str] = Field(default_factory=dict)


class DocumentMergeGroup(BaseModel):
    group_id: str
    task_ids: list[int] = Field(default_factory=list)
    filenames: list[str] = Field(default_factory=list)
    same_document_confidence: float | None = None
    decision_reasons: list[str] = Field(default_factory=list)


class CompletenessCheckResult(BaseModel):
    status: Literal["ok", "review_required", "missing_pages", "incomplete"]
    missing_page_ranges: list[str] = Field(default_factory=list)
    reasons: list[str] = Field(default_factory=list)


class QaAnswerWithEvidence(BaseModel):
    answer: str
    support_level: Literal["supported", "partial", "insufficient"] | None = None
    confidence: float | None = None
    evidence: list[dict[str, Any]] = Field(default_factory=list)

