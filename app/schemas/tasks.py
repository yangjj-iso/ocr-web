from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.core.result_validation import normalize_result_pages


def _summarize_agent_meta(pages: list[dict[str, Any]]) -> dict[str, Any] | None:
    page_meta = [page.get("agent_meta") for page in pages if isinstance(page.get("agent_meta"), dict)]
    if not page_meta:
        return None

    batch_summary = next(
        (meta.get("batch_summary") for meta in page_meta if isinstance(meta.get("batch_summary"), dict)),
        None,
    )
    page_confidences = [
        float(meta.get("confidence"))
        for meta in page_meta
        if isinstance(meta.get("confidence"), (int, float))
    ]
    retry_counts = [
        int(meta.get("retry_count") or 0)
        for meta in page_meta
        if isinstance(meta.get("retry_count"), (int, float))
    ]
    issues: list[str] = []
    seen: set[str] = set()
    for meta in page_meta:
        for issue in meta.get("issues") or []:
            text = str(issue or "").strip()
            if text and text not in seen:
                seen.add(text)
                issues.append(text)
    if isinstance(batch_summary, dict):
        for issue in batch_summary.get("issues") or []:
            text = str(issue or "").strip()
            if text and text not in seen:
                seen.add(text)
                issues.append(text)

    overall_confidence = None
    if isinstance(batch_summary, dict) and isinstance(batch_summary.get("overall_confidence"), (int, float)):
        overall_confidence = float(batch_summary["overall_confidence"])
    elif page_confidences:
        overall_confidence = round(sum(page_confidences) / len(page_confidences), 4)

    summary = {
        "overall_confidence": overall_confidence,
        "human_review": bool(batch_summary.get("human_review")) if isinstance(batch_summary, dict) else False,
        "review_status": str(batch_summary.get("review_status") or "") if isinstance(batch_summary, dict) else "",
        "review_reason": str(batch_summary.get("review_reason") or "") if isinstance(batch_summary, dict) else "",
        "issues": issues,
        "max_retry_count": max(retry_counts) if retry_counts else 0,
        "pages_with_retry": sum(1 for count in retry_counts if count > 0),
        "page_confidences": page_confidences,
    }
    if isinstance(batch_summary, dict):
        for key in ("quality_metrics", "rag_examples", "fields", "consistency"):
            if key in batch_summary:
                summary[key] = batch_summary[key]
    return summary


class OCRTaskOut(BaseModel):
    id: int
    filename: str

    file_path: str | None = None
    file_type: str
    mode: str = "layout"
    status: str
    page_count: int
    error_message: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class OCRTaskDetail(OCRTaskOut):
    full_text: str | None = None
    result_json: Any = None
    result_data: Any = None  # structured: {"pages": [...]}
    agent_meta: Any = None

    model_config = {"from_attributes": True}

    def model_post_init(self, __context):
        raw_pages = None
        if self.result_data and isinstance(self.result_data, dict) and self.result_data.get("pages"):
            raw_pages = self.result_data.get("pages")
        elif self.result_json:
            raw_pages = self.result_json

        if not raw_pages:
            return

        try:
            pages = normalize_result_pages(raw_pages)
        except Exception:
            pages = raw_pages if isinstance(raw_pages, list) else [raw_pages]

        self.result_json = pages
        self.agent_meta = _summarize_agent_meta(pages)
        self.result_data = {"pages": pages, "agent_meta": self.agent_meta}


class OCRTaskList(BaseModel):
    total: int
    tasks: list[OCRTaskOut]


class TaskProgressRequest(BaseModel):
    task_ids: list[int] = Field(default_factory=list)


class TaskProgressItem(BaseModel):
    id: int
    status: str
    error_message: str | None = None


class TaskProgressResponse(BaseModel):
    total: int
    done_count: int
    failed_count: int
    processing_count: int
    pending_count: int
    tasks: list[TaskProgressItem]
