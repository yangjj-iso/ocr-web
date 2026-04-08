"""
OCR 统一门面 — 代理到现有 ocr_engine.py

当前阶段：薄封装，保持与旧代码完全兼容
后续阶段：逐步将 ocr_engine.py 中的各引擎拆分为独立 Provider
"""
from typing import Any


def ocr_document(file_path: str, mode: str = "layout") -> dict[str, Any]:
    """
    对文档执行 OCR 识别（支持图片和 PDF）

    mode:
      - "vl":       PaddleOCR-VL-1.5 视觉语言模型（推荐）
      - "layout":   PP-StructureV3 版面解析（含表格识别）
      - "ocr":      PP-OCRv5 基础文字识别（快速）
      - "baidu_vl": 百度云 API

    Returns:
        {"page_count": int, "pages": list, "full_text": str, "mode": str}
    """
    # 延迟导入避免启动时加载重型 OCR 依赖
    from app.core.ocr_engine import ocr_document as _ocr_document
    return _ocr_document(file_path, mode)
