"""Hierarchical multi-agent OCR workflow powered by LangGraph."""

from __future__ import annotations

import asyncio
import base64
import json
import logging
import mimetypes
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any, Awaitable, Callable, Literal, TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command, interrupt
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.ocr_engine import get_ocr_engine, pdf_to_images
from app.core.result_validation import normalize_result_pages, serialize_pages_text
from app.db.models import OCRTask
from app.domains.extraction import field_service
from app.llm.base import LLMMessage
from app.llm.client import get_llm_client
from app.services import vector_store
from app.services.archive_service import save_archive_record
from config import (
    CONFIDENCE_THRESHOLD,
    HUMAN_REVIEW_MAX_CONFIDENCE,
    HUMAN_REVIEW_MIN_CONFIDENCE,
    LANGCHAIN_PROJECT,
    LANGCHAIN_TRACING_V2,
    LANGGRAPH_CHECKPOINTER_BACKEND,
    LANGGRAPH_CHECKPOINTER_DSN,
    LANGGRAPH_CHECKPOINTER_REDIS_URL,
    LANGGRAPH_HITL_ENABLED,
    LANGGRAPH_HUMAN_REVIEW_INTERRUPT_THRESHOLD,
    MAX_RETRIES,
    VISION_ROUTE_COMPLEXITY_THRESHOLD,
)

try:
    from PIL import Image, ImageStat
except ImportError:  # pragma: no cover - optional in stripped environments
    Image = None
    ImageStat = None


logger = logging.getLogger(__name__)
_WORKFLOW_EVENT_CALLBACKS: dict[str, Callable[[str, dict[str, Any], dict[str, Any]], Awaitable[None]]] = {}
_WORKFLOW_DB_SESSIONS: dict[str, AsyncSession] = {}

ARCHIVE_FIELDS = ["档号", "文号", "责任者", "题名", "日期", "页数", "密级", "备注"]
PROCESSING_STRATEGIES = [
    "none",
    "enhance_contrast",
    "crop_and_zoom",
    "deskew",
    "denoise",
    "sharpen",
]


class ExtractionResult(BaseModel):
    fields: dict[str, str] = Field(default_factory=dict)
    confidence: float = 0.0
    issues: list[str] = Field(default_factory=list)
    source: Literal["ocr", "vision_llm", "hybrid", "fallback"] = "fallback"
    reasoning: str = ""
    review_reason: str = ""
    human_review: bool = False
    evidence: dict[str, str] = Field(default_factory=dict)


class PageAgentState(TypedDict, total=False):
    task_id: int
    batch_id: str
    filename: str
    mode: str
    page_num: int
    image_path: str
    max_retries: int
    retry_count: int
    processing_strategy: str
    should_use_vision: bool
    page_complexity: float
    route_reason: str
    ocr_result: dict[str, Any] | None
    llm_result: dict[str, Any] | None
    final_result: dict[str, Any] | None
    page_output: dict[str, Any] | None


class BatchSupervisorState(TypedDict, total=False):
    task_id: int
    batch_id: str
    filename: str
    file_path: str
    mode: str
    batch_folder: str
    page_images: list[str]
    temp_page_images: list[str]
    current_page_index: int
    total_pages: int
    page_outputs: list[dict[str, Any]]
    combined_pages: list[dict[str, Any]]
    merged_fields: dict[str, str]
    rag_examples: list[dict[str, Any]]
    overall_confidence: float
    issues: list[str]
    consistency: dict[str, Any]
    human_review: bool
    review_status: str
    review_reason: str
    quality_metrics: dict[str, Any]
    archive_saved: bool
    pending_interrupt: dict[str, Any] | None
    resume_target: str
    workflow_thread_id: str
    workflow_result: dict[str, Any] | None
def _blank_fields() -> dict[str, str]:
    return {field: "" for field in ARCHIVE_FIELDS}


def _clean_text(value: Any) -> str:
    return str(value or "").strip()


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _clamp_confidence(value: Any) -> float:
    return round(min(1.0, max(0.0, _safe_float(value, 0.0))), 4)


def _compact_text(value: Any) -> str:
    return "".join(_clean_text(value).split())


def _dedupe_issues(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        text = _clean_text(value)
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text)
    return result


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _page_outputs_to_combined_pages(page_outputs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    ordered = sorted(page_outputs, key=lambda item: int(item.get("page_num") or 0))
    return normalize_result_pages([dict(item.get("page") or {}) for item in ordered if item.get("page")])


def _summarize_page_outputs(page_outputs: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], float, list[str]]:
    combined_pages = _page_outputs_to_combined_pages(page_outputs)
    confidences = [_clamp_confidence(item.get("confidence")) for item in page_outputs if item is not None]
    overall_confidence = round(sum(confidences) / len(confidences), 4) if confidences else 0.0
    issues = _dedupe_issues(
        [
            str(issue)
            for item in page_outputs
            for issue in (item.get("issues") or [])
        ]
    )
    return combined_pages, overall_confidence, issues


def _build_workflow_thread_id(task_id: int, batch_id: str) -> str:
    safe_batch = _clean_text(batch_id).replace(" ", "_") or "default"
    return f"ocr-task-{int(task_id)}-{safe_batch}"


def _register_workflow_runtime(
    thread_id: str,
    *,
    db: AsyncSession | None = None,
    event_callback: Callable[[str, dict[str, Any], dict[str, Any]], Awaitable[None]] | None = None,
) -> None:
    if db is not None:
        _WORKFLOW_DB_SESSIONS[thread_id] = db
    if event_callback is not None:
        _WORKFLOW_EVENT_CALLBACKS[thread_id] = event_callback


def _clear_workflow_runtime(thread_id: str) -> None:
    _WORKFLOW_DB_SESSIONS.pop(thread_id, None)
    _WORKFLOW_EVENT_CALLBACKS.pop(thread_id, None)


def _get_workflow_db_session(state: BatchSupervisorState) -> AsyncSession | None:
    thread_id = _clean_text(state.get("workflow_thread_id"))
    if not thread_id:
        return None
    return _WORKFLOW_DB_SESSIONS.get(thread_id)


def _get_event_callback(
    state: BatchSupervisorState,
) -> Callable[[str, dict[str, Any], dict[str, Any]], Awaitable[None]] | None:
    thread_id = _clean_text(state.get("workflow_thread_id"))
    if not thread_id:
        return None
    return _WORKFLOW_EVENT_CALLBACKS.get(thread_id)


@lru_cache(maxsize=1)
def get_langgraph_checkpointer():
    backend = LANGGRAPH_CHECKPOINTER_BACKEND
    if backend == "postgres" and LANGGRAPH_CHECKPOINTER_DSN:
        try:
            from langgraph.checkpoint.postgres import PostgresSaver  # type: ignore[import-not-found]

            saver_factory = getattr(PostgresSaver, "from_conn_string", None)
            if callable(saver_factory):
                return saver_factory(LANGGRAPH_CHECKPOINTER_DSN)
            return PostgresSaver(LANGGRAPH_CHECKPOINTER_DSN)
        except Exception:
            logger.warning("Falling back to InMemorySaver because Postgres checkpointer is unavailable.", exc_info=True)
    if backend == "redis" and LANGGRAPH_CHECKPOINTER_REDIS_URL:
        try:
            from langgraph.checkpoint.redis import RedisSaver  # type: ignore[import-not-found]

            saver_factory = getattr(RedisSaver, "from_conn_string", None)
            if callable(saver_factory):
                return saver_factory(LANGGRAPH_CHECKPOINTER_REDIS_URL)
            return RedisSaver(LANGGRAPH_CHECKPOINTER_REDIS_URL)
        except Exception:
            logger.warning("Falling back to InMemorySaver because Redis checkpointer is unavailable.", exc_info=True)
    return InMemorySaver()


