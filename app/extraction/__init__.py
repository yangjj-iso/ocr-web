"""
字段提取领域 — 规则引擎与 AI 引擎分离

使用方式:
    from app.extraction import extract_fields_by_rules
    fields = extract_fields_by_rules(filename, full_text, result_json, page_count)
"""
from app.extraction.rule_engine import extract_fields_by_rules  # noqa: F401
