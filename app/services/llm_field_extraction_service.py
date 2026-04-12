import asyncio
import json
import os
import re
from typing import Any

from app.db.models import OCRTask
from app.services.excel_export import extract_fields
from config import (
    MINIMAX_API_KEY,
    MINIMAX_BASE_URL,
    MINIMAX_ENABLED,
    MINIMAX_MAX_INPUT_CHARS,
    MINIMAX_MODEL,
    MINIMAX_TIMEOUT_SECONDS,
)

try:
    import httpx
except ImportError:  # pragma: no cover - import guard for incomplete environments
    httpx = None


ARCHIVE_FIELDS = ["档号", "文号", "责任者", "题名", "日期", "页数", "密级", "备注"]
_LLM_PREFERRED_FIELDS: frozenset[str] = frozenset({"题名", "备注"})
_MANUAL_REVIEW_FIELDS: frozenset[str] = frozenset()
TITLE_TYPES = {"title", "doc_title", "paragraph_title", "content_title", "abstract_title", "reference_title"}
DOC_NO_PATTERN = re.compile(
    r"[\u4e00-\u9fa5A-Za-z]{2,20}(?:[\[\(（]?\d{4}[\]\)）]?)\s*(?:第\s*)?\d+\s*号"
)
PAGE_SEPARATOR_PATTERN = re.compile(r"^---\s*第\s*\d+\s*页\s*---$")
QA_SUPPORT_LEVELS = {"supported", "partial", "insufficient"}


class MiniMaxServiceError(RuntimeError):
    def __init__(self, status_code: int, detail: str):
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


def _blank_fields() -> dict[str, str]:
    return {field: "" for field in ARCHIVE_FIELDS}


def _resolve_llm_runtime_config() -> dict[str, Any]:
    llm_base_url = os.getenv("LLM_BASE_URL", "").strip()
    llm_api_key = os.getenv("LLM_API_KEY", "").strip()
    llm_model = os.getenv("LLM_MODEL", "").strip()
    timeout_raw = os.getenv("LLM_TIMEOUT_SECONDS", "").strip()
    try:
        timeout_seconds = float(timeout_raw) if timeout_raw else float(MINIMAX_TIMEOUT_SECONDS)
    except ValueError:
        timeout_seconds = float(MINIMAX_TIMEOUT_SECONDS)

    if MINIMAX_ENABLED:
        base_url = MINIMAX_BASE_URL
        api_key = MINIMAX_API_KEY
        model = MINIMAX_MODEL
        enabled = True
    else:
        base_url = llm_base_url or MINIMAX_BASE_URL
        api_key = llm_api_key or MINIMAX_API_KEY
        model = llm_model or MINIMAX_MODEL
        enabled = bool(base_url and api_key and model)

    return {
        "enabled": enabled,
        "base_url": base_url.rstrip("/"),
        "api_key": api_key,
        "model": model,
        "timeout_seconds": timeout_seconds,
    }


