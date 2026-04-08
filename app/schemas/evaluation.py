from typing import Any

from pydantic import BaseModel, Field


class BatchEvaluationTruthTaskItem(BaseModel):
    task_id: int
    doc_key: str


class BatchEvaluationTruthDocumentItem(BaseModel):
    doc_key: str
    fields: dict[str, str]


class BatchEvaluationTruthGetResponse(BaseModel):
    batch_id: str
    tasks: list[BatchEvaluationTruthTaskItem]
    documents: list[BatchEvaluationTruthDocumentItem]
    truth_updated_at: str | None = None


class BatchEvaluationTruthPutRequest(BaseModel):
    tasks: list[BatchEvaluationTruthTaskItem] = Field(default_factory=list)
    documents: list[BatchEvaluationTruthDocumentItem] = Field(default_factory=list)


class BatchEvaluationMetricsResponse(BaseModel):
    batch_id: str
    operational_metrics: dict[str, Any]
    truth_metrics: dict[str, Any] | None = None
    compare_targets: list[str]
    generated_at: str | None = None
    truth_updated_at: str | None = None


class BatchEvaluationAiReportResponse(BaseModel):
    batch_id: str
    summary: str
    strengths: list[str]
    risks: list[str]
    recommendations: list[str]
    provider: str
    model: str
    generated_at: str | None = None
    raw_usage: dict[str, Any]
