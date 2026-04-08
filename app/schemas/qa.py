from typing import Any

from pydantic import BaseModel, Field


class BatchQARequest(BaseModel):
    question: str
    top_k: int = Field(default=8, ge=1, le=10)
    persist: bool = True


class BatchQAEvidenceItem(BaseModel):
    task_id: int
    filename: str
    snippet: str
    score: float


class BatchQACitationItem(BaseModel):
    evidence_index: int
    task_id: int
    filename: str


class BatchQAResponse(BaseModel):
    batch_id: str
    question: str
    answer: str
    evidence: list[BatchQAEvidenceItem]
    qa_id: int | None = None
    support_level: str = "insufficient"
    confidence: float = 0.0
    citations: list[BatchQACitationItem] = Field(default_factory=list)
    provider: str
    model: str
    raw_usage: dict[str, Any]
    generated_at: str | None = None


class BatchQAFeedbackItem(BaseModel):
    rating: str
    reason: str | None = None
    comment: str | None = None
    corrected_answer: str | None = None
    corrected_evidence: list[BatchQAEvidenceItem] = Field(default_factory=list)
    created_at: str | None = None
    updated_at: str | None = None


class BatchQAHistoryItem(BaseModel):
    qa_id: int
    batch_id: str
    question: str
    answer: str
    evidence: list[BatchQAEvidenceItem]
    support_level: str
    confidence: float
    citations: list[BatchQACitationItem] = Field(default_factory=list)
    provider: str
    model: str
    raw_usage: dict[str, Any]
    generated_at: str | None = None
    feedback: BatchQAFeedbackItem | None = None


class BatchQAHistoryResponse(BaseModel):
    batch_id: str
    total: int
    page: int
    page_size: int
    items: list[BatchQAHistoryItem]


class BatchQAFeedbackRequest(BaseModel):
    rating: str
    reason: str | None = None
    comment: str | None = None
    corrected_answer: str | None = None
    corrected_evidence: list[BatchQAEvidenceItem] = Field(default_factory=list)


class BatchQAFeedbackResponse(BaseModel):
    batch_id: str
    qa_id: int
    feedback: BatchQAFeedbackItem


class BatchQAMetricsResponse(BaseModel):
    batch_id: str
    helpful_rate: float
    insufficient_rate: float
    feedback_count: int
    recent_trend: list[dict[str, Any]]
    generated_at: str | None = None