def _workflow_config(task_id: int, batch_id: str, thread_id: str) -> dict[str, Any]:
    metadata = {
        "task_id": int(task_id),
        "batch_id": _clean_text(batch_id),
        "component": "langgraph-batch-supervisor",
        "thread_id": thread_id,
    }
    config: dict[str, Any] = {
        "configurable": {"thread_id": thread_id},
        "metadata": metadata,
        "tags": ["ocr-web", "batch-supervisor", "hierarchical-agent"],
    }
    if LANGCHAIN_TRACING_V2:
        config["run_name"] = LANGCHAIN_PROJECT
    return config


def _merge_field_overlay(base_fields: dict[str, Any] | None, override_fields: dict[str, Any] | None) -> dict[str, str]:
    merged = _normalize_fields(base_fields)
    for field, value in (override_fields or {}).items():
        if field not in merged:
            continue
        cleaned = _clean_text(value)
        if cleaned:
            merged[field] = cleaned
    return merged


def _apply_resume_payload_to_page_output(
    page_output: dict[str, Any],
    resume_payload: dict[str, Any],
) -> dict[str, Any]:
    updated = dict(page_output)
    page_num = int(updated.get("page_num") or 0)
    fields = _merge_field_overlay(updated.get("fields"), resume_payload.get("fields") or resume_payload.get("updated_fields"))
    page = dict(updated.get("page") or {})
    agent_meta = dict(page.get("agent_meta") or {})
    corrected_text = _clean_text(resume_payload.get("page_text") or resume_payload.get("corrected_text"))
    if corrected_text:
        corrected_page = _page_from_transcript(page_num, corrected_text)
        corrected_page["agent_meta"] = agent_meta
        page = normalize_result_pages([corrected_page])[0]
    notes = _clean_text(resume_payload.get("notes") or resume_payload.get("comment"))
    reviewed_by = _clean_text(resume_payload.get("reviewed_by"))
    updated_confidence = max(
        _clamp_confidence(updated.get("confidence")),
        _clamp_confidence(resume_payload.get("confidence") or 0.98),
    )
    updated["fields"] = fields
    updated["confidence"] = updated_confidence
    updated["human_review"] = False
    updated["review_reason"] = notes or "人工复核已完成，继续执行工作流。"
    updated["issues"] = _dedupe_issues([str(item) for item in (resume_payload.get("issues") or [])])
    agent_meta["fields"] = fields
    agent_meta["confidence"] = updated_confidence
    agent_meta["human_review"] = False
    agent_meta["review_reason"] = updated["review_reason"]
    agent_meta["issues"] = list(updated["issues"])
    agent_meta["reviewed_at"] = _utc_now_iso()
    if reviewed_by:
        agent_meta["reviewed_by"] = reviewed_by
    page["agent_meta"] = agent_meta
    updated["page"] = normalize_result_pages([page])[0] if page else page
    return updated


def _build_page_interrupt_payload(state: BatchSupervisorState, page_output: dict[str, Any]) -> dict[str, Any]:
    page_num = int(page_output.get("page_num") or 0)
    return {
        "kind": "page_human_review",
        "task_id": int(state.get("task_id") or 0),
        "batch_id": _clean_text(state.get("batch_id")),
        "filename": _clean_text(state.get("filename")),
        "workflow_thread_id": _clean_text(state.get("workflow_thread_id")),
        "page_num": page_num,
        "confidence": _clamp_confidence(page_output.get("confidence")),
        "review_reason": _clean_text(page_output.get("review_reason")),
        "issues": list(page_output.get("issues") or []),
        "fields": _normalize_fields(page_output.get("fields")),
        "page": page_output.get("page") or {},
        "progress": {
            "current_page": page_num,
            "total_pages": int(state.get("total_pages") or 0),
            "percent": round((page_num / max(1, int(state.get("total_pages") or 1))) * 100.0, 2),
        },
    }


def _build_batch_interrupt_payload(state: BatchSupervisorState) -> dict[str, Any]:
    return {
        "kind": "batch_human_review",
        "task_id": int(state.get("task_id") or 0),
        "batch_id": _clean_text(state.get("batch_id")),
        "filename": _clean_text(state.get("filename")),
        "workflow_thread_id": _clean_text(state.get("workflow_thread_id")),
        "review_status": _clean_text(state.get("review_status")) or "pending_human_review",
        "review_reason": _clean_text(state.get("review_reason")),
        "issues": list(state.get("issues") or []),
        "fields": _normalize_fields(state.get("merged_fields")),
        "consistency": dict(state.get("consistency") or {}),
        "quality_metrics": dict(state.get("quality_metrics") or {}),
        "progress": {
            "current_page": int(state.get("current_page_index") or 0),
            "total_pages": int(state.get("total_pages") or 0),
            "percent": round(
                (
                    int(state.get("current_page_index") or 0)
                    / max(1, int(state.get("total_pages") or 1))
                )
                * 100.0,
                2,
            ),
        },
    }


def _build_interrupted_workflow_result(state: dict[str, Any], workflow_thread_id: str) -> dict[str, Any]:
    page_outputs = list(state.get("page_outputs") or [])
    combined_pages, overall_confidence, issues = _summarize_page_outputs(page_outputs)
    interrupt_items = list(state.get("__interrupt__") or [])
    interrupt_payload = {}
    if interrupt_items:
        interrupt_payload = dict(getattr(interrupt_items[0], "value", {}) or {})
    return {
        "status": "INTERRUPTED",
        "pages": combined_pages,
        "full_text": serialize_pages_text(combined_pages),
        "page_count": len(combined_pages),
        "final_fields": _normalize_fields(state.get("merged_fields")),
        "overall_confidence": overall_confidence,
        "issues": _dedupe_issues(issues + [str(item) for item in interrupt_payload.get("issues", [])]),
        "human_review": True,
        "review_status": _clean_text(state.get("review_status")) or "pending_human_review",
        "review_reason": _clean_text(state.get("review_reason")) or _clean_text(interrupt_payload.get("review_reason")),
        "quality_metrics": dict(state.get("quality_metrics") or {}),
        "rag_examples": list(state.get("rag_examples") or []),
        "consistency": dict(state.get("consistency") or {}),
        "page_outputs": page_outputs,
        "workflow_thread_id": workflow_thread_id,
        "interrupt_payload": interrupt_payload,
    }


async def _emit_state_event(
    state: BatchSupervisorState,
    event_type: str,
    payload: dict[str, Any] | None = None,
    progress: dict[str, Any] | None = None,
) -> None:
    callback = _get_event_callback(state)
    if callback is None:
        return
    try:
        await callback(event_type, payload or {}, progress or {})
    except Exception:  # noqa: BLE001
        logger.warning(
            "State callback failed: task_id=%s, event_type=%s",
            state.get("task_id"),
            event_type,
            exc_info=True,
        )


def _normalize_fields(fields: dict[str, Any] | None) -> dict[str, str]:
    payload = _blank_fields()
    for field in ARCHIVE_FIELDS:
        payload[field] = _clean_text((fields or {}).get(field))
    return payload


def _result_text(page: dict[str, Any]) -> str:
    return serialize_pages_text([page])


def _ocr_confidence(page: dict[str, Any]) -> float:
    values: list[float] = []
    for line in page.get("lines", []):
        values.append(_clamp_confidence(line.get("confidence")))
    for region in page.get("regions", []):
        for line in region.get("region_lines", []):
            values.append(_clamp_confidence(line.get("confidence")))
    if values:
        return round(sum(values) / len(values), 4)
    if _result_text(page):
        return 0.55
    return 0.0


def _page_from_transcript(page_num: int, transcript: str) -> dict[str, Any]:
    lines = []
    clean_lines = [line.strip() for line in str(transcript or "").splitlines() if line.strip()]
    for index, line in enumerate(clean_lines, start=1):
        lines.append(
            {
                "line_num": index,
                "text": line,
                "confidence": 0.55,
                "bbox": [],
                "bbox_type": "rect",
            }
        )
    return {
        "page_num": int(page_num),
        "regions": [],
        "lines": lines,
    }


