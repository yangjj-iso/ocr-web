"""
Domain Layer: Field Extraction Operations
领域层：字段提取服务。

架构说明：
这里遵循领域驱动设计 (DDD) 的思想，封装关于“从非结构化文本提取出结构化归档字段”的业务能力。
Application（工作流层）调用这里的方法而不直接调用底层实现（`app.services.excel_export` 这种旧的、带副作用的服务），
以便在未来将规则引擎 (Rule-based) 和 大模型 (LLM-based) 提取方式平滑地重构、演进。
"""

from __future__ import annotations

from app.services import excel_export as legacy_excel_export
from app.services import llm_field_extraction_service as legacy_llm_extraction
from app.shared.contracts import FieldExtractionResult


def extract_fields(filename: str, full_text: str, result_json, page_count: int) -> dict[str, str]:
    raw_fields = legacy_excel_export.extract_fields(filename, full_text, result_json, page_count)
    return {str(key): str(value or "") for key, value in (raw_fields or {}).items()}


def build_field_extraction_result(fields: dict[str, str]) -> FieldExtractionResult:
    review_recommendation = {
        key: "review" if not str(value or "").strip() else "accepted"
        for key, value in fields.items()
    }
    return FieldExtractionResult(
        fields=fields,
        confidence={},
        review_recommendation=review_recommendation,
    )


async def compare_rule_and_llm_fields(task, *, include_evidence: bool = True) -> dict:
    return await legacy_llm_extraction.compare_rule_and_llm_fields(task, include_evidence=include_evidence)


__all__ = ["build_field_extraction_result", "compare_rule_and_llm_fields", "extract_fields"]
