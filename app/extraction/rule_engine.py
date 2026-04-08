"""
规则引擎 — 基于正则/关键词的字段提取

从 excel_export.py 中提取的纯业务逻辑，不包含 Excel I/O。
现有代码通过 excel_export.extract_fields() 调用此处逻辑。
"""
from typing import Any


def extract_fields_by_rules(
    filename: str,
    full_text: str,
    result_json: Any,
    page_count: int,
) -> dict[str, str]:
    """
    使用基于正则和关键字规则的启发式方法，从 OCR 识别结果中抽取核心归档字段。
    
    之所以保留此模块，是为了在不依赖大模型（LLM）的场景下，提供一套快速、确定性的提取降级方案。
    这些规则通常针对特定的公文/档案格式（如发文机关、红头文件格式等）高度硬编码。

    Args:
        filename (str): 上传的原始文件名。常用于从中利用正则直接提取“档号”（如 WS·2023·A1-1）。
        full_text (str): OCR 提取的全文纯文本，用于简单的关键字/正则全局搜索。
        result_json (Any): 结构化的 OCR 结果（包含 bounding box 等版面信息），用于基于位置的高级推断（如：顶部的居中文本更可能是标题）。
        page_count (int): 文档总页数。

    Returns:
        dict[str, str]: 标准化提取结果，至少包含 {"档号": "...", "文号": "...", "责任者": "...", "题名": "...", "日期": "...", "密级": "..."}
    """
    # 委托到现有的业务逻辑模块执行提取，保持对旧版调用的向后兼容性。
    # 避免在此处重复实现繁杂的正则解析逻辑。
    from app.services.excel_export import extract_fields
    return extract_fields(filename, full_text, result_json, page_count)