def _estimate_page_complexity(image_path: str) -> float:
    if Image is None or ImageStat is None:
        return 0.5
    try:
        with Image.open(image_path) as raw:
            image = raw.convert("L")
            width, height = image.size
            stat = ImageStat.Stat(image)
            contrast = min((stat.stddev[0] or 0.0) / 96.0, 1.0)
            area_score = min((width * height) / float(2400 * 3200), 1.0)
            portrait_bonus = 0.15 if height > width * 1.2 else 0.0
            return round(min(1.0, (contrast * 0.45) + (area_score * 0.4) + portrait_bonus), 4)
    except Exception:  # noqa: BLE001
        logger.debug("Failed to estimate page complexity for %s", image_path, exc_info=True)
        return 0.5


def _page_route_should_use_vision(mode: str, complexity: float, retry_count: int) -> tuple[bool, str]:
    if mode in {"vl", "baidu_vl"}:
        return True, "当前模式要求启用 Vision LLM。"
    if retry_count > 0:
        return True, "低置信结果进入重试阶段，启用 Vision LLM 辅助仲裁。"
    if complexity >= VISION_ROUTE_COMPLEXITY_THRESHOLD:
        return True, f"页面复杂度 {complexity:.2f} 超过阈值，启用双路识别。"
    return False, f"页面复杂度 {complexity:.2f} 较低，优先仅运行传统 OCR。"


def _image_to_data_url(image_path: str) -> str:
    mime_type = mimetypes.guess_type(image_path)[0] or "image/png"
    raw = Path(image_path).read_bytes()
    encoded = base64.b64encode(raw).decode("utf-8")
    return f"data:{mime_type};base64,{encoded}"


def _parse_json_object(payload: str) -> dict[str, Any]:
    content = _clean_text(payload)
    if content.startswith("```"):
        content = content.strip("`")
        if content.startswith("json"):
            content = content[4:].strip()
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        decoder = json.JSONDecoder()
        for start in (index for index, char in enumerate(content) if char in "{["):
            try:
                parsed, _ = decoder.raw_decode(content[start:])
            except json.JSONDecodeError:
                continue
            if isinstance(parsed, dict):
                return parsed
        start = content.find("{")
        end = content.rfind("}")
        if start != -1 and end != -1 and end > start:
            candidate = content[start : end + 1]
            try:
                parsed = json.loads(candidate)
            except json.JSONDecodeError:
                logger.debug("Failed to salvage JSON payload: %s", candidate[:500], exc_info=True)
            else:
                if isinstance(parsed, dict):
                    return parsed
        logger.debug("Unable to parse JSON object from payload: %s", content[:1000])
        raise


async def _chat_json(
    *,
    vision: bool,
    messages: list[LLMMessage],
    timeout_seconds: float | None = None,
) -> dict[str, Any]:
    client = get_llm_client(vision=vision)
    if not client.is_available():
        raise RuntimeError("LLM provider is not configured.")
    response = await client.chat_completion(
        messages,
        temperature=0.1,
        response_format={"type": "json_object"},
        timeout_seconds=timeout_seconds,
    )
    return _parse_json_object(response.content)


def _heuristic_merge(ocr_result: dict[str, Any] | None, llm_result: dict[str, Any] | None) -> ExtractionResult:
    rule_fields = _normalize_fields((ocr_result or {}).get("fields"))
    llm_fields = _normalize_fields((llm_result or {}).get("fields"))
    ocr_conf = _clamp_confidence((ocr_result or {}).get("confidence"))
    llm_conf = _clamp_confidence((llm_result or {}).get("confidence"))

    chosen_fields = {}
    for field in ARCHIVE_FIELDS:
        left = rule_fields.get(field, "")
        right = llm_fields.get(field, "")
        if left and right and _compact_text(left) != _compact_text(right):
            chosen_fields[field] = left if ocr_conf >= llm_conf else right
        else:
            chosen_fields[field] = left or right

    issues = []
    issues.extend((ocr_result or {}).get("issues") or [])
    issues.extend((llm_result or {}).get("issues") or [])
    confidence = max(ocr_conf, llm_conf, 0.35)
    source = "ocr" if ocr_conf >= llm_conf else "vision_llm"
    if ocr_conf and llm_conf:
        source = "hybrid"
        confidence = round(min(1.0, (ocr_conf * 0.45) + (llm_conf * 0.55)), 4)

    return ExtractionResult(
        fields=chosen_fields,
        confidence=confidence,
        issues=_dedupe_issues(issues),
        source=source,
        reasoning="启用本地启发式合并，因为仲裁模型暂不可用。",
    )


async def node_page_plan(state: PageAgentState) -> dict[str, Any]:
    complexity = _estimate_page_complexity(state["image_path"])
    should_use_vision, reason = _page_route_should_use_vision(
        state.get("mode", "layout"),
        complexity,
        int(state.get("retry_count") or 0),
    )
    return {
        "page_complexity": complexity,
        "should_use_vision": should_use_vision,
        "route_reason": reason,
    }


async def route_page_execution(state: PageAgentState) -> list[str]:
    return ["node_ocr", "node_vision_llm"] if state.get("should_use_vision") else ["node_ocr"]


async def node_ocr(state: PageAgentState) -> dict[str, Any]:
    try:
        engine = get_ocr_engine(
            strategy=state.get("processing_strategy", "none"),
            mode=state.get("mode", "layout"),
        )
        page = await asyncio.to_thread(engine.recognize_page, state["image_path"])
        page = normalize_result_pages([{**page, "page_num": state["page_num"]}])[0]
        full_text = _result_text(page)
        fields = field_service.extract_fields(state["filename"], full_text, [page], 1)
        issues = []
        if not full_text:
            issues.append("传统 OCR 未提取到有效文本。")
        return {
            "ocr_result": {
                "page": page,
                "full_text": full_text,
                "fields": fields,
                "confidence": _ocr_confidence(page),
                "issues": issues,
                "processing_strategy": state.get("processing_strategy", "none"),
            }
        }
    except Exception as exc:  # noqa: BLE001
        logger.warning("Page OCR failed: task=%s page=%s", state.get("task_id"), state.get("page_num"), exc_info=True)
        return {
            "ocr_result": {
                "page": _page_from_transcript(state["page_num"], ""),
                "full_text": "",
                "fields": _blank_fields(),
                "confidence": 0.0,
                "issues": [f"传统 OCR 失败：{exc}"],
                "processing_strategy": state.get("processing_strategy", "none"),
            }
        }


async def node_vision_llm(state: PageAgentState) -> dict[str, Any]:
    try:
        image_data_url = await asyncio.to_thread(_image_to_data_url, state["image_path"])
        payload = await _chat_json(
            vision=True,
            timeout_seconds=90.0,
            messages=[
                LLMMessage(
                    role="system",
                    content=(
                        "你是档案整理场景的视觉抽取代理。"
                        "请识别当前页面中的关键信息，并只返回 JSON。"
                        "JSON 字段固定为：fields, confidence, issues, transcript, evidence。"
                        "fields 仅包含 档号、文号、责任者、题名、日期、页数、密级、备注。"
                        "confidence 为 0 到 1 的小数；issues 为字符串数组；evidence 为字段到证据短句的映射。"
                    ),
                ),
                LLMMessage(
                    role="user",
                    content=[
                        {
                            "type": "text",
                            "text": f"文件名：{state['filename']}\n页码：{state['page_num']}\n请识别该页档案内容。",
                        },
                        {
                            "type": "image_url",
                            "image_url": {"url": image_data_url},
                        },
                    ],
                ),
            ],
        )
        return {
            "llm_result": {
                "fields": _normalize_fields(payload.get("fields") or payload),
                "confidence": _clamp_confidence(payload.get("confidence")),
                "issues": _dedupe_issues([str(item) for item in (payload.get("issues") or [])]),
                "transcript": _clean_text(payload.get("transcript")),
                "evidence": {
                    key: _clean_text(value)
                    for key, value in (payload.get("evidence") or {}).items()
                    if _clean_text(value)
                },
            }
        }
    except Exception as exc:  # noqa: BLE001
        logger.info("Vision LLM unavailable for task=%s page=%s: %s", state.get("task_id"), state.get("page_num"), exc)
        return {
            "llm_result": {
                "fields": _blank_fields(),
                "confidence": 0.0,
                "issues": [f"Vision LLM 未返回可用结果：{exc}"],
                "transcript": "",
                "evidence": {},
            }
        }


