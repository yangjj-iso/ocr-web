"""
字段比对器 — 规则提取 vs LLM 提取结果比对

从 llm_field_extraction_service.py 中提取的比对逻辑。
"""
from typing import Any

from app.services.llm_field_extraction_service import (
    build_agreement_summary,
    merge_rule_and_llm_fields,
)


def compare_fields(
    rule_fields: dict[str, str],
    llm_fields: dict[str, Any],
    *,
    page_count: int,
) -> dict[str, Any]:
    """
    比对规则提取与 LLM 提取结果

    Returns:
        {
            "recommended_fields": {...},
            "conflicts": {...},
            "agreement": {...},
        }
    """
    recommended, conflicts = merge_rule_and_llm_fields(
        rule_fields, llm_fields, page_count=page_count,
    )
    agreement = build_agreement_summary(rule_fields, llm_fields)
    return {
        "recommended_fields": recommended,
        "conflicts": conflicts,
        "agreement": agreement,
    }