def _coerce_string(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    return str(value).strip()


def _normalize_compare_value(value: Any) -> str:
    return re.sub(r"\s+", "", _coerce_string(value))


def _dedupe_keep_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        clean = _coerce_string(value)
        if not clean or clean in seen:
            continue
        seen.add(clean)
        result.append(clean)
    return result


def _extract_clean_lines(full_text: str) -> list[str]:
    lines = []
    for raw in (full_text or "").splitlines():
        clean = _coerce_string(raw)
        if not clean or PAGE_SEPARATOR_PATTERN.match(clean):
            continue
        lines.append(clean)
    return lines


def collect_first_page_title_candidates(result_json: Any, limit: int = 8) -> list[str]:
    if isinstance(result_json, list):
        first_page = result_json[0] if result_json else {}
    elif isinstance(result_json, dict):
        first_page = result_json
    else:
        first_page = {}

    candidates: list[str] = []
    if isinstance(first_page, dict):
        for region in first_page.get("regions", []):
            if not isinstance(region, dict):
                continue
            region_type = _coerce_string(region.get("type"))
            if region_type in TITLE_TYPES:
                candidates.append(_coerce_string(region.get("content")))
        if len(candidates) < limit:
            for line in first_page.get("lines", []):
                if not isinstance(line, dict):
                    continue
                candidates.append(_coerce_string(line.get("text")))
                if len(candidates) >= limit:
                    break

    return _dedupe_keep_order(candidates)[:limit]


def collect_doc_no_candidates(full_text: str, limit: int = 5) -> list[str]:
    candidates: list[str] = []
    for line in _extract_clean_lines(full_text):
        if DOC_NO_PATTERN.search(line):
            candidates.append(line)
        if len(candidates) >= limit:
            break
    return _dedupe_keep_order(candidates)[:limit]


def build_minimax_input_text(
    full_text: str,
    *,
    title_candidates: list[str] | None = None,
    doc_no_candidates: list[str] | None = None,
    max_chars: int = MINIMAX_MAX_INPUT_CHARS,
) -> str:
    clean_text = "\n".join(_extract_clean_lines(full_text))

    extra_sections: list[str] = []
    if title_candidates:
        extra_sections.append("标题候选：\n" + "\n".join(f"- {item}" for item in _dedupe_keep_order(title_candidates)))
    if doc_no_candidates:
        extra_sections.append("文号候选：\n" + "\n".join(f"- {item}" for item in _dedupe_keep_order(doc_no_candidates)))

    extra_text = "\n\n".join(extra_sections).strip()
    if len(clean_text) <= max_chars and not extra_text:
        return clean_text

    remaining = max(max_chars - len(extra_text) - 260, 360)
    front_size = max(int(remaining * 0.45), 200)
    middle_size = max(int(remaining * 0.2), 120)
    tail_size = max(int(remaining * 0.35), 200)

    front = clean_text[:front_size]
    middle_start = max((len(clean_text) // 2) - (middle_size // 2), 0)
    middle = clean_text[middle_start: middle_start + middle_size]
    tail = clean_text[-tail_size:] if tail_size < len(clean_text) else clean_text

    excerpt = "\n".join(
        [
            "[前部摘录]",
            front,
            "",
            "[中部摘录]",
            middle,
            "",
            "[尾部摘录]",
            tail,
        ]
    ).strip()

    final_text = excerpt if not extra_text else f"{extra_text}\n\n[OCR全文摘录]\n{excerpt}"
    return final_text[:max_chars]


def _build_prompt(
    *,
    filename: str,
    page_count: int,
    rule_fields: dict[str, str],
    excerpt_text: str,
    file_path: str = "",
) -> str:
    path_hint = ""
    if file_path:
        path_hint = f"文件路径：{file_path}\n"

    return (
        "你是中国档案、公文、合同和申报材料归档字段抽取助手。\n"
        "你只能根据给定文本抽取，不得猜测，不得补全未知内容。\n"
        "请只返回一个 JSON 对象，不要输出额外解释、不要用 Markdown。\n"
        "JSON 必须包含以下字段：档号、文号、责任者、题名、日期、页数、密级、备注、evidence。\n"
        "其中 evidence 也必须是一个 JSON 对象，键为前面 8 个字段名，值为支持该字段的原文短句；没有证据就填空字符串。\n"
        "如果某字段无法确定，请填空字符串。\n\n"
        "【字段填写规范】\n"
        "- 档号：从文件名或文件夹路径解析，格式为 WS·年度·保管期限-件号（如 WS·2024·D30-0156）。"
        "同一文件夹内所有图片共享同一个档号。\n"
        "- 文号：从正文首页提取，如 中办发〔2023〕12号 或 2024年第13期。无则留空。\n"
        "- 责任者：发文机构全称，优先从首页标题区或末页落款/盖章/印发处提取。多个用中文分号分隔。\n"
        "- 题名：完整标题，从首页正文标题区提取。\n"
        "- 日期：优先取末页「印发」日期或正文成文日期，格式 YYYYMMDD 或 YYYY-MM-DD。\n"
        "- 页数：文档总页数。\n"
        "- 密级：普通/公开/内部/秘密/机密/绝密，无则留空。\n"
        "- 备注：破损、缺页、附件类型等特殊说明，无则留空。\n\n"
        f"文件名：{filename}\n"
        f"{path_hint}"
        f"页数：{page_count}\n"
        f"规则抽取结果：{json.dumps(rule_fields, ensure_ascii=False)}\n\n"
        "OCR 文本如下：\n"
        f"{excerpt_text}"
    )


def _extract_message_text(response_json: dict[str, Any]) -> str:
    choices = response_json.get("choices") or []
    if not choices:
        raise MiniMaxServiceError(502, "MiniMax response did not include any choices.")

    content = (((choices[0] or {}).get("message") or {}).get("content"))
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                text = item.get("text") or item.get("content") or ""
                if text:
                    parts.append(str(text))
        return "\n".join(parts).strip()
    raise MiniMaxServiceError(502, "MiniMax response content was not a text payload.")


def _parse_json_object(text: str) -> dict[str, Any]:
    clean = _coerce_string(text)
    clean = re.sub(r"^\s*<think>.*?</think>\s*", "", clean, flags=re.DOTALL)
    if clean.startswith("```"):
        clean = re.sub(r"^```(?:json)?\s*", "", clean)
        clean = re.sub(r"\s*```$", "", clean)
    try:
        return json.loads(clean)
    except json.JSONDecodeError:
        decoder = json.JSONDecoder()
        for start in (index for index, char in enumerate(clean) if char == "{"):
            try:
                payload, _end = decoder.raw_decode(clean[start:])
            except json.JSONDecodeError:
                continue
            if isinstance(payload, dict):
                return payload
        raise MiniMaxServiceError(502, "MiniMax returned invalid JSON.")


async def _post_minimax_chat_completions(
    payload: dict[str, Any],
    *,
    timeout_seconds: float | None = None,
) -> dict[str, Any]:
    runtime = _resolve_llm_runtime_config()
    if not runtime["enabled"]:
        raise MiniMaxServiceError(503, "MiniMax field extraction is disabled.")
    if not runtime["api_key"]:
        raise MiniMaxServiceError(503, "MINIMAX_API_KEY is not configured.")
    if httpx is None:
        raise MiniMaxServiceError(503, "httpx is required for MiniMax integration.")

    attempts = 3
    for attempt in range(attempts):
        try:
            async with httpx.AsyncClient(timeout=timeout_seconds or runtime["timeout_seconds"]) as client:
                response = await client.post(
                    f"{runtime['base_url']}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {runtime['api_key']}",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                )
        except httpx.TimeoutException as exc:
            raise MiniMaxServiceError(504, "MiniMax request timed out.") from exc
        except httpx.HTTPError as exc:
            raise MiniMaxServiceError(502, f"MiniMax request failed: {exc}") from exc

        if response.status_code >= 500 and attempt < attempts - 1:
            await asyncio.sleep(0.5 * (attempt + 1))
            continue
        break

    if response.status_code >= 400:
        response_text = _coerce_string(response.text)
        response_text = re.sub(r"\s+", " ", response_text)[:200]
        if response.status_code in {401, 403}:
            detail = f"MiniMax returned HTTP {response.status_code}. 智能服务暂未连通，请检查本地模型配置。"
        elif response.status_code == 404:
            detail = f"MiniMax returned HTTP {response.status_code}. 上游接口地址或模型名称可能未生效，请检查本地模型配置。"
        else:
            detail = f"MiniMax returned HTTP {response.status_code}. 上游智能服务返回异常。"

        if response_text:
            detail = f"{detail} Upstream: {response_text}"

        raise MiniMaxServiceError(502, detail)

    try:
        return response.json()
    except ValueError as exc:
        raise MiniMaxServiceError(502, "MiniMax returned a non-JSON response.") from exc


def _resolve_field_extraction_timeout(*, page_count: int, excerpt_text: str) -> float:
    timeout = MINIMAX_TIMEOUT_SECONDS
    excerpt_length = len(_coerce_string(excerpt_text))
    if page_count >= 6 or excerpt_length >= 4000:
        return max(timeout, 180.0)
    if page_count >= 3 or excerpt_length >= 2000:
        return max(timeout, 120.0)
    return timeout


def normalize_llm_output(payload: dict[str, Any]) -> dict[str, Any]:
    normalized = _blank_fields()
    for field in ARCHIVE_FIELDS:
        normalized[field] = _coerce_string(payload.get(field))

    evidence_payload = payload.get("evidence") if isinstance(payload.get("evidence"), dict) else {}
    normalized["evidence"] = {
        field: _coerce_string(evidence_payload.get(field))
        for field in ARCHIVE_FIELDS
    }
    return normalized


def build_agreement_summary(
    rule_fields: dict[str, str],
    llm_fields: dict[str, Any],
) -> dict[str, Any]:
    matched_fields: list[str] = []
    mismatch_fields: list[str] = []
    for field in ARCHIVE_FIELDS:
        if _normalize_compare_value(rule_fields.get(field)) == _normalize_compare_value(llm_fields.get(field)):
            matched_fields.append(field)
        else:
            mismatch_fields.append(field)

    total = len(ARCHIVE_FIELDS)
    matched = len(matched_fields)
    return {
        "matched": matched,
        "total": total,
        "ratio": round(matched / total, 4) if total else 1.0,
        "matched_fields": matched_fields,
        "mismatch_fields": mismatch_fields,
    }


def merge_rule_and_llm_fields(
    rule_fields: dict[str, str],
    llm_fields: dict[str, Any],
    *,
    page_count: int,
) -> tuple[dict[str, str], dict[str, dict[str, str | None]]]:
    recommended = _blank_fields()
    conflicts: dict[str, dict[str, str | None]] = {}

    for field in ARCHIVE_FIELDS:
        rule_value = _coerce_string(rule_fields.get(field))
        llm_value = _coerce_string(llm_fields.get(field))

        if field == "页数":
            recommended[field] = str(page_count) if page_count else (rule_value or llm_value)
            if llm_value and _normalize_compare_value(llm_value) != _normalize_compare_value(recommended[field]):
                conflicts[field] = {
                    "rule": recommended[field],
                    "llm": llm_value,
                    "evidence": _coerce_string((llm_fields.get("evidence") or {}).get(field)),
                }
            continue

        if _normalize_compare_value(rule_value) == _normalize_compare_value(llm_value):
            recommended[field] = rule_value or llm_value
            continue
        if not rule_value and llm_value:
            recommended[field] = llm_value
            continue
        if rule_value and not llm_value:
            recommended[field] = rule_value
            continue

        if field in _MANUAL_REVIEW_FIELDS:
            recommended[field] = ""
            conflicts[field] = {
                "rule": rule_value,
                "llm": llm_value,
                "evidence": _coerce_string((llm_fields.get("evidence") or {}).get(field)),
            }
            continue

        if field in _LLM_PREFERRED_FIELDS:
            recommended[field] = llm_value
        else:
            recommended[field] = rule_value
        conflicts[field] = {
            "rule": rule_value,
            "llm": llm_value,
            "evidence": _coerce_string((llm_fields.get("evidence") or {}).get(field)),
        }

    # Pass through auto-generated fields from rule engine that LLM does not extract
    for key in ("存放路径",):
        if key not in recommended or not recommended[key]:
            rule_val = _coerce_string(rule_fields.get(key))
            if rule_val:
                recommended[key] = rule_val

    return recommended, conflicts


async def call_minimax_field_extraction(
    *,
    filename: str,
    page_count: int,
    full_text: str,
    result_json: Any,
    rule_fields: dict[str, str],
    file_path: str = "",
) -> dict[str, Any]:
    title_candidates = collect_first_page_title_candidates(result_json)
    doc_no_candidates = collect_doc_no_candidates(full_text)
    excerpt_text = build_minimax_input_text(
        full_text,
        title_candidates=title_candidates,
        doc_no_candidates=doc_no_candidates,
        max_chars=MINIMAX_MAX_INPUT_CHARS,
    )
    prompt = _build_prompt(
        filename=filename,
        page_count=page_count,
        rule_fields=rule_fields,
        excerpt_text=excerpt_text,
        file_path=file_path,
    )

    payload = {
        "model": _resolve_llm_runtime_config()["model"],
        "temperature": 0.1,
        "response_format": {"type": "json_object"},
        "messages": [
            {
                "role": "system",
                "content": "你是一个严谨的中文档案归档字段抽取助手，只能输出 JSON。",
            },
            {"role": "user", "content": prompt},
        ],
    }

    response_json = await _post_minimax_chat_completions(
        payload,
        timeout_seconds=_resolve_field_extraction_timeout(
            page_count=page_count,
            excerpt_text=excerpt_text,
        ),
    )
    content = _extract_message_text(response_json)
    llm_fields = normalize_llm_output(_parse_json_object(content))
    return {
        "provider": "minimax",
        "model": response_json.get("model") or _resolve_llm_runtime_config()["model"],
        "raw_usage": response_json.get("usage") or {},
        "llm_fields": llm_fields,
    }


async def call_minimax_same_document_judgement(
    *,
    left_filename: str,
    left_page_count: int,
    left_full_text: str,
    left_rule_fields: dict[str, str],
    right_filename: str,
    right_page_count: int,
    right_full_text: str,
    right_rule_fields: dict[str, str],
) -> dict[str, Any]:
    left_excerpt = build_minimax_input_text(left_full_text, max_chars=max(1200, MINIMAX_MAX_INPUT_CHARS // 4))
    right_excerpt = build_minimax_input_text(right_full_text, max_chars=max(1200, MINIMAX_MAX_INPUT_CHARS // 4))
    prompt = (
        "你是档案文档同一性判断助手。请判断两段 OCR 内容是否属于同一份文档的不同片段（如分册/续页/拆分文件）。\n"
        "只能基于给定内容判断，不得猜测。\n"
        "特别注意：这里的“页数”仅表示当前 OCR 任务片段包含的页数，不代表原始文档总页数。"
        "批量上传 JPG 时，每张图片的页数通常都是 1，这不能作为“不是同一文档”的依据。\n"
        "如果文件名前缀一致且末尾页码连续，应把它视为强线索，再结合题名、正文、表格和证照内容综合判断。\n"
        "预算书封面、预算汇总表、预算表、施工说明、平面图、立面图等标题即使不同，"
        "只要围绕同一工程并呈现连续阅读关系，仍然可能属于同一原始文件的连续页或附页。\n"
        "必须返回 JSON 对象，且仅包含以下字段：same_document, confidence, evidence。\n"
        "same_document 为布尔值；confidence 为 0-1 之间数字；evidence 为简短中文证据。\n\n"
        f"文档A 文件名：{left_filename}\n"
        f"文档A 当前片段页数：{left_page_count}\n"
        f"文档A 规则字段：{json.dumps(left_rule_fields, ensure_ascii=False)}\n"
        f"文档A 摘录：\n{left_excerpt}\n\n"
        f"文档B 文件名：{right_filename}\n"
        f"文档B 当前片段页数：{right_page_count}\n"
        f"文档B 规则字段：{json.dumps(right_rule_fields, ensure_ascii=False)}\n"
        f"文档B 摘录：\n{right_excerpt}\n"
    )
    payload = {
        "model": _resolve_llm_runtime_config()["model"],
        "temperature": 0,
        "response_format": {"type": "json_object"},
        "messages": [
            {
                "role": "system",
                "content": "你是一个严谨的文档同一性判断助手，只能输出 JSON。",
            },
            {"role": "user", "content": prompt},
        ],
    }
    response_json = await _post_minimax_chat_completions(payload)
    content = _extract_message_text(response_json)
    decision = _parse_json_object(content)
    same_document = bool(decision.get("same_document"))
    confidence_raw = decision.get("confidence", 0)
    try:
        confidence = float(confidence_raw)
    except (TypeError, ValueError):
        confidence = 0.0
    confidence = min(1.0, max(0.0, confidence))

    return {
        "provider": "minimax",
        "model": response_json.get("model") or _resolve_llm_runtime_config()["model"],
        "raw_usage": response_json.get("usage") or {},
        "same_document": same_document,
        "confidence": confidence,
        "evidence": _coerce_string(decision.get("evidence")),
    }


def _normalize_report_list(value: Any, *, fallback: str) -> list[str]:
    if isinstance(value, list):
        normalized = [_coerce_string(item) for item in value]
        normalized = [item for item in normalized if item]
        return normalized[:8] if normalized else [fallback]

    single = _coerce_string(value)
    if single:
        return [single]
    return [fallback]


def _normalize_qa_citations(payload: Any, evidence_items: list[dict[str, Any]]) -> list[int]:
    total = len(evidence_items)
    if total <= 0:
        return []

    normalized: list[int] = []
    raw_items: list[Any]
    if isinstance(payload, list):
        raw_items = payload
    elif payload is None:
        raw_items = []
    else:
        raw_items = [payload]

    for raw in raw_items:
        value: int | None = None
        if isinstance(raw, int):
            value = raw
        elif isinstance(raw, float):
            value = int(raw)
        elif isinstance(raw, str):
            match = re.search(r"\d+", raw)
            if match:
                value = int(match.group(0))
        elif isinstance(raw, dict):
            for key in ("index", "evidence_index", "id"):
                entry = raw.get(key)
                if isinstance(entry, int):
                    value = entry
                    break
                if isinstance(entry, str) and entry.isdigit():
                    value = int(entry)
                    break

        if value is None:
            continue
        if value < 1 or value > total:
            continue
        if value not in normalized:
            normalized.append(value)
    return normalized


async def call_minimax_batch_evaluation_report(
    *,
    batch_id: str,
    merge_result: dict[str, Any],
    metrics: dict[str, Any],
) -> dict[str, Any]:
    groups = merge_result.get("groups") or []
    documents = merge_result.get("documents") or []
    operational_metrics = metrics.get("operational_metrics") or {}
    truth_metrics = metrics.get("truth_metrics")

    conflict_samples: list[dict[str, Any]] = []
    for document in documents:
        group_id = _coerce_string(document.get("group_id")) or "unknown-group"
        conflicts = document.get("conflicts") or {}
        for field, payload in conflicts.items():
            if not isinstance(payload, dict):
                continue
            conflict_samples.append(
                {
                    "group_id": group_id,
                    "field": _coerce_string(field),
                    "rule": _coerce_string(payload.get("rule")),
                    "llm": _coerce_string(payload.get("llm")),
                    "evidence": _coerce_string(payload.get("evidence")),
                }
            )
            if len(conflict_samples) >= 12:
                break
        if len(conflict_samples) >= 12:
            break

    prompt_payload = {
        "batch_id": batch_id,
        "summary": merge_result.get("summary") or {},
        "group_count": len(groups),
        "document_count": len(documents),
        "operational_metrics": operational_metrics,
        "truth_metrics": truth_metrics,
        "conflict_samples": conflict_samples,
    }
    prompt = (
        "你是中文档案OCR系统的评测分析助手。请基于输入数据输出简洁、可执行的诊断报告。\n"
        "要求：\n"
        "1) 只能基于给定数据，不要虚构。\n"
        "2) 输出必须是 JSON 对象，不要 Markdown。\n"
        "3) 字段必须包含：summary, strengths, risks, recommendations。\n"
        "4) summary 是 1 段 80~200 字中文总结。\n"
        "5) strengths / risks / recommendations 都是字符串数组，每项一句话，2-6条。\n\n"
        f"输入数据：\n{json.dumps(prompt_payload, ensure_ascii=False)}"
    )

    payload = {
        "model": _resolve_llm_runtime_config()["model"],
        "temperature": 0.2,
        "response_format": {"type": "json_object"},
        "messages": [
            {
                "role": "system",
                "content": "你是严谨的中文数据分析助手，只能输出 JSON。",
            },
            {"role": "user", "content": prompt},
        ],
    }

    response_json = await _post_minimax_chat_completions(payload)
    content = _extract_message_text(response_json)
    report = _parse_json_object(content)

    summary = _coerce_string(report.get("summary"))
    if not summary:
        summary = "当前批次暂无可总结的稳定结论，请先补充样本或真值后重试。"

    return {
        "provider": "minimax",
        "model": response_json.get("model") or _resolve_llm_runtime_config()["model"],
        "raw_usage": response_json.get("usage") or {},
        "summary": summary,
        "strengths": _normalize_report_list(report.get("strengths"), fallback="暂无明显优势信号。"),
        "risks": _normalize_report_list(report.get("risks"), fallback="暂无明显风险信号。"),
        "recommendations": _normalize_report_list(
            report.get("recommendations"),
            fallback="建议继续扩大样本并观察关键字段表现。",
        ),
    }


async def call_minimax_batch_qa_answer(
    *,
    batch_id: str,
    question: str,
    evidence_items: list[dict[str, Any]],
) -> dict[str, Any]:
    indexed_evidence = [{**item, "index": index + 1} for index, item in enumerate(evidence_items)]
    prompt = (
        "你是档案系统的批次知识问答助手。\n"
        "你只能基于给定证据回答，不得使用外部知识，不得猜测。\n"
        "如果证据不足，必须明确回答“无法确认”，并说明缺少哪些关键信息。\n"
        "请只输出 JSON 对象，字段固定为：answer, citations。\n"
        "citations 只允许是证据编号数组（从 1 开始），例如 [1,3]。\n\n"
        f"批次ID：{batch_id}\n"
        f"问题：{question}\n"
        f"证据列表：{json.dumps(indexed_evidence, ensure_ascii=False)}"
    )

    payload = {
        "model": _resolve_llm_runtime_config()["model"],
        "temperature": 0.1,
        "response_format": {"type": "json_object"},
        "messages": [
            {
                "role": "system",
                "content": "你是严谨的知识问答助手，只能基于证据输出 JSON。",
            },
            {"role": "user", "content": prompt},
        ],
    }

    response_json = await _post_minimax_chat_completions(payload)
    content = _extract_message_text(response_json)
    answer_payload = _parse_json_object(content)
    answer = _coerce_string(answer_payload.get("answer"))
    if not answer:
        answer = "无法确认：当前证据不足以给出可靠结论。"
    citations = _normalize_qa_citations(answer_payload.get("citations"), evidence_items)

    return {
        "provider": "minimax",
        "model": response_json.get("model") or _resolve_llm_runtime_config()["model"],
        "raw_usage": response_json.get("usage") or {},
        "answer": answer,
        "citations": citations,
    }


async def call_minimax_batch_qa_support_check(
    *,
    question: str,
    answer: str,
    evidence_items: list[dict[str, Any]],
) -> dict[str, Any]:
    indexed_evidence = [{**item, "index": index + 1} for index, item in enumerate(evidence_items)]
    prompt = (
        "你是问答质量审校助手。请只根据证据判断给定回答是否成立。\n"
        "你只能输出 JSON 对象，字段固定为：support_level, confidence, suggestion。\n"
        "support_level 必须是 supported / partial / insufficient 之一。\n"
        "confidence 必须是 0 到 1 之间的小数。\n"
        "如果证据不足，必须返回 insufficient。\n\n"
        f"问题：{question}\n"
        f"回答：{answer}\n"
        f"证据：{json.dumps(indexed_evidence, ensure_ascii=False)}"
    )

    payload = {
        "model": _resolve_llm_runtime_config()["model"],
        "temperature": 0,
        "response_format": {"type": "json_object"},
        "messages": [
            {
                "role": "system",
                "content": "你是严谨的证据审校助手，只能输出 JSON。",
            },
            {"role": "user", "content": prompt},
        ],
    }

    response_json = await _post_minimax_chat_completions(payload)
    content = _extract_message_text(response_json)
    check_payload = _parse_json_object(content)

    support_level = _coerce_string(check_payload.get("support_level")).lower()
    if support_level not in QA_SUPPORT_LEVELS:
        support_level = "insufficient"

    confidence_raw = check_payload.get("confidence", 0)
    try:
        confidence = float(confidence_raw)
    except (TypeError, ValueError):
        confidence = 0.0
    confidence = min(1.0, max(0.0, confidence))

    return {
        "provider": "minimax",
        "model": response_json.get("model") or _resolve_llm_runtime_config()["model"],
        "raw_usage": response_json.get("usage") or {},
        "support_level": support_level,
        "confidence": confidence,
        "suggestion": _coerce_string(check_payload.get("suggestion")),
    }


async def compare_rule_and_llm_fields_for_content(
    *,
    filename: str,
    page_count: int,
    full_text: str,
    result_json: Any,
    include_evidence: bool = True,
    task_id: int | None = None,
    file_path: str = "",
) -> dict[str, Any]:
    rule_fields = extract_fields(filename, full_text or "", result_json, page_count, file_path=file_path)
    llm_response = await call_minimax_field_extraction(
        filename=filename,
        page_count=page_count,
        full_text=full_text or "",
        result_json=result_json,
        rule_fields=rule_fields,
        file_path=file_path,
    )
    llm_fields = llm_response["llm_fields"]
    recommended_fields, conflicts = merge_rule_and_llm_fields(
        rule_fields,
        llm_fields,
        page_count=page_count,
    )

    response_llm_fields = dict(llm_fields)
    if not include_evidence:
        response_llm_fields.pop("evidence", None)

    payload = {
        "rule_fields": rule_fields,
        "llm_fields": response_llm_fields,
        "recommended_fields": recommended_fields,
        "conflicts": conflicts,
        "agreement": build_agreement_summary(rule_fields, llm_fields),
        "provider": llm_response["provider"],
        "model": llm_response["model"],
        "raw_usage": llm_response["raw_usage"],
    }
    if task_id is not None:
        payload["task_id"] = task_id
    return payload


async def compare_rule_and_llm_fields(task: OCRTask, *, include_evidence: bool = True) -> dict[str, Any]:
    return await compare_rule_and_llm_fields_for_content(
        filename=task.filename,
        page_count=task.page_count,
        full_text=task.full_text or "",
        result_json=task.result_json,
        include_evidence=include_evidence,
        file_path=task.file_path or "",
        task_id=task.id,
    )