async def _arbiter_merge_page_results(state: PageAgentState) -> ExtractionResult:
    ocr_result = state.get("ocr_result") or {}
    llm_result = state.get("llm_result") or {}

    if not state.get("should_use_vision"):
        ocr_fields = _normalize_fields(ocr_result.get("fields"))
        return ExtractionResult(
            fields=ocr_fields,
            confidence=_clamp_confidence(ocr_result.get("confidence")),
            issues=_dedupe_issues([str(item) for item in (ocr_result.get("issues") or [])]),
            source="ocr",
            reasoning=state.get("route_reason") or "页面复杂度较低，仅运行传统 OCR。",
            evidence={},
        )

    llm_fields = _normalize_fields(llm_result.get("fields"))
    if not any(_clean_text(value) for value in llm_fields.values()) and not _clean_text(llm_result.get("transcript")):
        fallback = _heuristic_merge(ocr_result, llm_result)
        if fallback.source == "vision_llm":
            fallback.source = "ocr"
        return fallback

    try:
        payload = await _chat_json(
            vision=False,
            timeout_seconds=60.0,
            messages=[
                LLMMessage(
                    role="system",
                    content=(
                        "你是档案整理系统中的仲裁节点。"
                        "请比较 OCR 结构化结果与 Vision LLM 结果，输出统一 ExtractionResult。"
                        "仅返回 JSON，字段固定为：fields, confidence, issues, source, reasoning, review_reason, human_review, evidence。"
                        "fields 只能包含 档号、文号、责任者、题名、日期、页数、密级、备注。"
                        "confidence 为 0 到 1 浮点数，source 只能是 ocr、vision_llm、hybrid、fallback。"
                    ),
                ),
                LLMMessage(
                    role="user",
                    content=json.dumps(
                        {
                            "task_id": state.get("task_id"),
                            "batch_id": state.get("batch_id"),
                            "filename": state.get("filename"),
                            "page_num": state.get("page_num"),
                            "route_reason": state.get("route_reason"),
                            "processing_strategy": state.get("processing_strategy"),
                            "ocr": {
                                "fields": _normalize_fields(ocr_result.get("fields")),
                                "confidence": _clamp_confidence(ocr_result.get("confidence")),
                                "issues": ocr_result.get("issues") or [],
                                "excerpt": _clean_text(ocr_result.get("full_text"))[:2000],
                            },
                            "vision": {
                                "fields": llm_fields,
                                "confidence": _clamp_confidence(llm_result.get("confidence")),
                                "issues": llm_result.get("issues") or [],
                                "transcript": _clean_text(llm_result.get("transcript"))[:2000],
                                "evidence": llm_result.get("evidence") or {},
                            },
                        },
                        ensure_ascii=False,
                    ),
                ),
            ],
        )
        source = _clean_text(payload.get("source")) or "hybrid"
        if source not in {"ocr", "vision_llm", "hybrid", "fallback"}:
            source = "hybrid"
        issues = []
        issues.extend([str(item) for item in (ocr_result.get("issues") or [])])
        issues.extend([str(item) for item in (llm_result.get("issues") or [])])
        issues.extend([str(item) for item in (payload.get("issues") or [])])
        result = ExtractionResult(
            fields=_normalize_fields(payload.get("fields")),
            confidence=max(
                _clamp_confidence(payload.get("confidence")),
                min(
                    0.98,
                    max(
                        _clamp_confidence(ocr_result.get("confidence")),
                        _clamp_confidence(llm_result.get("confidence")),
                    ),
                ),
            ),
            issues=_dedupe_issues(issues),
            source=source,
            reasoning=_clean_text(payload.get("reasoning")),
            review_reason=_clean_text(payload.get("review_reason")),
            human_review=bool(payload.get("human_review")),
            evidence={
                key: _clean_text(value)
                for key, value in (payload.get("evidence") or {}).items()
                if key in ARCHIVE_FIELDS and _clean_text(value)
            },
        )
        if not any(_clean_text(value) for value in result.fields.values()):
            return _heuristic_merge(ocr_result, llm_result)
        if result.confidence < CONFIDENCE_THRESHOLD and not result.review_reason:
            result.review_reason = "页面抽取置信度低于阈值，建议继续重试或进入人工复核。"
        return result
    except Exception:
        logger.info(
            "Arbiter fallback to heuristic merge: task=%s page=%s",
            state.get("task_id"),
            state.get("page_num"),
            exc_info=True,
        )
        return _heuristic_merge(ocr_result, llm_result)


async def node_evaluate_and_merge(state: PageAgentState) -> dict[str, Any]:
    result = await _arbiter_merge_page_results(state)
    ocr_page = (state.get("ocr_result") or {}).get("page") or {}
    llm_transcript = _clean_text((state.get("llm_result") or {}).get("transcript"))

    if ocr_page and (_result_text(ocr_page) or ocr_page.get("regions")):
        base_page = {**ocr_page, "page_num": state["page_num"]}
    elif llm_transcript:
        base_page = _page_from_transcript(state["page_num"], llm_transcript)
    else:
        base_page = _page_from_transcript(state["page_num"], "")

    agent_meta = {
        "confidence": result.confidence,
        "issues": result.issues,
        "source": result.source,
        "reasoning": result.reasoning,
        "retry_count": int(state.get("retry_count") or 0),
        "processing_strategy": state.get("processing_strategy", "none"),
        "page_complexity": _safe_float(state.get("page_complexity"), 0.0),
        "route_reason": _clean_text(state.get("route_reason")),
        "ocr_confidence": _clamp_confidence((state.get("ocr_result") or {}).get("confidence")),
        "llm_confidence": _clamp_confidence((state.get("llm_result") or {}).get("confidence")),
        "fields": result.fields,
        "human_review": bool(result.human_review),
        "review_reason": result.review_reason,
        "evidence": result.evidence,
    }
    page = normalize_result_pages([{**base_page, "agent_meta": agent_meta}])[0]
    page_output = {
        "page_num": state["page_num"],
        "page": page,
        "fields": result.fields,
        "confidence": result.confidence,
        "issues": result.issues,
        "source": result.source,
        "retry_count": int(state.get("retry_count") or 0),
        "processing_strategy": state.get("processing_strategy", "none"),
        "human_review": bool(result.human_review),
        "review_reason": result.review_reason,
    }
    return {
        "final_result": result.model_dump(mode="json"),
        "page_output": page_output,
    }


async def route_after_page_merge(state: PageAgentState) -> str:
    final_result = state.get("final_result") or {}
    confidence = _clamp_confidence(final_result.get("confidence"))
    retry_count = int(state.get("retry_count") or 0)
    max_retries = int(state.get("max_retries") or MAX_RETRIES)
    if confidence < CONFIDENCE_THRESHOLD and retry_count < max_retries:
        return "node_adjust_strategy"
    return "node_finalize_page"


