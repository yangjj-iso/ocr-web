"""
OCR 领域包 — 统一入口

使用方式:
    from app.ocr import ocr_document
    result = ocr_document(file_path, mode="vl")

支持的 mode:
    - "vl":       PaddleOCR-VL-1.5 视觉语言模型
    - "layout":   PP-StructureV3 版面解析
    - "ocr":      PP-OCRv5 基础文字识别
    - "baidu_vl": 百度云 API
"""
from app.ocr.facade import ocr_document  # noqa: F401
