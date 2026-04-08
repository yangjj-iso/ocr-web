from typing import Any

from pydantic import BaseModel, Field


class AIExtractFieldsRequest(BaseModel):
    persist: bool = False
    include_evidence: bool = True


class AIFieldConflict(BaseModel):
    rule: str
    llm: str
    evidence: str | None = None


class AIFieldAgreement(BaseModel):
    matched: int
    total: int
    ratio: float
    matched_fields: list[str]
    mismatch_fields: list[str]


class AIExtractFieldsResponse(BaseModel):
    task_id: int
    rule_fields: dict[str, Any]
    llm_fields: dict[str, Any]
    recommended_fields: dict[str, str]
    conflicts: dict[str, AIFieldConflict]
    agreement: AIFieldAgreement
    provider: str
    model: str
    raw_usage: dict[str, Any]


class AIBatchMergeExtractRequest(BaseModel):
    persist: bool = False
    include_evidence: bool = True
    force_refresh: bool = False


class AIBatchSkippedTask(BaseModel):
    task_id: int
    filename: str
    status: str
    reason: str


class AIBatchGroup(BaseModel):
    group_id: str
    task_ids: list[int]
    filenames: list[str]
    same_document_confidence: float
    decision_reasons: list[str]


class AIBatchDocument(BaseModel):
    group_id: str
    merged_page_count: int
    rule_fields: dict[str, Any]
    llm_fields: dict[str, Any]
    recommended_fields: dict[str, str]
    conflicts: dict[str, AIFieldConflict]
    agreement: AIFieldAgreement


class AIBatchSummary(BaseModel):
    total_tasks: int
    done_tasks: int
    eligible_tasks: int
    skipped_tasks: list[AIBatchSkippedTask]
    groups_count: int
    documents_count: int


class AIBatchMergeExtractResponse(BaseModel):
    batch_id: str
    groups: list[AIBatchGroup]
    documents: list[AIBatchDocument]
    provider: str
    model: str
    raw_usage: dict[str, Any]
    summary: AIBatchSummary
    generated_at: str | None = None


class AIBoundarySequence(BaseModel):
    prefix: str
    task_ids: list[int]
    filenames: list[str]


class AIBoundaryDecision(BaseModel):
    left_task_id: int
    right_task_id: int
    prefix: str
    left_page_no: int
    right_page_no: int
    same_document_score: float
    should_merge: bool
    is_ambiguous: bool
    strong_split: bool
    reason: str
    signals: dict[str, Any]


class AIBoundaryGroup(BaseModel):
    group_id: str
    prefix: str
    task_ids: list[int]
    filenames: list[str]
    start_page: int
    end_page: int
    confidence: float
    reasons: list[str]


class AIBoundarySummary(BaseModel):
    sequence_count: int
    decision_count: int
    group_count: int


class AIBoundaryAnalysisResponse(BaseModel):
    batch_id: str
    sequences: list[AIBoundarySequence]
    decisions: list[AIBoundaryDecision]
    groups: list[AIBoundaryGroup]
    task_to_group: dict[int, str]
    summary: AIBoundarySummary
    truth_updated_at: str | None = None


class AIBoundaryTruthTaskItem(BaseModel):
    task_id: int
    doc_key: str
    source: str = "human"
    note: str | None = None


class AIBoundaryTruthFeedbackItem(BaseModel):
    left_task_id: int
    right_task_id: int
    label: str
    source: str
    note: str | None = None


class AIBoundaryTruthResponse(BaseModel):
    batch_id: str
    tasks: list[AIBoundaryTruthTaskItem]
    feedback: list[AIBoundaryTruthFeedbackItem]
    truth_updated_at: str | None = None


class AIBoundaryTruthPutRequest(BaseModel):
    tasks: list[AIBoundaryTruthTaskItem] = Field(default_factory=list)