async def node_adjust_strategy(state: PageAgentState) -> dict[str, Any]:
    current = _clean_text(state.get("processing_strategy")) or "none"
    retry_count = int(state.get("retry_count") or 0)
    try:
        current_index = PROCESSING_STRATEGIES.index(current)
    except ValueError:
        current_index = 0
    next_index = min(current_index + 1, len(PROCESSING_STRATEGIES) - 1)
    next_strategy = PROCESSING_STRATEGIES[next_index]
    if next_strategy == current and retry_count + 1 < len(PROCESSING_STRATEGIES):
        next_strategy = PROCESSING_STRATEGIES[retry_count + 1]

    logger.info(
        "Page agent retry scheduled: task=%s page=%s retry=%s strategy=%s->%s",
        state.get("task_id"),
        state.get("page_num"),
        retry_count + 1,
        current,
        next_strategy,
    )
    return {
        "retry_count": retry_count + 1,
        "processing_strategy": next_strategy,
        "ocr_result": None,
        "llm_result": None,
        "final_result": None,
        "page_output": None,
    }


async def node_finalize_page(state: PageAgentState) -> dict[str, Any]:
    page_output = state.get("page_output")
    if page_output:
        return {"page_output": page_output}

    final_result = state.get("final_result") or _heuristic_merge(
        state.get("ocr_result"),
        state.get("llm_result"),
    ).model_dump(mode="json")
    fallback_page = (state.get("ocr_result") or {}).get("page") or _page_from_transcript(
        state["page_num"],
        _clean_text((state.get("llm_result") or {}).get("transcript")),
    )
    fallback_page = normalize_result_pages(
        [
            {
                **fallback_page,
                "page_num": state["page_num"],
                "agent_meta": {
                    "confidence": _clamp_confidence(final_result.get("confidence")),
                    "issues": final_result.get("issues") or [],
                    "source": final_result.get("source") or "fallback",
                    "retry_count": int(state.get("retry_count") or 0),
                    "processing_strategy": state.get("processing_strategy", "none"),
                },
            }
        ]
    )[0]
    return {
        "page_output": {
            "page_num": state["page_num"],
            "page": fallback_page,
            "fields": _normalize_fields(final_result.get("fields")),
            "confidence": _clamp_confidence(final_result.get("confidence")),
            "issues": _dedupe_issues([str(item) for item in (final_result.get("issues") or [])]),
            "source": _clean_text(final_result.get("source")) or "fallback",
            "retry_count": int(state.get("retry_count") or 0),
            "processing_strategy": state.get("processing_strategy", "none"),
            "human_review": bool(final_result.get("human_review")),
            "review_reason": _clean_text(final_result.get("review_reason")),
        }
    }


def _merge_page_field_candidates(page_outputs: list[dict[str, Any]]) -> dict[str, str]:
    merged = _blank_fields()
    candidates: dict[str, dict[str, dict[str, Any]]] = {field: {} for field in ARCHIVE_FIELDS}
    for output in page_outputs:
        fields = _normalize_fields(output.get("fields"))
        confidence = _clamp_confidence(output.get("confidence"))
        for field, value in fields.items():
            text = _clean_text(value)
            if not text:
                continue
            normalized_key = _compact_text(text)
            bucket = candidates[field].setdefault(
                normalized_key,
                {"value": text, "count": 0, "score": 0.0, "max_confidence": 0.0},
            )
            bucket["count"] += 1
            bucket["score"] += confidence
            bucket["max_confidence"] = max(bucket["max_confidence"], confidence)
            if field == "题名" and len(text) > len(bucket["value"]):
                bucket["value"] = text

    for field in ARCHIVE_FIELDS:
        if field == "页数":
            merged[field] = str(len(page_outputs)) if page_outputs else ""
            continue
        if not candidates[field]:
            continue
        chosen = max(
            candidates[field].values(),
            key=lambda item: (item["count"], item["score"], item["max_confidence"], len(item["value"])),
        )
        merged[field] = chosen["value"]

    remark_values = []
    for output in page_outputs:
        remark = _clean_text(_normalize_fields(output.get("fields")).get("备注"))
        if remark:
            remark_values.append(remark)
    if remark_values:
        merged["备注"] = "；".join(_dedupe_issues(remark_values)[:3])
    return merged


def _build_quality_metrics(
    page_outputs: list[dict[str, Any]],
    overall_confidence: float,
    consistency: dict[str, Any] | None,
    human_review: bool,
) -> dict[str, Any]:
    confidences = [_clamp_confidence(item.get("confidence")) for item in page_outputs]
    retry_pages = [int(item.get("page_num") or 0) for item in page_outputs if int(item.get("retry_count") or 0) > 0]
    issue_pages = [int(item.get("page_num") or 0) for item in page_outputs if item.get("issues")]
    consistency = consistency or {}
    conflict_count = len((consistency.get("conflicts") or {}).keys())
    return {
        "page_count": len(page_outputs),
        "average_confidence": round(sum(confidences) / len(confidences), 4) if confidences else overall_confidence,
        "min_confidence": min(confidences) if confidences else overall_confidence,
        "max_confidence": max(confidences) if confidences else overall_confidence,
        "retry_pages": retry_pages,
        "pages_with_retry": len(retry_pages),
        "pages_with_issues": issue_pages,
        "conflict_count": conflict_count,
        "human_review": bool(human_review),
    }


async def node_prepare_batch(state: BatchSupervisorState) -> dict[str, Any]:
    task_id = int(state["task_id"])
    db = _get_workflow_db_session(state)
    task = await db.get(OCRTask, task_id) if db is not None else None
    filename = state.get("filename") or (task.filename if task else "")
    file_path = state.get("file_path") or (task.file_path if task else "")
    if not file_path:
        raise ValueError(f"OCRTask {task_id} missing file_path.")

    page_images = list(state.get("page_images") or [])
    temp_page_images = list(state.get("temp_page_images") or [])
    if not page_images:
        if Path(file_path).suffix.lower() == ".pdf":
            page_images = await asyncio.to_thread(pdf_to_images, file_path)
            temp_page_images = list(page_images)
        else:
            page_images = [file_path]
            temp_page_images = []

    return {
        "filename": filename,
        "file_path": file_path,
        "batch_folder": str(Path(file_path).parent),
        "page_images": page_images,
        "temp_page_images": temp_page_images,
        "current_page_index": int(state.get("current_page_index") or 0),
        "total_pages": len(page_images),
        "page_outputs": list(state.get("page_outputs") or []),
        "workflow_thread_id": _clean_text(state.get("workflow_thread_id"))
        or _build_workflow_thread_id(task_id, _clean_text(state.get("batch_id"))),
    }


async def route_after_prepare_batch(state: BatchSupervisorState) -> str:
    if int(state.get("current_page_index") or 0) >= len(state.get("page_images") or []):
        return "node_cross_page_consistency"
    return "node_process_next_page"


async def node_process_next_page(state: BatchSupervisorState) -> dict[str, Any]:
    page_graph = get_page_agent_graph()
    page_images = state.get("page_images") or []
    if not page_images:
        raise ValueError("No page images available for hierarchical OCR workflow.")
    current_index = int(state.get("current_page_index") or 0)
    if current_index >= len(page_images):
        combined_pages, overall_confidence, issues = _summarize_page_outputs(list(state.get("page_outputs") or []))
        return {
            "combined_pages": combined_pages,
            "overall_confidence": overall_confidence,
            "issues": issues,
        }

    page_num = current_index + 1
    image_path = page_images[current_index]
    initial_state: PageAgentState = {
        "task_id": int(state["task_id"]),
        "batch_id": _clean_text(state.get("batch_id")),
        "filename": _clean_text(state.get("filename")),
        "mode": _clean_text(state.get("mode")) or "layout",
        "page_num": page_num,
        "image_path": image_path,
        "max_retries": MAX_RETRIES,
        "retry_count": 0,
        "processing_strategy": "none",
    }
    try:
        page_state = await page_graph.ainvoke(initial_state)
        output = page_state.get("page_output") or {}
        if not output:
            raise RuntimeError(f"Page agent did not return page_output for page {page_num}.")
    except Exception as exc:  # noqa: BLE001
        logger.exception(
            "Page agent subgraph failed: task=%s page=%s",
            state.get("task_id"),
            page_num,
        )
        output = {
            "page_num": page_num,
            "page": normalize_result_pages(
                [
                    {
                        **_page_from_transcript(page_num, ""),
                        "agent_meta": {
                            "confidence": 0.0,
                            "issues": [f"Page Agent 执行失败：{exc}"],
                            "source": "fallback",
                            "retry_count": 0,
                            "processing_strategy": "none",
                            "human_review": True,
                            "review_reason": "页面子图执行失败，需要人工复核。",
                        },
                    }
                ]
            )[0],
            "fields": _blank_fields(),
            "confidence": 0.0,
            "issues": [f"Page Agent 执行失败：{exc}"],
            "source": "fallback",
            "retry_count": 0,
            "processing_strategy": "none",
            "human_review": True,
            "review_reason": "页面子图执行失败，需要人工复核。",
        }

    await _emit_state_event(
        state,
        "PAGE_COMPLETED",
        {
            "page_no": page_num,
            "page_confidence": _clamp_confidence(output.get("confidence")),
            "issues": list(output.get("issues") or []),
            "human_review_required": bool(output.get("human_review"))
            or _clamp_confidence(output.get("confidence")) <= LANGGRAPH_HUMAN_REVIEW_INTERRUPT_THRESHOLD,
            "note": "Page agent completed",
        },
        {
            "current_page": page_num,
            "total_pages": len(page_images),
            "percent": round((page_num / len(page_images)) * 100.0, 2),
        },
    )

    page_outputs = list(state.get("page_outputs") or [])
    page_outputs.append(output)
    page_outputs = sorted(page_outputs, key=lambda item: int(item.get("page_num") or 0))
    combined_pages, overall_confidence, issues = _summarize_page_outputs(page_outputs)
    pending_interrupt = None
    resume_target = "node_process_next_page"
    page_requires_review = bool(output.get("human_review")) or (
        _clamp_confidence(output.get("confidence")) <= LANGGRAPH_HUMAN_REVIEW_INTERRUPT_THRESHOLD
    )
    if (
        LANGGRAPH_HITL_ENABLED
        and page_requires_review
    ):
        pending_interrupt = _build_page_interrupt_payload(
            {
                **state,
                "workflow_thread_id": _clean_text(state.get("workflow_thread_id")),
                "total_pages": len(page_images),
            },
            output,
        )
    return {
        "page_outputs": page_outputs,
        "combined_pages": combined_pages,
        "overall_confidence": overall_confidence,
        "issues": issues,
        "current_page_index": current_index + 1,
        "total_pages": len(page_images),
        "pending_interrupt": pending_interrupt,
        "resume_target": resume_target,
    }


async def route_after_next_page(state: BatchSupervisorState) -> str:
    if state.get("pending_interrupt"):
        return "node_pause_for_human_review"
    if int(state.get("current_page_index") or 0) >= int(state.get("total_pages") or 0):
        return "node_cross_page_consistency"
    return "node_process_next_page"


async def route_after_pause(state: BatchSupervisorState) -> str:
    resume_target = _clean_text(state.get("resume_target"))
    if resume_target == "node_final_archiver_and_quality":
        return "node_final_archiver_and_quality"
    if int(state.get("current_page_index") or 0) >= int(state.get("total_pages") or 0):
        return "node_cross_page_consistency"
    return "node_process_next_page"


async def node_cross_page_consistency(state: BatchSupervisorState) -> dict[str, Any]:
    page_outputs = state.get("page_outputs") or []
    merged_fields = _merge_page_field_candidates(page_outputs)
    conflicts: dict[str, list[dict[str, Any]]] = {}
    aligned_fields: list[str] = []
    missing_fields: list[str] = []
    critical_fields = ["档号", "文号", "责任者", "日期", "密级"]

    for field in critical_fields:
        values: dict[str, dict[str, Any]] = {}
        for output in page_outputs:
            raw_value = _clean_text(_normalize_fields(output.get("fields")).get(field))
            if not raw_value:
                continue
            compact_value = _compact_text(raw_value)
            bucket = values.setdefault(compact_value, {"value": raw_value, "pages": []})
            bucket["pages"].append(
                {
                    "page_num": int(output.get("page_num") or 0),
                    "confidence": _clamp_confidence(output.get("confidence")),
                    "value": raw_value,
                }
            )
        if len(values) > 1:
            conflicts[field] = list(values.values())
        elif len(values) == 1:
            aligned_fields.append(field)
        else:
            missing_fields.append(field)

    issues = list(state.get("issues") or [])
    issues.extend([f"跨页一致性检查发现 `{field}` 存在冲突。" for field in conflicts])
    consistency = {
        "status": "conflict" if conflicts else "ok",
        "conflicts": conflicts,
        "aligned_fields": aligned_fields,
        "missing_fields": missing_fields,
    }
    return {
        "merged_fields": merged_fields,
        "consistency": consistency,
        "issues": _dedupe_issues(issues),
    }


async def node_rag_retrieve(state: BatchSupervisorState) -> dict[str, Any]:
    merged_fields = _normalize_fields(state.get("merged_fields"))
    query = " ".join(
        part
        for part in [
            merged_fields.get("题名"),
            merged_fields.get("文号"),
            merged_fields.get("责任者"),
            merged_fields.get("日期"),
            state.get("filename"),
        ]
        if _clean_text(part)
    )
    db = _get_workflow_db_session(state)
    if not query or db is None:
        return {"rag_examples": []}

    try:
        examples = await vector_store.similarity_search(
            query,
            k=3,
            db=db,
            exclude_batch_id=_clean_text(state.get("batch_id")),
        )
        return {"rag_examples": examples}
    except Exception:  # noqa: BLE001
        logger.warning(
            "RAG retrieval failed: task=%s batch=%s",
            state.get("task_id"),
            state.get("batch_id"),
            exc_info=True,
        )
        return {"rag_examples": []}


async def node_human_router(state: BatchSupervisorState) -> dict[str, Any]:
    overall_confidence = _clamp_confidence(state.get("overall_confidence"))
    issues = _dedupe_issues([str(item) for item in (state.get("issues") or [])])
    merged_fields = _normalize_fields(state.get("merged_fields"))
    consistency = state.get("consistency") or {}
    conflict_fields = list((consistency.get("conflicts") or {}).keys())

    human_review = False
    review_status = "approved"
    reason_parts: list[str] = []

    if conflict_fields:
        human_review = True
        review_status = "pending_human_review"
        reason_parts.append(f"跨页关键字段冲突：{', '.join(conflict_fields)}")

    if overall_confidence < HUMAN_REVIEW_MIN_CONFIDENCE:
        human_review = True
        review_status = "required"
        reason_parts.append(
            f"总体置信度 {overall_confidence:.2f} 低于 {HUMAN_REVIEW_MIN_CONFIDENCE:.2f}"
        )
    elif HUMAN_REVIEW_MIN_CONFIDENCE <= overall_confidence <= HUMAN_REVIEW_MAX_CONFIDENCE:
        human_review = True
        if review_status == "approved":
            review_status = "pending_human_review"
        reason_parts.append(f"总体置信度 {overall_confidence:.2f} 落在人工审核区间")

    missing_core_fields = [
        field
        for field in ("档号", "文号", "责任者", "题名", "日期")
        if not _clean_text(merged_fields.get(field))
    ]
    if len(missing_core_fields) >= 2:
        human_review = True
        if review_status == "approved":
            review_status = "pending_human_review"
        reason_parts.append(f"关键字段缺失较多：{', '.join(missing_core_fields)}")

    if issues and not reason_parts:
        human_review = True
        if review_status == "approved":
            review_status = "pending_human_review"
        reason_parts.append(issues[0])

    review_reason = "；".join(_dedupe_issues(reason_parts))
    if human_review:
        await _emit_state_event(
            state,
            "HUMAN_REVIEW_REQUIRED",
            {
                "review_status": review_status,
                "review_reason": review_reason,
                "conflict_fields": conflict_fields,
                "issues": issues,
            },
        )

    page_outputs = []
    for output in state.get("page_outputs") or []:
        page_confidence = _clamp_confidence(output.get("confidence"))
        page_issues = _dedupe_issues([str(item) for item in (output.get("issues") or [])])
        page_review = bool(page_issues) or page_confidence <= HUMAN_REVIEW_MAX_CONFIDENCE
        if human_review and not page_review and page_confidence < CONFIDENCE_THRESHOLD:
            page_review = True
        page_reason = _clean_text(output.get("review_reason")) or (
            review_reason if page_review and review_reason else ""
        )
        updated = dict(output)
        updated["human_review"] = page_review
        updated["review_reason"] = page_reason
        page = dict(updated.get("page") or {})
        page_meta = dict(page.get("agent_meta") or {})
        page_meta["human_review"] = page_review
        if page_reason:
            page_meta["review_reason"] = page_reason
        page["agent_meta"] = page_meta
        updated["page"] = page
        page_outputs.append(updated)

    combined_pages = normalize_result_pages([item["page"] for item in page_outputs]) if page_outputs else []
    pending_interrupt = None
    resume_target = "node_final_archiver_and_quality"
    if human_review and LANGGRAPH_HITL_ENABLED:
        pending_interrupt = _build_batch_interrupt_payload(
            {
                **state,
                "merged_fields": merged_fields,
                "review_status": review_status,
                "review_reason": review_reason,
                "issues": issues,
                "quality_metrics": dict(state.get("quality_metrics") or {}),
            }
        )
    return {
        "human_review": human_review,
        "review_status": review_status,
        "review_reason": review_reason,
        "page_outputs": page_outputs,
        "combined_pages": combined_pages,
        "pending_interrupt": pending_interrupt,
        "resume_target": resume_target,
    }


async def route_after_human_router(state: BatchSupervisorState) -> str:
    if state.get("pending_interrupt"):
        return "node_pause_for_human_review"
    if state.get("human_review"):
        return "node_pending_human_review"
    return "node_final_archiver_and_quality"


async def node_pending_human_review(state: BatchSupervisorState) -> dict[str, Any]:
    issues = list(state.get("issues") or [])
    issues.append("任务已挂起人工审核，当前仅保留候选结果，暂不写入 archive_records。")
    return {
        "issues": _dedupe_issues(issues),
        "review_status": state.get("review_status") or "pending_human_review",
    }


async def node_pause_for_human_review(state: BatchSupervisorState) -> dict[str, Any]:
    interrupt_payload = dict(state.get("pending_interrupt") or {})
    interrupt_payload.setdefault("workflow_thread_id", _clean_text(state.get("workflow_thread_id")))
    interrupt_payload.setdefault("issued_at", _utc_now_iso())
    resume_payload = interrupt(interrupt_payload)
    resume_data = dict(resume_payload or {})
    kind = _clean_text(interrupt_payload.get("kind"))
    updates: dict[str, Any] = {
        "pending_interrupt": None,
        "review_status": "approved_by_human",
        "review_reason": _clean_text(resume_data.get("notes") or resume_data.get("comment"))
        or "人工复核已完成，工作流恢复执行。",
        "human_review": False,
    }

    if kind == "page_human_review":
        target_page = int(interrupt_payload.get("page_num") or 0)
        page_outputs: list[dict[str, Any]] = []
        for item in state.get("page_outputs") or []:
            if int(item.get("page_num") or 0) == target_page:
                page_outputs.append(_apply_resume_payload_to_page_output(item, resume_data))
            else:
                page_outputs.append(dict(item))
        combined_pages, overall_confidence, issues = _summarize_page_outputs(page_outputs)
        issues = _dedupe_issues(issues + ["人工复核已完成，已恢复后续页面处理。"])
        updates.update(
            {
                "page_outputs": page_outputs,
                "combined_pages": combined_pages,
                "overall_confidence": overall_confidence,
                "issues": issues,
                "resume_target": "node_process_next_page",
            }
        )
        return updates

    merged_fields = _merge_field_overlay(
        state.get("merged_fields"),
        resume_data.get("fields") or resume_data.get("updated_fields"),
    )
    issues = _dedupe_issues(list(state.get("issues") or []) + ["人工复核已完成，继续归档与导出流程。"])
    updates.update(
        {
            "merged_fields": merged_fields,
            "issues": issues,
            "resume_target": "node_final_archiver_and_quality",
        }
    )
    return updates


async def node_final_archiver_and_quality(state: BatchSupervisorState) -> dict[str, Any]:
    merged_fields = _normalize_fields(state.get("merged_fields"))
    combined_pages = normalize_result_pages(state.get("combined_pages") or [])
    overall_confidence = _clamp_confidence(state.get("overall_confidence"))
    issues = _dedupe_issues([str(item) for item in (state.get("issues") or [])])
    human_review = bool(state.get("human_review"))
    consistency = state.get("consistency") or {}
    rag_examples = state.get("rag_examples") or []
    quality_metrics = _build_quality_metrics(
        state.get("page_outputs") or [],
        overall_confidence,
        consistency,
        human_review,
    )
    batch_summary = {
        "overall_confidence": overall_confidence,
        "human_review": human_review,
        "review_status": _clean_text(state.get("review_status")) or ("pending_human_review" if human_review else "approved"),
        "review_reason": _clean_text(state.get("review_reason")),
        "issues": issues,
        "quality_metrics": quality_metrics,
        "rag_examples": rag_examples,
        "fields": merged_fields,
        "consistency": consistency,
    }

    if combined_pages:
        first_meta = dict(combined_pages[0].get("agent_meta") or {})
        first_meta["batch_summary"] = batch_summary
        combined_pages[0]["agent_meta"] = first_meta
        combined_pages = normalize_result_pages(combined_pages)

    archive_saved = False
    db = _get_workflow_db_session(state)
    if db is not None and not human_review:
        try:
            await save_archive_record(
                db,
                int(state["task_id"]),
                _clean_text(state.get("batch_id")),
                _clean_text(state.get("batch_folder")),
                merged_fields,
            )
            archive_saved = True
        except Exception:  # noqa: BLE001
            logger.exception("Final archiver failed for task=%s", state.get("task_id"))
            issues = _dedupe_issues(issues + ["归档写入失败，已保留 OCR 结果供后续补偿处理。"])
            batch_summary["issues"] = issues

    workflow_result = {
        "pages": combined_pages,
        "full_text": serialize_pages_text(combined_pages),
        "page_count": len(combined_pages),
        "final_fields": merged_fields,
        "overall_confidence": overall_confidence,
        "issues": issues,
        "human_review": human_review,
        "review_status": batch_summary["review_status"],
        "review_reason": batch_summary["review_reason"],
        "quality_metrics": quality_metrics,
        "rag_examples": rag_examples,
        "consistency": consistency,
        "archive_saved": archive_saved,
    }
    return {
        "combined_pages": combined_pages,
        "quality_metrics": quality_metrics,
        "archive_saved": archive_saved,
        "workflow_result": workflow_result,
    }


@lru_cache(maxsize=1)
def get_page_agent_graph():
    graph = StateGraph(PageAgentState)
    graph.add_node("node_page_plan", node_page_plan)
    graph.add_node("node_ocr", node_ocr)
    graph.add_node("node_vision_llm", node_vision_llm)
    graph.add_node("node_evaluate_and_merge", node_evaluate_and_merge)
    graph.add_node("node_adjust_strategy", node_adjust_strategy)
    graph.add_node("node_finalize_page", node_finalize_page)

    graph.add_edge(START, "node_page_plan")
    graph.add_conditional_edges("node_page_plan", route_page_execution)
    graph.add_edge("node_ocr", "node_evaluate_and_merge")
    graph.add_edge("node_vision_llm", "node_evaluate_and_merge")
    graph.add_conditional_edges("node_evaluate_and_merge", route_after_page_merge)
    graph.add_edge("node_adjust_strategy", "node_page_plan")
    graph.add_edge("node_finalize_page", END)
    return graph.compile()


def _compile_batch_supervisor_graph(*, with_checkpointer: bool):
    graph = StateGraph(BatchSupervisorState)
    graph.add_node("node_prepare_batch", node_prepare_batch)
    graph.add_node("node_process_next_page", node_process_next_page)
    graph.add_node("node_cross_page_consistency", node_cross_page_consistency)
    graph.add_node("node_rag_retrieve", node_rag_retrieve)
    graph.add_node("node_human_router", node_human_router)
    graph.add_node("node_pending_human_review", node_pending_human_review)
    graph.add_node("node_pause_for_human_review", node_pause_for_human_review)
    graph.add_node("node_final_archiver_and_quality", node_final_archiver_and_quality)

    graph.add_edge(START, "node_prepare_batch")
    graph.add_conditional_edges("node_prepare_batch", route_after_prepare_batch)
    graph.add_conditional_edges("node_process_next_page", route_after_next_page)
    graph.add_edge("node_cross_page_consistency", "node_rag_retrieve")
    graph.add_edge("node_rag_retrieve", "node_human_router")
    graph.add_conditional_edges("node_human_router", route_after_human_router)
    graph.add_edge("node_pending_human_review", "node_final_archiver_and_quality")
    graph.add_conditional_edges("node_pause_for_human_review", route_after_pause)
    graph.add_edge("node_final_archiver_and_quality", END)
    if with_checkpointer:
        return graph.compile(checkpointer=get_langgraph_checkpointer())
    return graph.compile()


@lru_cache(maxsize=1)
def get_batch_supervisor_graph():
    return _compile_batch_supervisor_graph(with_checkpointer=True)


@lru_cache(maxsize=1)
def get_batch_supervisor_graph_for_studio():
    return _compile_batch_supervisor_graph(with_checkpointer=False)


async def run_hierarchical_ocr_task(
    db: AsyncSession,
    task_id: int,
    *,
    mode: str = "layout",
    batch_id: str = "",
) -> tuple[OCRTask, dict[str, Any]]:
    task = await db.get(OCRTask, task_id)
    if not task:
        raise ValueError(f"Task not found: {task_id}")

    task.status = "processing"
    task.error_message = None
    await db.commit()

    file_path = task.file_path
    page_images: list[str] = []
    temp_page_images: list[str] = []
    final_state: dict[str, Any] | None = None

    try:
        if Path(file_path).suffix.lower() == ".pdf":
            page_images = await asyncio.to_thread(pdf_to_images, file_path)
            temp_page_images = list(page_images)
        else:
            page_images = [file_path]

        workflow_thread_id = _build_workflow_thread_id(task.id, batch_id)
        _register_workflow_runtime(workflow_thread_id, db=db)
        final_state = await get_batch_supervisor_graph().ainvoke(
            {
                "task_id": task.id,
                "batch_id": batch_id,
                "filename": task.filename,
                "file_path": task.file_path,
                "mode": mode,
                "page_images": page_images,
                "temp_page_images": temp_page_images,
                "workflow_thread_id": workflow_thread_id,
            },
            config=_workflow_config(task.id, batch_id, workflow_thread_id),
        )
        if "__interrupt__" in final_state:
            interrupted = _build_interrupted_workflow_result(final_state, workflow_thread_id)
            pages = normalize_result_pages(interrupted.get("pages") or [])
            task.result_json = pages
            task.full_text = _clean_text(interrupted.get("full_text")) or serialize_pages_text(pages)
            task.page_count = int(interrupted.get("page_count") or len(pages))
            task.status = "human_review"
            task.error_message = None
            await db.commit()
            await db.refresh(task)
            return task, interrupted
        workflow_result = final_state.get("workflow_result") or {}
        pages = normalize_result_pages(workflow_result.get("pages") or [])
        task.result_json = pages
        task.full_text = _clean_text(workflow_result.get("full_text")) or serialize_pages_text(pages)
        task.page_count = int(workflow_result.get("page_count") or len(pages))
        task.status = "done"
        task.error_message = None
        await db.commit()
        await db.refresh(task)
        return task, workflow_result
    except Exception as exc:  # noqa: BLE001
        logger.exception("Hierarchical OCR workflow failed for task=%s", task_id)
        task.status = "failed"
        task.error_message = str(exc)
        await db.commit()
        await db.refresh(task)
        return task, {}
    finally:
        _clear_workflow_runtime(_build_workflow_thread_id(task.id, batch_id))
        cleanup_images = temp_page_images or list((final_state or {}).get("temp_page_images") or [])
        for image_path in cleanup_images:
            try:
                Path(image_path).unlink(missing_ok=True)
            except Exception:
                logger.debug("Failed to cleanup temp page image: %s", image_path, exc_info=True)


async def run_hierarchical_ocr_detached(
    *,
    task_id: int,
    filename: str,
    file_path: str = "",
    mode: str = "layout",
    batch_id: str = "",
    event_callback: Callable[[str, dict[str, Any], dict[str, Any]], Awaitable[None]] | None = None,
    workflow_thread_id: str = "",
    resume_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    page_images: list[str] = []
    temp_page_images: list[str] = []
    final_state: dict[str, Any] | None = None

    try:
        resolved_thread_id = _clean_text(workflow_thread_id) or _build_workflow_thread_id(task_id, batch_id)
        _register_workflow_runtime(resolved_thread_id, event_callback=event_callback)
        if resume_payload is None:
            if not file_path:
                raise ValueError("Initial hierarchical OCR invocation requires file_path.")
            if Path(file_path).suffix.lower() == ".pdf":
                page_images = await asyncio.to_thread(pdf_to_images, file_path)
                temp_page_images = list(page_images)
            else:
                page_images = [file_path]
            graph_input: dict[str, Any] | Command = {
                "task_id": int(task_id),
                "batch_id": batch_id,
                "filename": filename,
                "file_path": file_path,
                "mode": mode,
                "page_images": page_images,
                "temp_page_images": temp_page_images,
                "workflow_thread_id": resolved_thread_id,
            }
        else:
            graph_input = Command(resume=resume_payload)

        final_state = await get_batch_supervisor_graph().ainvoke(
            graph_input,
            config=_workflow_config(task_id, batch_id, resolved_thread_id),
        )
        if "__interrupt__" in final_state:
            workflow_result = _build_interrupted_workflow_result(final_state, resolved_thread_id)
            workflow_result["page_images"] = list(page_images)
            return workflow_result
        workflow_result = dict(final_state.get("workflow_result") or {})
        workflow_result["page_outputs"] = list(final_state.get("page_outputs") or [])
        workflow_result["page_images"] = list(page_images)
        workflow_result["workflow_thread_id"] = resolved_thread_id
        return workflow_result
    finally:
        _clear_workflow_runtime(_clean_text(workflow_thread_id) or _build_workflow_thread_id(task_id, batch_id))
        cleanup_images = temp_page_images or list((final_state or {}).get("temp_page_images") or [])
        for image_path in cleanup_images:
            try:
                Path(image_path).unlink(missing_ok=True)
            except Exception:
                logger.debug("Failed to cleanup temp page image: %s", image_path, exc_info=True)
