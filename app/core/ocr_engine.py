import base64
import logging
import re
import tempfile
import time
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

try:
    import ml_dtypes as _ml_dtypes  # noqa: F401
except ImportError:  # pragma: no cover - environment dependent
    _ml_dtypes = None

try:
    import cv2
except ImportError:  # pragma: no cover - environment dependent
    cv2 = None

try:
    import numpy as np
except ImportError:  # pragma: no cover - environment dependent
    np = None

try:
    from paddleocr import PaddleOCR
except ImportError:  # pragma: no cover - environment dependent
    PaddleOCR = Any

try:
    import fitz  # type: ignore[import-not-found]
except ImportError:  # pragma: no cover - environment dependent
    fitz = None

try:
    import httpx
except ImportError:  # pragma: no cover - environment dependent
    httpx = None

# 图片最大像素面积限制（长×宽），超过则等比缩放
MAX_IMAGE_PIXELS = 2500 * 2500
STRUCTURED_MAX_IMAGE_PIXELS = 5000 * 5000

from app.core.result_validation import normalize_table_data, table_data_to_text, table_html_to_data
from config import (
    BAIDU_API_KEY,
    BAIDU_SECRET_KEY,
    OCR_DEVICE,
    OCR_LANG,
    OCR_LAYOUT_API_TIMEOUT_SECONDS,
    OCR_LAYOUT_API_TOKEN,
    OCR_LAYOUT_API_URL,
    OCR_LAYOUT_API_USE_CHART_RECOGNITION,
    OCR_LAYOUT_API_USE_DOC_ORIENTATION_CLASSIFY,
    OCR_LAYOUT_API_USE_DOC_UNWARPING,
    OCR_LAYOUT_BACKEND,
    OCR_VL_BACKEND,
    UPLOAD_DIR,
)


def _cv_imread(path: str):
    """读取图片（支持中文路径）"""
    _require_cv_stack()
    data = np.fromfile(path, dtype=np.uint8)
    return cv2.imdecode(data, cv2.IMREAD_COLOR)


def _cv_imwrite(path: str, img):
    """保存图片（支持中文路径）"""
    _require_cv_stack()
    ext = Path(path).suffix or '.jpg'
    ok, buf = cv2.imencode(ext, img)
    if ok:
        buf.tofile(path)

logger = logging.getLogger(__name__)

# ===== 多模型管理 =====
_ocr_instance = None
_layout_pipeline = None
_vl_pipeline = None
_paddle_bfloat16_patch_applied = False
_UNSUPPORTED_PREDICT_ARG_RE = re.compile(r"unexpected keyword argument ['\"](?P<name>\w+)['\"]")
_MISSING_DOC_PREPROCESSOR_RE = re.compile(r"doc_preprocessor_pipeline")


def _patch_paddle_bfloat16_tensor_loading() -> None:
    global _paddle_bfloat16_patch_applied
    if _paddle_bfloat16_patch_applied or np is None:
        return

    try:
        import paddle as _paddle
        import paddle.tensor.creation as _paddle_creation
    except Exception:
        return

    original_to_tensor = getattr(_paddle, "to_tensor", None)
    if original_to_tensor is None:
        return

    def _patched_to_tensor(data, dtype=None, place=None, stop_gradient=True):
        data_dtype = getattr(data, "dtype", None)
        if str(data_dtype) == "bfloat16":
            tensor = original_to_tensor(
                np.asarray(data, dtype=np.float32),
                dtype="float32",
                place=place,
                stop_gradient=stop_gradient,
            )
            if dtype in (None, "bfloat16", getattr(_paddle, "bfloat16", None)):
                return tensor.astype("bfloat16")
            if dtype in ("float32", getattr(_paddle, "float32", None)):
                return tensor
            return tensor.astype(dtype)

        return original_to_tensor(data, dtype=dtype, place=place, stop_gradient=stop_gradient)

    _paddle.to_tensor = _patched_to_tensor
    _paddle_creation.to_tensor = _patched_to_tensor
    _paddle_bfloat16_patch_applied = True


def _pipeline_has_doc_preprocessor(pipeline) -> bool:
    if not hasattr(pipeline, "doc_preprocessor_pipeline"):
        return False
    try:
        return getattr(pipeline, "doc_preprocessor_pipeline") is not None
    except Exception:
        return False


def _structured_predict_kwargs(pipeline, profile: str) -> dict[str, Any]:
    if profile == "vl":
        return {}

    kwargs: dict[str, Any] = {
        "use_doc_orientation_classify": True,
        "use_doc_unwarping": True,
        "use_table_recognition": True,
        "use_seal_recognition": True,
        "layout_shape_mode": "poly",
        "layout_merge_bboxes_mode": "union",
        "format_block_content": True,
    }

    if not _pipeline_has_doc_preprocessor(pipeline):
        disabled = []
        for arg_name in ("use_doc_orientation_classify", "use_doc_unwarping"):
            if arg_name in kwargs:
                kwargs.pop(arg_name)
                disabled.append(arg_name)
        if disabled:
            logger.info(
                "当前管线未初始化 doc_preprocessor_pipeline，预测前跳过 %s。",
                ", ".join(disabled),
            )

    return kwargs


def _require_fitz():
    if fitz is None:
        raise RuntimeError("PyMuPDF is required to process PDF files. Install PyMuPDF>=1.24.0.")
    return fitz


def _require_cv_stack():
    if cv2 is None or np is None:
        raise RuntimeError("OpenCV and NumPy are required to process images.")


def _require_paddleocr():
    if PaddleOCR is Any:
        raise RuntimeError("paddleocr is required to run OCR. Install paddleocr>=3.0.0.")


def _can_use_baidu_document_api() -> bool:
    return bool(str(BAIDU_API_KEY or "").strip() and str(BAIDU_SECRET_KEY or "").strip())


def _should_use_baidu_vl_backend(mode: str) -> bool:
    if mode == "baidu_vl":
        return True
    if mode != "vl":
        return False
    if OCR_VL_BACKEND == "local":
        return False
    if OCR_VL_BACKEND == "baidu":
        return True
    return _can_use_baidu_document_api()


def _can_use_layout_api() -> bool:
    return bool(OCR_LAYOUT_API_URL and OCR_LAYOUT_API_TOKEN)


def _should_use_layout_api(mode: str) -> bool:
    if not _can_use_layout_api():
        return False
    if mode == "ocr":
        return OCR_LAYOUT_BACKEND == "api"
    if mode == "layout":
        return OCR_LAYOUT_BACKEND == "api"
    if mode == "vl":
        if OCR_VL_BACKEND == "api":
            return True
        if OCR_VL_BACKEND == "auto":
            return OCR_LAYOUT_BACKEND == "api"
    return False


def should_require_local_vl_runtime(mode: str) -> bool:
    return mode == "vl" and not _should_use_baidu_vl_backend(mode) and not _should_use_layout_api(mode)


def uses_shared_layout_api_for_ocr_and_vl() -> bool:
    """Whether OCR and VL routes currently hit the same remote layout API."""
    return _should_use_layout_api("ocr") and _should_use_layout_api("vl")


def _is_known_layout_runtime_error(exc: Exception) -> bool:
    message = str(exc)
    return any(
        token in message
        for token in (
            "warpPerspective",
            "Expected Ptr<cv::UMat>",
            "Overload resolution failed",
            "Conversion error: src",
        )
    )


def get_ocr() -> PaddleOCR:
    """获取 PP-OCRv5 基础 OCR 单例（快速文字识别，无版面分析）"""
    global _ocr_instance
    if _ocr_instance is None:
        _require_paddleocr()
        logger.info("正在初始化 PP-OCRv5 引擎 (lang=%s, device=%s)...", OCR_LANG, OCR_DEVICE)
        # PP-OCRv5 server 模型在 PaddlePaddle 3.3.0 CPU 下有 PIR/oneDNN Bug
        # 当 device=cpu 时改用 mobile 模型，避免 ConvertPirAttribute2RuntimeAttribute 报错
        use_mobile = (OCR_DEVICE == "cpu")
        _ocr_instance = PaddleOCR(
            lang=OCR_LANG,
            use_doc_orientation_classify=False,
            use_doc_unwarping=False,
            use_textline_orientation=False,
            device=OCR_DEVICE,
            text_detection_model_name="PP-OCRv5_mobile_det" if use_mobile else None,
            text_recognition_model_name="PP-OCRv5_mobile_rec" if use_mobile else None,
        )
        logger.info("PP-OCRv5 引擎初始化完成")
    return _ocr_instance


def get_layout_pipeline():
    """获取 PP-StructureV3 版面解析管线单例（含 OCR + 表格识别 + 版面分析）"""
    global _layout_pipeline
    if _layout_pipeline is None:
        from paddlex import create_pipeline
        logger.info("正在初始化 PP-StructureV3 版面解析管线 (device=%s)...", OCR_DEVICE)
        _layout_pipeline = create_pipeline(
            pipeline="layout_parsing",
            device=OCR_DEVICE,
        )
        logger.info("PP-StructureV3 版面解析管线初始化完成")
    return _layout_pipeline


def _maybe_resize_image(image_path: str, max_pixels: int | None = MAX_IMAGE_PIXELS) -> str:
    """如果图片过大，等比缩放后保存到临时文件，返回新路径；否则返回原路径"""
    try:
        if not max_pixels or max_pixels <= 0:
            return image_path
        img = _cv_imread(image_path)
        if img is None:
            return image_path
        h, w = img.shape[:2]
        pixels = h * w
        if pixels <= max_pixels:
            del img
            return image_path
        scale = (max_pixels / pixels) ** 0.5
        new_w = int(w * scale)
        new_h = int(h * scale)
        logger.info("缩放大图: %s (%dx%d -> %dx%d, %.0f%%)", Path(image_path).name, w, h, new_w, new_h, scale * 100)
        resized = cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_AREA)
        # 保存到 uploads 目录（纯 ASCII 路径，避免中文路径问题）
        suffix = Path(image_path).suffix or '.jpg'
        tmp = tempfile.NamedTemporaryFile(suffix=suffix, delete=False, dir=str(UPLOAD_DIR))
        tmp.close()
        _cv_imwrite(tmp.name, resized)
        del img, resized
        return tmp.name
    except Exception as e:
        logger.warning("图片缩放失败 %s: %s", image_path, e)
        return image_path


def _poly_to_list(poly) -> list[list[float]]:
    if hasattr(poly, "tolist"):
        poly = poly.tolist()
    if not poly:
        return []

    points: list[list[float]] = []

    def _walk(node):
        if hasattr(node, "tolist"):
            node = node.tolist()
        if isinstance(node, dict):
            if "x" in node and "y" in node:
                points.append([_safe_float(node.get("x")), _safe_float(node.get("y"))])
                return
            for child in node.values():
                _walk(child)
            return
        if isinstance(node, (list, tuple)):
            if (
                len(node) >= 2
                and not isinstance(node[0], (list, tuple, dict))
                and not isinstance(node[1], (list, tuple, dict))
            ):
                points.append([_safe_float(node[0]), _safe_float(node[1])])
                return
            for child in node:
                _walk(child)

    _walk(poly)
    return points


def _item_polygon_points(item, attr_name: str = "polygon_points", dict_key: str = "block_polygon_points") -> list[list[float]]:
    if hasattr(item, attr_name):
        return _poly_to_list(getattr(item, attr_name))
    if isinstance(item, dict):
        return _poly_to_list(item.get(dict_key))
    return []


def _item_value(item, *names: str):
    for name in names:
        if hasattr(item, name):
            value = getattr(item, name)
            if value is not None:
                # Convert numpy arrays to lists so that "value or []" works safely downstream.
                if hasattr(value, "tolist"):
                    value = value.tolist()
                    # Empty numpy arrays (len==0) should be treated as missing → continue.
                    if not value:
                        continue
                return value
        if isinstance(item, dict) and name in item:
            value = item.get(name)
            if value is not None:
                if hasattr(value, "tolist"):
                    value = value.tolist()
                    if not value:
                        continue
                return value
    return None


def _coerce_layout_bbox(bbox_raw, poly_pts: list[list[float]] | None = None) -> tuple[list[float], list[list[float]]]:
    if hasattr(bbox_raw, "tolist"):
        bbox_raw = bbox_raw.tolist()
    poly = poly_pts or []
    if isinstance(bbox_raw, list) and bbox_raw and isinstance(bbox_raw[0], (list, tuple)):
        raw_poly = _poly_to_list(bbox_raw)
        if raw_poly and not poly:
            poly = raw_poly
        return (_rect_from_polys([raw_poly]) if raw_poly else []), poly
    if isinstance(bbox_raw, (list, tuple)) and len(bbox_raw) >= 4:
        bbox = [_safe_float(x) for x in bbox_raw[:4]]
        if bbox[2] <= bbox[0] or bbox[3] <= bbox[1]:
            return [], poly
        return bbox, poly
    return [], poly


def _looks_like_html_table(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    lowered = value.lower()
    return "<table" in lowered or ("<tr" in lowered and ("<td" in lowered or "<th" in lowered))


def _looks_like_markdown_table(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    lines = [line.strip() for line in value.splitlines() if line.strip()]
    if len(lines) < 2:
        return False
    pipe_lines = [line for line in lines if line.count("|") >= 2]
    if len(pipe_lines) < 2:
        return False
    divider = pipe_lines[1].replace("|", "").replace(":", "").replace("-", "").replace(" ", "")
    return divider == ""


def _has_table_content(table_data: list[list[str]] | None) -> bool:
    return bool(table_data) and any(str(cell).strip() for row in table_data for cell in row)


def _normalize_table_payload(raw_table) -> list[list[str]] | None:
    if raw_table is None:
        return None
    try:
        table_data = normalize_table_data(raw_table)
    except Exception:
        return None
    return table_data if _has_table_content(table_data) else None


def _markdown_table_to_data(value: Any) -> list[list[str]] | None:
    if not _looks_like_markdown_table(value):
        return None
    lines = [line.strip() for line in str(value).splitlines() if line.strip() and line.count("|") >= 1]
    rows = []
    for index, line in enumerate(lines):
        stripped = line.strip()
        divider = stripped.replace("|", "").replace(":", "").replace("-", "").replace(" ", "")
        if index == 1 and divider == "":
            continue
        if stripped.startswith("|"):
            stripped = stripped[1:]
        if stripped.endswith("|"):
            stripped = stripped[:-1]
        rows.append([cell.strip() for cell in stripped.split("|")])
    return _normalize_table_payload(rows)


def _plain_text_table_to_data(value: Any) -> list[list[str]] | None:
    if not isinstance(value, str):
        return None
    lines = [line.strip() for line in value.splitlines() if line.strip()]
    if len(lines) < 2:
        return None
    rows = []
    max_cols = 0
    for line in lines:
        if "\t" in line:
            cells = [cell.strip() for cell in line.split("\t")]
        else:
            cells = [cell.strip() for cell in re.split(r"\s{2,}", line) if cell.strip()]
        if len(cells) < 2:
            return None
        rows.append(cells)
        max_cols = max(max_cols, len(cells))
    padded_rows = [row + [""] * (max_cols - len(row)) for row in rows]
    return _normalize_table_payload(padded_rows)


def _extract_table_payload(item, label: str, content: str) -> tuple[list[list[str]] | None, str | None, str]:
    raw_label = str(label or "").strip().lower()
    table_data = _normalize_table_payload(_item_value(item, "table_data", "block_table_data", "cells"))
    html = _item_value(item, "html", "block_html", "table_html")
    markdown = _item_value(item, "markdown", "block_markdown", "table_markdown")

    nested = _item_value(item, "res", "result", "block_result", "table_result")
    if isinstance(nested, dict):
        if table_data is None:
            table_data = _normalize_table_payload(nested.get("table_data") or nested.get("cells"))
        if html is None:
            html = nested.get("html") or nested.get("table_html")
        if markdown is None:
            markdown = nested.get("markdown") or nested.get("table_markdown")

    if table_data is None and isinstance(content, str):
        if _looks_like_html_table(content):
            html = content
        elif _looks_like_markdown_table(content):
            markdown = content
        elif raw_label in {"table", "table_body"}:
            table_data = _plain_text_table_to_data(content)

    if table_data is None and isinstance(html, str) and _looks_like_html_table(html):
        try:
            table_data = _normalize_table_payload(table_html_to_data(html))
        except Exception:
            table_data = None

    if table_data is None and isinstance(markdown, str) and markdown.strip():
        table_data = _markdown_table_to_data(markdown)

    table_content = str(content or "")
    if table_data is not None:
        table_content = table_data_to_text(table_data)
    elif isinstance(markdown, str) and markdown.strip():
        table_content = markdown.strip()

    html_value = html.strip() if isinstance(html, str) and _looks_like_html_table(html) else None
    return table_data, html_value, table_content


def _canonical_region_type(label: Any, has_table_payload: bool = False) -> str:
    lowered = str(label or "text").strip().lower()
    if has_table_payload or lowered in {"table", "table_body"}:
        return "table"
    if "seal" in lowered or "stamp" in lowered:
        return "seal"
    return lowered or "text"


def _compact_text(value: Any) -> str:
    return re.sub(r"\s+", "", str(value or ""))


def _rect_contains_point(rect: list[float], x: float, y: float) -> bool:
    return len(rect) >= 4 and rect[0] <= x <= rect[2] and rect[1] <= y <= rect[3]


def _rect_from_polys(polys: list[list[list[float]]]) -> list[float]:
    xs = [pt[0] for poly in polys for pt in poly]
    ys = [pt[1] for poly in polys for pt in poly]
    if not xs or not ys:
        return []
    return [min(xs), min(ys), max(xs), max(ys)]


def _rect_area(rect: list[float]) -> float:
    if len(rect) < 4:
        return 0.0
    return max(0.0, rect[2] - rect[0]) * max(0.0, rect[3] - rect[1])


def _rect_intersection_area(a: list[float], b: list[float]) -> float:
    if len(a) < 4 or len(b) < 4:
        return 0.0
    x1 = max(a[0], b[0])
    y1 = max(a[1], b[1])
    x2 = min(a[2], b[2])
    y2 = min(a[3], b[3])
    return max(0.0, x2 - x1) * max(0.0, y2 - y1)


def _line_rect(line: dict) -> list[float]:
    bbox = line.get("bbox") or []
    if bbox and isinstance(bbox[0], list):
        return _rect_from_polys([bbox])
    if len(bbox) >= 4:
        return [float(bbox[0]), float(bbox[1]), float(bbox[2]), float(bbox[3])]
    return []


def _line_center(poly: list[list[float]]) -> tuple[float, float]:
    if not poly:
        return 0.0, 0.0
    return (
        sum(point[0] for point in poly) / len(poly),
        sum(point[1] for point in poly) / len(poly),
    )


def _line_sort_key(line: dict) -> tuple[float, float, int]:
    rect = _line_rect(line)
    line_num = int(line.get("line_num") or 0)
    y = rect[1] if len(rect) >= 4 else 0.0
    x = rect[0] if len(rect) >= 4 else 0.0
    return y, x, line_num


def _copy_line_payload(line: dict) -> dict:
    bbox = line.get("bbox") or []
    copied_bbox = [point[:] for point in bbox] if bbox and isinstance(bbox[0], list) else list(bbox)
    confidence = line.get("confidence", 0.0)
    try:
        confidence_value = float(confidence)
    except (TypeError, ValueError):
        confidence_value = 0.0
    return {
        "line_num": int(line.get("line_num") or 0),
        "text": str(line.get("text") or ""),
        "confidence": round(confidence_value, 4),
        "bbox": copied_bbox,
        "bbox_type": "poly" if copied_bbox and isinstance(copied_bbox[0], list) else "rect",
    }


def _is_textual_region(label: str) -> bool:
    return label not in {"table", "figure", "image", "chart", "seal"}


def _collect_region_lines(label: str, bbox: list[float], content: str, page_lines: list[dict]) -> list[dict]:
    if len(bbox) < 4 or not _is_textual_region(label) or not page_lines:
        return []

    content_norm = _compact_text(content)
    candidates = []
    for line in page_lines:
        text = str(line.get("text") or "").strip()
        poly = line.get("bbox") or []
        if not text or not poly or not isinstance(poly[0], list):
            continue
        line_rect = _line_rect(line)
        if len(line_rect) < 4:
            continue
        cx, cy = _line_center(poly)
        overlap_ratio = _rect_intersection_area(bbox, line_rect) / (_rect_area(line_rect) or 1.0)
        if _rect_contains_point(bbox, cx, cy) or overlap_ratio >= 0.26:
            candidates.append((line, overlap_ratio))

    if not candidates:
        return []

    matched = []
    if content_norm:
        for line, overlap_ratio in candidates:
            line_norm = _compact_text(line.get("text"))
            if not line_norm:
                continue
            if line_norm in content_norm or content_norm in line_norm or _text_similarity(content_norm, line_norm) >= 0.72:
                matched.append((line, overlap_ratio))

    if matched:
        if len(content_norm) <= 32:
            matched.sort(
                key=lambda item: (_text_similarity(content_norm, _compact_text(item[0].get("text"))), item[1]),
                reverse=True,
            )
            chosen_lines = [matched[0][0]]
        else:
            chosen_lines = [item[0] for item in matched]
    else:
        fallback = [line for line, overlap_ratio in candidates if overlap_ratio >= 0.45]
        if fallback:
            chosen_lines = fallback
        elif len(content_norm) <= 32:
            candidates.sort(key=lambda item: item[1], reverse=True)
            chosen_lines = [candidates[0][0]]
        else:
            chosen_lines = [item[0] for item in candidates]

    seen = set()
    output = []
    for line in sorted(chosen_lines, key=_line_sort_key):
        rect = _line_rect(line)
        key = (
            int(line.get("line_num") or 0),
            _compact_text(line.get("text")),
            tuple(round(value, 1) for value in rect),
        )
        if key in seen:
            continue
        seen.add(key)
        output.append(_copy_line_payload(line))
    return output


def _normalize_seal_content(value: Any) -> str:
    lines = [line.strip() for line in str(value or "").splitlines() if line.strip()]
    if not lines:
        return ""
    joined = "\n".join(lines)
    if len(lines) > 4:
        return ""
    if len(joined) > 48 and re.search(r"[，。；、]", joined):
        return ""
    return joined


def _seal_candidate_score(value: Any) -> float:
    normalized = _normalize_seal_content(value)
    if not normalized:
        return -1.0

    compact = _compact_text(normalized)
    lines = [line for line in normalized.splitlines() if line.strip()]
    score = min(len(compact), 24) / 12
    if 1 <= len(lines) <= 3:
        score += 0.6
    elif len(lines) == 4:
        score += 0.3
    if re.search(r"(章|印|公司|专用|合同|财务|法人|有限|委员会|办公室)", normalized):
        score += 0.8
    if re.search(r"\d{6,}", compact):
        score += 0.35
    if any(len(_compact_text(line)) > 18 for line in lines):
        score -= 0.35
    if len(compact) > 36:
        score -= 0.45
    if re.search(r"[，。；、,.;!?]", normalized):
        score -= 0.65
    return score


def _choose_best_seal_content(raw_content: str, line_content: str) -> str:
    raw_candidate = _normalize_seal_content(raw_content)
    line_candidate = _normalize_seal_content(line_content)
    if not raw_candidate:
        return line_candidate
    if not line_candidate:
        return raw_candidate
    raw_score = _seal_candidate_score(raw_candidate)
    line_score = _seal_candidate_score(line_candidate)
    if line_score > raw_score + 0.2:
        return line_candidate
    return raw_candidate


def _seal_content_from_lines(layout_bbox: list[float], page_lines: list[dict], raw_content: str = "") -> str:
    raw_candidate = _normalize_seal_content(raw_content)
    if len(layout_bbox) < 4 or not page_lines:
        return raw_candidate

    seal_width = max(0.0, layout_bbox[2] - layout_bbox[0])
    seal_height = max(0.0, layout_bbox[3] - layout_bbox[1])
    candidates = []
    for line in page_lines:
        text = str(line.get("text") or "").strip()
        poly = line.get("bbox") or []
        if not text or not poly or not isinstance(poly[0], list):
            continue
        line_rect = _line_rect(line)
        if len(line_rect) < 4:
            continue
        cx, cy = _line_center(poly)
        overlap_ratio = _rect_intersection_area(layout_bbox, line_rect) / (_rect_area(line_rect) or 1.0)
        if _rect_contains_point(layout_bbox, cx, cy) or overlap_ratio >= 0.26:
            candidates.append((text, overlap_ratio, line_rect))

    if not candidates:
        return raw_candidate

    candidates.sort(key=lambda item: item[1], reverse=True)
    seen = set()
    selected = []
    for text, _, line_rect in candidates:
        normalized = _compact_text(text)
        if not normalized or normalized in seen:
            continue
        line_width = max(0.0, line_rect[2] - line_rect[0])
        line_height = max(0.0, line_rect[3] - line_rect[1])
        if line_width and seal_width and line_width > seal_width * 1.2 and len(normalized) > 12:
            continue
        if line_height and seal_height and line_height > seal_height * 0.65 and len(normalized) > 16:
            continue
        if len(normalized) > 28:
            continue
        if len(normalized) > 18 and re.search(r"[，。；、]", text):
            continue
        seen.add(normalized)
        selected.append(text)
        if len(selected) >= 4:
            break

    line_candidate = "\n".join(selected)
    return _choose_best_seal_content(raw_candidate, line_candidate)


def _region_rect(region: dict) -> list[float]:
    layout_bbox = region.get("layout_bbox") or []
    if len(layout_bbox) >= 4:
        return [float(layout_bbox[0]), float(layout_bbox[1]), float(layout_bbox[2]), float(layout_bbox[3])]
    bbox = region.get("bbox") or []
    if bbox and isinstance(bbox[0], list):
        return _rect_from_polys([bbox])
    if len(bbox) >= 4:
        return [float(bbox[0]), float(bbox[1]), float(bbox[2]), float(bbox[3])]
    return []


def _overlap_on_smaller(a: list[float], b: list[float]) -> float:
    denominator = min(_rect_area(a), _rect_area(b))
    if denominator <= 0:
        return 0.0
    return _rect_intersection_area(a, b) / denominator


def _merge_seal_regions(
    page: dict[str, Any],
    seal_regions: list[dict[str, Any]],
    *,
    detector_name: str | None = None,
) -> dict[str, Any]:
    page.setdefault("regions", [])
    page.setdefault("lines", [])
    if not seal_regions:
        return page

    regions = list(page.get("regions") or [])
    added_count = 0
    for detected in seal_regions:
        if str(detected.get("type") or "").strip().lower() != "seal":
            continue

        detected_rect = _region_rect(detected)
        matched_region = next(
            (
                region
                for region in regions
                if str(region.get("type") or "").strip().lower() == "seal"
                and _overlap_on_smaller(detected_rect, _region_rect(region)) >= 0.55
            ),
            None,
        )

        if matched_region is None:
            regions.append(detected)
            added_count += 1
            continue

        detected_meta = dict(detected.get("agent_meta") or {})
        existing_meta = dict(matched_region.get("agent_meta") or {})
        if detected_meta:
            existing_meta.update({key: value for key, value in detected_meta.items() if key not in existing_meta})
            matched_region["agent_meta"] = existing_meta

        best_content = _choose_best_seal_content(
            str(matched_region.get("content") or ""),
            str(detected.get("content") or ""),
        )
        if best_content:
            matched_region["content"] = best_content
        if not matched_region.get("bbox") and detected.get("bbox"):
            matched_region["bbox"] = detected["bbox"]
            matched_region["bbox_type"] = detected.get("bbox_type", "rect")
        if not matched_region.get("layout_bbox") and detected.get("layout_bbox"):
            matched_region["layout_bbox"] = detected["layout_bbox"]
        if not matched_region.get("region_lines") and detected.get("region_lines"):
            matched_region["region_lines"] = detected["region_lines"]

    page["regions"] = _filter_output_regions(regions)
    page_meta = dict(page.get("agent_meta") or {})
    page_meta["seal_region_count"] = sum(
        1 for region in page["regions"] if str(region.get("type") or "").strip().lower() == "seal"
    )
    if detector_name and added_count:
        page_meta["seal_detector"] = detector_name
    if page_meta:
        page["agent_meta"] = page_meta
    return page


def _table_text_from_region(region: dict) -> str:
    table_data = _normalize_table_payload(region.get("table_data"))
    html = region.get("html")
    if table_data is None and isinstance(html, str) and _looks_like_html_table(html):
        try:
            table_data = _normalize_table_payload(table_html_to_data(html))
        except Exception:
            table_data = None
    if table_data is not None:
        return _compact_text(table_data_to_text(table_data))
    return _compact_text(region.get("content"))


def _table_region_score(region: dict) -> float:
    score = 0.0
    table_data = _normalize_table_payload(region.get("table_data"))
    html = region.get("html")
    if table_data is None and isinstance(html, str) and _looks_like_html_table(html):
        try:
            table_data = _normalize_table_payload(table_html_to_data(html))
        except Exception:
            table_data = None
    if table_data is not None:
        non_empty = sum(1 for row in table_data for cell in row if str(cell).strip())
        score += min(non_empty, 60) * 0.12
        score += min(len(table_data), 20) * 0.08
        score += min(max((len(row) for row in table_data), default=0), 12) * 0.14
    if isinstance(html, str) and _looks_like_html_table(html):
        score += 1.5
    score += min(len(_table_text_from_region(region)), 180) / 90
    return score


def _table_regions_look_duplicated(region: dict, other: dict) -> bool:
    overlap_ratio = _overlap_on_smaller(_region_rect(region), _region_rect(other))
    if overlap_ratio >= 0.92:
        return True

    region_text = _table_text_from_region(region)
    other_text = _table_text_from_region(other)
    if overlap_ratio >= 0.72:
        if not region_text or not other_text:
            return True
        if region_text in other_text or other_text in region_text:
            return True
        if _text_similarity(region_text, other_text) >= 0.88:
            return True

    if overlap_ratio >= 0.58 and region_text and other_text and _text_similarity(region_text, other_text) >= 0.96:
        return True

    return False


def _filter_output_regions(regions: list[dict]) -> list[dict]:
    if not regions:
        return regions

    kept = []
    kept_tables: list[dict[str, Any]] = []
    for region in regions:
        region_type = str(region.get("type") or "text")
        region_rect = _region_rect(region)
        region_text = _compact_text(region.get("content"))

        if region_type == "table":
            duplicate_index = next(
                (index for index, table in enumerate(kept_tables) if _table_regions_look_duplicated(region, table["region"])),
                None,
            )
            if duplicate_index is not None:
                candidate_score = _table_region_score(region)
                if candidate_score > kept_tables[duplicate_index]["score"]:
                    kept_index = kept_tables[duplicate_index]["index"]
                    kept[kept_index] = region
                    kept_tables[duplicate_index] = {
                        "region": region,
                        "rect": region_rect,
                        "text": _table_text_from_region(region),
                        "score": candidate_score,
                        "index": kept_index,
                    }
                continue

            kept.append(region)
            kept_tables.append(
                {
                    "region": region,
                    "rect": region_rect,
                    "text": _table_text_from_region(region),
                    "score": _table_region_score(region),
                    "index": len(kept) - 1,
                }
            )
            continue

        if region_type in {"text", "paragraph", "number"} and region_text:
            covered_by_table = any(
                _overlap_on_smaller(region_rect, table["rect"]) >= 0.88
                and (
                    not table["text"]
                    or region_text in table["text"]
                    or table["text"] in region_text
                )
                for table in kept_tables
            )
            if covered_by_table:
                continue

        kept.append(region)

    return kept


def _expand_rect(rect: list[float], width: int, height: int, padding_ratio: float = 0.08) -> list[float]:
    if len(rect) < 4:
        return []
    rect_width = max(0.0, rect[2] - rect[0])
    rect_height = max(0.0, rect[3] - rect[1])
    padding_x = max(6.0, rect_width * padding_ratio)
    padding_y = max(6.0, rect_height * padding_ratio)
    return [
        max(0.0, rect[0] - padding_x),
        max(0.0, rect[1] - padding_y),
        min(float(width), rect[2] + padding_x),
        min(float(height), rect[3] + padding_y),
    ]


def _detect_red_seal_regions(image_path: str, *, page_lines: list[dict] | None = None) -> list[dict]:
    if cv2 is None or np is None:
        return []

    try:
        image = _cv_imread(image_path)
    except Exception:
        logger.debug("印章颜色检测跳过，图片读取失败: %s", image_path, exc_info=True)
        return []

    if image is None or not getattr(image, "size", 0):
        return []

    page_height, page_width = image.shape[:2]
    if page_height <= 0 or page_width <= 0:
        return []

    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    red_mask_low = cv2.inRange(
        hsv,
        np.array([0, 35, 45], dtype=np.uint8),
        np.array([16, 255, 255], dtype=np.uint8),
    )
    red_mask_high = cv2.inRange(
        hsv,
        np.array([150, 35, 45], dtype=np.uint8),
        np.array([180, 255, 255], dtype=np.uint8),
    )
    red_mask = cv2.bitwise_or(red_mask_low, red_mask_high)

    blue = image[:, :, 0]
    green = image[:, :, 1]
    red = image[:, :, 2]
    red_bias = (red.astype(np.int16) - np.maximum(blue, green).astype(np.int16)) >= 24
    bright_red = red >= 72
    red_mask = cv2.bitwise_or(red_mask, ((red_bias & bright_red).astype(np.uint8) * 255))

    if cv2.countNonZero(red_mask) == 0:
        return []

    cluster_kernel_size = max(5, int(round(min(page_width, page_height) * 0.022)))
    if cluster_kernel_size % 2 == 0:
        cluster_kernel_size += 1
    cluster_kernel = cv2.getStructuringElement(
        cv2.MORPH_ELLIPSE,
        (cluster_kernel_size, cluster_kernel_size),
    )

    clustered = cv2.morphologyEx(red_mask, cv2.MORPH_CLOSE, cluster_kernel, iterations=2)
    clustered = cv2.dilate(clustered, cluster_kernel, iterations=1)

    total_area = float(page_width * page_height)
    min_short_edge = max(24, int(min(page_width, page_height) * 0.07))
    min_bbox_area = max(900, int(total_area * 0.004))

    num_labels, _, stats, _ = cv2.connectedComponentsWithStats(clustered, connectivity=8)
    candidates: list[tuple[float, dict[str, Any]]] = []
    for label_idx in range(1, num_labels):
        x, y, width, height, _ = stats[label_idx]
        if width <= 0 or height <= 0:
            continue

        bbox_area = int(width * height)
        if bbox_area < min_bbox_area:
            continue

        short_edge = min(width, height)
        long_edge = max(width, height)
        if short_edge < min_short_edge:
            continue

        aspect_ratio = long_edge / max(short_edge, 1)
        if aspect_ratio > 2.3:
            continue

        bbox_area_ratio = bbox_area / total_area
        if bbox_area_ratio > 0.45:
            continue

        raw_region_mask = red_mask[y:y + height, x:x + width]
        red_pixels = int(cv2.countNonZero(raw_region_mask))
        if red_pixels < max(160, int(min_bbox_area * 0.12)):
            continue

        red_fill_ratio = red_pixels / float(bbox_area)
        if red_fill_ratio < 0.025:
            continue

        rect = _expand_rect([float(x), float(y), float(x + width), float(y + height)], page_width, page_height)
        content = _seal_content_from_lines(rect, page_lines or [], raw_content="")

        confidence = 0.35
        if aspect_ratio <= 1.35:
            confidence += 0.22
        elif aspect_ratio <= 1.7:
            confidence += 0.1
        confidence += min(red_fill_ratio / 0.18, 1.0) * 0.22
        confidence += min(bbox_area_ratio / 0.08, 1.0) * 0.16
        if content:
            confidence += 0.08
        confidence = round(min(confidence, 0.99), 4)

        candidates.append(
            (
                confidence,
                {
                    "type": "seal",
                    "bbox": rect,
                    "bbox_type": "rect",
                    "layout_bbox": rect,
                    "content": content,
                    "agent_meta": {
                        "detected_by": "opencv_red_seal_detector",
                        "detector_confidence": confidence,
                        "bbox_ratio": [
                            round(rect[0] / page_width, 4),
                            round(rect[1] / page_height, 4),
                            round(rect[2] / page_width, 4),
                            round(rect[3] / page_height, 4),
                        ],
                        "red_fill_ratio": round(red_fill_ratio, 4),
                        "red_pixel_count": red_pixels,
                        "page_size": [int(page_width), int(page_height)],
                    },
                },
            )
        )

    if not candidates:
        return []

    candidates.sort(key=lambda item: item[0], reverse=True)
    detected_regions: list[dict[str, Any]] = []
    for _, region in candidates:
        region_rect = _region_rect(region)
        if any(_overlap_on_smaller(region_rect, _region_rect(existing)) >= 0.7 for existing in detected_regions):
            continue
        detected_regions.append(region)
    return detected_regions


def _merge_detected_seal_regions(
    page: dict[str, Any],
    image_path: str,
    *,
    page_lines: list[dict] | None = None,
) -> dict[str, Any]:
    page.setdefault("regions", [])
    page.setdefault("lines", [])

    seal_regions = _detect_red_seal_regions(image_path, page_lines=page_lines or page.get("lines") or [])
    if not seal_regions:
        return page
    return _merge_seal_regions(page, seal_regions, detector_name="opencv_red_seal_detector")


def _enrich_document_with_detected_seals(document: dict[str, Any], file_path: str) -> dict[str, Any]:
    pages = document.get("pages") or []
    if not isinstance(pages, list) or not pages:
        return document

    file_ext = Path(file_path).suffix.lower()
    temp_images: list[str] = []
    image_paths: list[str] = []

    try:
        if file_ext == ".pdf":
            image_paths = pdf_to_images(file_path)
            temp_images.extend(image_paths)
        else:
            image_paths = [file_path]

        for index, page in enumerate(pages):
            if not isinstance(page, dict):
                continue
            if index >= len(image_paths):
                break
            pages[index] = _merge_detected_seal_regions(page, image_paths[index])
    finally:
        for tmp in temp_images:
            try:
                Path(tmp).unlink(missing_ok=True)
            except Exception:
                pass

    document["pages"] = pages
    return document


def _extract_page_lines(res, line_num_start: int = 0) -> tuple[list[dict], int]:
    page_lines = []
    line_num = line_num_start
    try:
        ocr_res = _item_value(res, "overall_ocr_res") or {}
        rec_texts = _item_value(ocr_res, "rec_texts") or []
        rec_scores = _item_value(ocr_res, "rec_scores") or []
        dt_polys = _item_value(ocr_res, "dt_polys") or []

        for idx in range(len(rec_texts)):
            text = rec_texts[idx]
            confidence = _safe_float(rec_scores[idx]) if idx < len(rec_scores) else 0.0
            bbox = _poly_to_list(dt_polys[idx]) if idx < len(dt_polys) else []
            line_num += 1
            page_lines.append(
                {
                    "line_num": line_num,
                    "text": text,
                    "confidence": round(confidence, 4),
                    "bbox": bbox,
                }
            )
    except Exception as exc:
        logger.warning("提取 OCR 行数据失败: %s", exc)
    return page_lines, line_num


def _predict_structured(pipeline, image_path: str, profile: str = "layout"):
    kwargs = _structured_predict_kwargs(pipeline, profile)
    predict_name = "VL" if profile == "vl" else "Layout"
    logger.info(
        "开始执行 %s 预测: %s (kwargs=%s)",
        predict_name,
        Path(image_path).name,
        ", ".join(sorted(kwargs)) or "none",
    )
    if profile == "vl":
        import paddle as _paddle

        _paddle.device.set_device(OCR_DEVICE)
        logger.info("VL 预测前设置 paddle device: %s", OCR_DEVICE)

    started_at = time.perf_counter()
    while True:
        try:
            results = list(pipeline.predict(input=image_path, **kwargs))
            logger.info(
                "%s 预测完成: %s, 输出 %s 个结果, 用时 %.2fs",
                predict_name,
                Path(image_path).name,
                len(results),
                time.perf_counter() - started_at,
            )
            return results
        except TypeError as exc:
            match = _UNSUPPORTED_PREDICT_ARG_RE.search(str(exc))
            if not match:
                raise
            arg_name = match.group("name")
            if arg_name not in kwargs:
                raise
            logger.warning("predict 参数 %s 当前不可用，自动回退。", arg_name)
            kwargs.pop(arg_name)
        except Exception as exc:
            message = str(exc)
            if not _MISSING_DOC_PREPROCESSOR_RE.search(message):
                raise

            disabled = []
            for arg_name in ("use_doc_orientation_classify", "use_doc_unwarping"):
                if arg_name in kwargs:
                    kwargs.pop(arg_name)
                    disabled.append(arg_name)

            if not disabled:
                raise

            logger.warning(
                "当前管线缺少 doc_preprocessor_pipeline，已自动关闭 %s 后重试。",
                ", ".join(disabled),
            )


def _text_similarity(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    if a in b or b in a:
        return 0.92
    return SequenceMatcher(None, a, b).ratio()


def _precise_region_bbox_from_lines(label: str, bbox: list[float], region_lines: list[dict]):
    if len(bbox) < 4 or not _is_textual_region(label):
        return bbox, "rect"

    polys = [line["bbox"] for line in region_lines if line.get("bbox") and isinstance(line["bbox"][0], list)]
    if not polys:
        return bbox, "rect"
    if len(polys) == 1:
        return polys[0], "poly"
    precise_rect = _rect_from_polys(polys)
    return precise_rect or bbox, "rect"


def get_vl_pipeline():
    """获取 PaddleOCR-VL-1.5 视觉语言模型管线单例（官网同款，识别质量最佳）"""
    global _vl_pipeline
    if _vl_pipeline is None:
        import os
        _patch_paddle_bfloat16_tensor_loading()
        from paddlex import create_pipeline
        logger.info("正在初始化 PaddleOCR-VL-1.5 视觉语言模型管线 (device=%s)...", OCR_DEVICE)
        import paddle as _paddle
        _paddle.device.set_device(OCR_DEVICE)
        # VL 管线的 PP-DocLayoutV3 需要 JSON 格式模型，临时切换标志
        old_flag = os.environ.get("FLAGS_json_format_model")
        os.environ.pop("FLAGS_json_format_model", None)
        try:
            _vl_pipeline = create_pipeline(
                pipeline="PaddleOCR-VL-1.5",
                device=OCR_DEVICE,
            )
            logger.info("PaddleOCR-VL-1.5 管线初始化完成")
        finally:
            if old_flag is not None:
                os.environ["FLAGS_json_format_model"] = old_flag

    return _vl_pipeline


def ocr_document_layout_api(file_path: str, *, mode_label: str = "layout_api") -> dict:
    """Call the remote PaddleOCR layout API and normalize its result."""
    document = _map_layout_api_result_to_document(_call_layout_api(file_path))
    document = _enrich_document_with_detected_seals(document, file_path)
    document["mode"] = mode_label
    return document


def ocr_image_basic(image_path: str) -> dict:
    """
    使用轻量级 PP-OCRv5 模型进行纯文本提取。
    
    这是系统中最快速的兜底提取管线（Fallback）。它不包含版面分析（不区分段落、表格或印章），
    纯粹将图片切割成行并读取文字。
    
    适用场景：只关注“有哪些字”，而不需要复杂的结构化上下文，常作为 LLM 实体提取的前置输入。
    """
    if _should_use_layout_api("ocr"):
        document = ocr_document_layout_api(image_path, mode_label="ocr_api")
        pages = document.get("pages") or []
        return pages[0] if pages else {"regions": [], "lines": []}

    ocr = get_ocr()
    results = ocr.predict(image_path)

    lines = []
    if results:
        for res in results:
            rec_texts = _item_value(res, "rec_texts") or []
            rec_scores = _item_value(res, "rec_scores") or []
            dt_polys = _item_value(res, "dt_polys") or []
            for idx, text in enumerate(rec_texts):
                confidence = _safe_float(rec_scores[idx]) if idx < len(rec_scores) else 0.0
                bbox = _poly_to_list(dt_polys[idx]) if idx < len(dt_polys) else []
                lines.append(
                    {
                        "line_num": idx + 1,
                        "text": text,
                        "confidence": round(confidence, 4),
                        "bbox": bbox,
                    }
                )
    return _merge_detected_seal_regions({"regions": [], "lines": lines}, image_path, page_lines=lines)


def ocr_image_with_layout(image_path: str) -> dict:
    """
    使用 PP-StructureV3 版面解析流水线。
    
    不同于 basic OCR，这是一个复杂的计算机视觉（CV）工程，包括：
    1. 版面元素检测（区分正文、标题、表格、印章等区域）。
    2. 对每个区域使用不同的子模型进行识别（如表格结构重建、印章文字弯曲矫正）。
    3. 最后合并逻辑，重新排列段落的逻辑阅读顺序。
    
    返回：
        {"regions": [{"type": "text", "content": "...", "bbox": [...]}, ...], "lines": [...]}
    """
    if _should_use_layout_api("layout"):
        document = ocr_document_layout_api(image_path)
        pages = document.get("pages") or []
        return pages[0] if pages else {"regions": [], "lines": []}

    pipeline = get_layout_pipeline()
    results = _predict_structured(pipeline, image_path, profile="layout")

    regions = []
    lines = []
    line_num = 0

    for res in results:
        page_lines, line_num = _extract_page_lines(res, line_num)
        lines.extend(page_lines)

        parsing_list = _item_value(res, "parsing_res_list") or []
        for item in parsing_list:
            bbox_raw = _item_value(item, "block_bbox", "bbox") or []
            poly_pts = _item_polygon_points(item, dict_key="block_polygon_points")
            layout_bbox, poly_pts = _coerce_layout_bbox(bbox_raw, poly_pts)
            raw_label = _item_value(item, "block_label", "label") or "text"
            content = str(_item_value(item, "block_content", "content") or "")
            table_data, table_html, content = _extract_table_payload(item, str(raw_label), content)
            label = _canonical_region_type(raw_label, has_table_payload=table_data is not None or bool(table_html))
            region_lines = _collect_region_lines(label, layout_bbox, content, page_lines)
            if label == "seal":
                content = _seal_content_from_lines(layout_bbox, page_lines, raw_content=content)

            if poly_pts:
                precise_bbox, bbox_type = poly_pts, "poly"
            else:
                precise_bbox, bbox_type = _precise_region_bbox_from_lines(label, layout_bbox, region_lines)

            region = {
                "type": label,
                "bbox": precise_bbox,
                "bbox_type": bbox_type,
                "layout_bbox": layout_bbox,
                "content": content,
            }
            if table_html:
                region["html"] = table_html
            if table_data is not None:
                region["table_data"] = table_data
            if region_lines:
                region["region_lines"] = region_lines
            regions.append(region)

    return _merge_detected_seal_regions(
        {"regions": _filter_output_regions(regions), "lines": lines},
        image_path,
        page_lines=lines,
    )


def ocr_image_with_vl(image_path: str) -> dict:
    """
    使用 PaddleOCR-VL-1.5 视觉语言模型进行提取（多模态架构）。
    
    这是系统中准确率最高的提取管线，它不仅仅使用传统 OCR 识别字符，
    还结合 PaddleOCR-VL-1.5 的视觉语言建模能力来理解版面和语义逻辑
    （例如复杂表格、印章主体关系等）。
    
    注意：此方法对 GPU 显存和算力要求较高，常用于高质量、结构化诉求强烈的发票、合同等复杂文档。
    
    返回: 
        {"regions": [{"type": "table|text|seal", "content": "...", "bbox": [...]}, ...], "lines": []}
    """
    if _should_use_layout_api("vl"):
        document = ocr_document_layout_api(image_path, mode_label="vl_api")
        pages = document.get("pages") or []
        return pages[0] if pages else {"regions": [], "lines": []}

    pipeline = get_vl_pipeline()
    results = _predict_structured(pipeline, image_path, profile="vl")

    regions = []
    line_num = 0
    for res in results:
        page_lines, line_num = _extract_page_lines(res, line_num)
        parsing_list = _item_value(res, "parsing_res_list") or []
        for item in parsing_list:
            raw_label = _item_value(item, "label", "block_label") or "text"
            content = str(_item_value(item, "content", "block_content") or "")
            bbox_raw = _item_value(item, "bbox", "block_bbox") or []
            poly_pts = _item_polygon_points(item, dict_key="block_polygon_points")
            bbox, poly_pts = _coerce_layout_bbox(bbox_raw, poly_pts)
            table_data, table_html, content = _extract_table_payload(item, str(raw_label), content)
            label = _canonical_region_type(raw_label, has_table_payload=table_data is not None or bool(table_html))
            region_lines = _collect_region_lines(label, bbox, content, page_lines)
            if label == "seal":
                content = _seal_content_from_lines(bbox, page_lines, raw_content=content)

            bbox_type = "rect"
            final_bbox = bbox
            if poly_pts:
                final_bbox = poly_pts
                bbox_type = "poly"

            region = {
                "type": label,
                "bbox": final_bbox,
                "bbox_type": bbox_type,
                "layout_bbox": bbox,
                "content": content,
            }
            if table_html:
                region["html"] = table_html
            if table_data is not None:
                region["table_data"] = table_data
            if region_lines:
                region["region_lines"] = region_lines
            regions.append(region)

    return _merge_detected_seal_regions(
        {"regions": _filter_output_regions(regions), "lines": []},
        image_path,
        page_lines=page_lines,
    )


def pdf_to_images(pdf_path: str) -> list[str]:
    """将 PDF 转换为图片列表（保存到 uploads 目录避免中文路径问题）"""
    fitz_module = _require_fitz()
    doc = fitz_module.open(pdf_path)
    image_paths = []
    prefix = Path(pdf_path).stem[:8]  # 取文件名前8字符作为前缀

    for page_num in range(len(doc)):
        page = doc[page_num]
        mat = fitz_module.Matrix(2, 2)  # 2x 分辨率
        pix = page.get_pixmap(matrix=mat)
        # 保存到 uploads 目录（纯 ASCII 路径）
        tmp = tempfile.NamedTemporaryFile(suffix='.png', delete=False, dir=str(UPLOAD_DIR),
                                          prefix=f'page{page_num+1}_')
        tmp.close()
        pix.save(tmp.name)
        image_paths.append(tmp.name)

    doc.close()
    return image_paths


# ===== 百度 AI 云文档解析 API =====

_BAIDU_TYPE_MAP: dict[str, str] = {
    "abstract": "text",
    "algorithm": "text",
    "aside_text": "text",
    "chart": "chart",
    "content": "text",
    "display_formula": "text",
    "doc_title": "doc_title",
    "figure_title": "text",
    "footer": "footer",
    "footer_image": "image",
    "footnote": "text",
    "formula_number": "number",
    "head_tail": "other_text",
    "header": "header",
    "header_image": "image",
    "image": "image",
    "inline_formula": "text",
    "number": "number",
    "paragraph_title": "paragraph_title",
    "reference": "text",
    "reference_content": "text",
    "seal": "seal",
    "table": "table",
    "text": "text",
    "title": "paragraph_title",
    "vertical_text": "text",
}

_baidu_token_cache: dict = {}


def _canonical_baidu_type(raw_type: str) -> str:
    return _BAIDU_TYPE_MAP.get(str(raw_type).lower(), "text")


def _get_baidu_access_token() -> str:
    import requests as _requests

    now = time.time()
    if _baidu_token_cache.get("token") and now < _baidu_token_cache.get("expires_at", 0) - 300:
        return _baidu_token_cache["token"]

    if not BAIDU_API_KEY or not BAIDU_SECRET_KEY:
        raise RuntimeError(
            "未配置百度 AI 密钥，请在 .env 文件中设置 BAIDU_API_KEY 和 BAIDU_SECRET_KEY。"
        )

    resp = _requests.get(
        "https://aip.baidubce.com/oauth/2.0/token",
        params={
            "grant_type": "client_credentials",
            "client_id": BAIDU_API_KEY,
            "client_secret": BAIDU_SECRET_KEY,
        },
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    if "access_token" not in data:
        raise RuntimeError(f"百度 AI 鉴权失败: {data}")

    token = data["access_token"]
    expires_in = int(data.get("expires_in", 2592000))
    _baidu_token_cache["token"] = token
    _baidu_token_cache["expires_at"] = now + expires_in
    logger.info("百度 AI 访问令牌已刷新，有效期 %d 秒。", expires_in)
    return token


def _parse_markdown_table(markdown: str) -> list[list[str]]:
    rows = []
    for line in markdown.strip().splitlines():
        line = line.strip()
        if not line or "|" not in line:
            continue
        if re.match(r"^[\|\s\-:]+$", line):
            continue
        cells = line.split("|")
        if cells and cells[0].strip() == "":
            cells = cells[1:]
        if cells and cells[-1].strip() == "":
            cells = cells[:-1]
        cells = [c.strip() for c in cells]
        if cells:
            rows.append(cells)
    return rows if rows else [[""]]


def _markdown_table_to_html(markdown: str) -> str:
    lines = [l.strip() for l in markdown.strip().splitlines() if l.strip()]
    if not lines:
        return ""
    header_done = False
    html_rows = []
    for line in lines:
        if "|" not in line:
            continue
        if re.match(r"^[\|\s\-:]+$", line):
            header_done = True
            continue
        cells = line.split("|")
        if cells and cells[0].strip() == "":
            cells = cells[1:]
        if cells and cells[-1].strip() == "":
            cells = cells[:-1]
        cells = [c.strip() for c in cells]
        if not cells:
            continue
        if not header_done:
            row_html = "<tr>" + "".join(f"<th>{c}</th>" for c in cells) + "</tr>"
        else:
            row_html = "<tr>" + "".join(f"<td>{c}</td>" for c in cells) + "</tr>"
        html_rows.append(row_html)
    return f"<table>{''.join(html_rows)}</table>" if html_rows else ""


_HTML_IMAGE_TAG_RE = re.compile(r"<img\b[^>]*>", re.IGNORECASE)
_MARKDOWN_IMAGE_RE = re.compile(r"!\[[^\]]*]\([^)]+\)")


def _sanitize_baidu_table_cell(value: Any) -> str:
    text = str(value or "")
    text = _HTML_IMAGE_TAG_RE.sub(" ", text)
    text = _MARKDOWN_IMAGE_RE.sub(" ", text)
    text = text.replace("\r", " ").replace("\n", " ").replace("\t", " ")
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _markdown_line_to_plain_text(value: Any) -> str:
    text = str(value or "")
    text = _MARKDOWN_IMAGE_RE.sub(" ", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"^\s{0,3}#{1,6}\s*", "", text)
    text = re.sub(r"^\s*[-*+]\s+", "", text)
    text = re.sub(r"^\s*\d+[.)]\s+", "", text)
    text = text.replace("**", "").replace("__", "").replace("`", "")
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _markdown_text_to_page(markdown_text: str, page_num: int) -> dict:
    regions: list[dict[str, Any]] = []
    lines: list[dict[str, Any]] = []
    line_num = 0

    blocks: list[str] = []
    buffer: list[str] = []
    for raw_line in str(markdown_text or "").splitlines():
        line = raw_line.rstrip()
        if line.strip():
            buffer.append(line)
            continue
        if buffer:
            blocks.append("\n".join(buffer))
            buffer = []
    if buffer:
        blocks.append("\n".join(buffer))

    for block in blocks:
        if _looks_like_markdown_table(block):
            table_data = _normalize_table_payload(_parse_markdown_table(block)) or [[""]]
            table_text = table_data_to_text(table_data)
            regions.append(
                {
                    "type": "table",
                    "bbox": [],
                    "bbox_type": "rect",
                    "layout_bbox": [],
                    "content": table_text,
                    "table_data": table_data,
                    "html": _markdown_table_to_html(block),
                }
            )
            for row_text in table_text.splitlines():
                clean = _markdown_line_to_plain_text(row_text)
                if not clean:
                    continue
                line_num += 1
                lines.append(
                    {
                        "line_num": line_num,
                        "text": clean,
                        "confidence": 0.95,
                        "bbox": [],
                        "bbox_type": "rect",
                    }
                )
            continue

        plain_lines = []
        for raw_line in block.splitlines():
            clean = _markdown_line_to_plain_text(raw_line)
            if clean:
                plain_lines.append(clean)

        if not plain_lines:
            continue

        region_lines = []
        for clean in plain_lines:
            line_num += 1
            payload = {
                "line_num": line_num,
                "text": clean,
                "confidence": 0.95,
                "bbox": [],
                "bbox_type": "rect",
            }
            lines.append(dict(payload))
            region_lines.append(payload)

        regions.append(
            {
                "type": "text",
                "bbox": [],
                "bbox_type": "rect",
                "layout_bbox": [],
                "content": "\n".join(plain_lines),
                "region_lines": region_lines,
            }
        )

    return {
        "page_num": page_num,
        "regions": regions,
        "lines": lines,
        "_ocr_web_meta": {
            "route_confidence_available": False,
            "route_confidence_source": "layout_api_markdown",
        },
    }


def _raise_layout_api_error(response) -> None:
    text = re.sub(r"\s+", " ", str(response.text or "")).strip()[:240]
    detail = f"PaddleOCR API HTTP {response.status_code}: 版面解析请求失败。"
    if response.status_code in {401, 403}:
        detail = f"PaddleOCR API HTTP {response.status_code}: 鉴权失败，请检查 OCR_LAYOUT_API_TOKEN。"
    elif response.status_code == 404:
        detail = f"PaddleOCR API HTTP {response.status_code}: 接口地址不可用，请检查 OCR_LAYOUT_API_URL。"
    if text:
        detail = f"{detail} Upstream: {text}"
    raise RuntimeError(detail)


def _call_layout_api(file_path: str) -> dict[str, Any]:
    if httpx is None:
        raise RuntimeError("httpx is required to call the remote PaddleOCR layout API.")
    if not _can_use_layout_api():
        raise RuntimeError("OCR_LAYOUT_API_URL/OCR_LAYOUT_API_TOKEN is not configured.")

    payload = {
        "file": base64.b64encode(Path(file_path).read_bytes()).decode("ascii"),
        "fileType": 0 if Path(file_path).suffix.lower() == ".pdf" else 1,
        "useDocOrientationClassify": OCR_LAYOUT_API_USE_DOC_ORIENTATION_CLASSIFY,
        "useDocUnwarping": OCR_LAYOUT_API_USE_DOC_UNWARPING,
        "useChartRecognition": OCR_LAYOUT_API_USE_CHART_RECOGNITION,
    }
    headers = {
        "Authorization": f"token {OCR_LAYOUT_API_TOKEN}",
        "Content-Type": "application/json",
    }

    with httpx.Client(timeout=OCR_LAYOUT_API_TIMEOUT_SECONDS) as client:
        response = client.post(OCR_LAYOUT_API_URL, json=payload, headers=headers)

    if response.status_code >= 400:
        _raise_layout_api_error(response)

    try:
        payload = response.json()
    except ValueError as exc:
        raise RuntimeError("PaddleOCR API returned a non-JSON response.") from exc

    result = payload.get("result")
    if not isinstance(result, dict):
        raise RuntimeError("PaddleOCR API response did not include a valid `result` object.")
    return result


def _map_layout_api_result_to_document(raw_result: dict[str, Any]) -> dict[str, Any]:
    layout_results = raw_result.get("layoutParsingResults") or []
    pages = []
    texts = []

    for index, item in enumerate(layout_results, start=1):
        markdown_text = str((((item or {}).get("markdown") or {}).get("text")) or "").strip()
        page = _markdown_text_to_page(markdown_text, index)
        pages.append(page)
        texts.append(markdown_text)

    if not pages:
        pages = [_markdown_text_to_page("", 1)]
        texts = [""]

    if len(texts) > 1:
        full_text = "\n\n".join(
            f"--- 第 {index} 页 ---\n{text}"
            for index, text in enumerate(texts, start=1)
        ).strip()
    else:
        full_text = texts[0]

    return {
        "page_count": len(pages),
        "pages": pages,
        "full_text": full_text,
        "mode": "layout_api",
    }


def _collapse_obvious_merged_rows(rows: list[list[str]]) -> list[list[str]]:
    normalized_rows: list[list[str]] = []
    for row in rows:
        cells = [str(cell or "").strip() for cell in row]
        non_empty = [cell for cell in cells if cell]
        if non_empty and len(set(non_empty)) == 1 and len(non_empty) >= 3:
            normalized_rows.append([non_empty[0]] + [""] * (len(cells) - 1))
            continue
        normalized_rows.append(cells)
    return normalized_rows


def _extract_baidu_table_data(table_info: dict) -> list[list[str]]:
    cells = table_info.get("cells") or []
    matrix = table_info.get("matrix") or []
    if cells and matrix:
        cell_texts = [_sanitize_baidu_table_cell(cell.get("text")) for cell in cells]
        seen_global: set[int] = set()
        result: list[list[str]] = []
        for row in matrix:
            seen_in_row: set[int] = set()
            row_cells: list[str] = []
            for raw_idx in row:
                try:
                    idx = int(raw_idx)
                except (TypeError, ValueError):
                    row_cells.append("")
                    continue
                if idx < 0 or idx >= len(cell_texts):
                    row_cells.append("")
                    continue

                # Matrix indices are reused for merged cells.
                # Keep the first appearance and blank span-expansion positions.
                if idx in seen_in_row or idx in seen_global:
                    row_cells.append("")
                    continue

                row_cells.append(cell_texts[idx])
                seen_in_row.add(idx)
                seen_global.add(idx)

            result.append(row_cells)

        result = [row for row in result if any(str(cell or "").strip() for cell in row)]
        result = _collapse_obvious_merged_rows(result)
        normalized = _normalize_table_payload(result)
        return normalized if normalized is not None else [[""]]
    markdown = str(table_info.get("markdown") or "")
    if markdown:
        parsed = _parse_markdown_table(markdown)
        parsed = [[_sanitize_baidu_table_cell(cell) for cell in row] for row in parsed]
        parsed = _collapse_obvious_merged_rows(parsed)
        normalized = _normalize_table_payload(parsed)
        return normalized if normalized is not None else [[""]]
    return [[""]]


def _safe_float(value: Any, default: float = 0.0) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return default
        try:
            return float(text)
        except ValueError:
            return default
    if isinstance(value, (list, tuple)) and value:
        return _safe_float(value[0], default)
    return default


def _baidu_location_to_bbox(raw_location: Any) -> list[float]:
    if hasattr(raw_location, "tolist"):
        raw_location = raw_location.tolist()

    if isinstance(raw_location, dict):
        x = _safe_float(raw_location.get("x", raw_location.get("left", 0.0)))
        y = _safe_float(raw_location.get("y", raw_location.get("top", 0.0)))
        width = _safe_float(raw_location.get("w", raw_location.get("width", 0.0)))
        height = _safe_float(raw_location.get("h", raw_location.get("height", 0.0)))
        if width > 0 and height > 0:
            return [x, y, x + width, y + height]
        right = _safe_float(raw_location.get("right", x))
        bottom = _safe_float(raw_location.get("bottom", y))
        if right > x and bottom > y:
            return [x, y, right, bottom]
        return []

    if not isinstance(raw_location, (list, tuple)) or not raw_location:
        return []

    first_item = raw_location[0]
    if isinstance(first_item, dict):
        poly = _poly_to_list(raw_location)
        return _rect_from_polys([poly]) if poly else []
    if isinstance(first_item, (list, tuple)):
        poly = _poly_to_list(raw_location)
        return _rect_from_polys([poly]) if poly else []

    if len(raw_location) >= 8:
        poly = []
        for index in range(0, min(len(raw_location), 8), 2):
            poly.append([_safe_float(raw_location[index]), _safe_float(raw_location[index + 1])])
        return _rect_from_polys([poly]) if poly else []

    if len(raw_location) >= 4:
        x = _safe_float(raw_location[0])
        y = _safe_float(raw_location[1])
        width = _safe_float(raw_location[2])
        height = _safe_float(raw_location[3])
        if width <= 0 or height <= 0:
            return []
        return [x, y, x + width, y + height]

    return []


def _rect_to_poly(rect: list[float]) -> list[list[float]]:
    if len(rect) < 4:
        return []
    x1, y1, x2, y2 = rect
    return [[x1, y1], [x2, y1], [x2, y2], [x1, y2]]


def _baidu_location_to_poly(raw_location: Any) -> list[list[float]]:
    poly = _poly_to_list(raw_location)
    if poly:
        return poly
    return _rect_to_poly(_baidu_location_to_bbox(raw_location))


def _baidu_probability_value(value: Any) -> float:
    if isinstance(value, dict):
        for key in ("probability", "average", "score", "confidence"):
            if key in value:
                return _safe_float(value.get(key))
        return 0.0
    if isinstance(value, (list, tuple)):
        scores = [_baidu_probability_value(item) for item in value]
        scores = [score for score in scores if score > 0]
        return round(sum(scores) / len(scores), 4) if scores else 0.0
    return _safe_float(value)


def _baidu_office_word_text(word_payload: Any) -> str:
    if isinstance(word_payload, dict):
        return str(word_payload.get("word") or word_payload.get("words") or "").strip()
    return str(word_payload or "").strip()


def _extract_baidu_office_page_lines(raw_result: dict[str, Any]) -> list[dict[str, Any]]:
    lines: list[dict[str, Any]] = []
    for line_num, result in enumerate(raw_result.get("results") or [], start=1):
        words_payload = result.get("words")
        line_text = ""
        line_poly: list[list[float]] = []

        if isinstance(words_payload, list):
            texts = [_baidu_office_word_text(item) for item in words_payload]
            line_text = "".join(text for text in texts if text)
            polys = [
                _baidu_location_to_poly(
                    item.get("poly_location")
                    or item.get("words_location")
                    or item.get("location")
                    or []
                )
                for item in words_payload
                if isinstance(item, dict)
            ]
            polys = [poly for poly in polys if poly]
            if polys:
                line_poly = _rect_to_poly(_rect_from_polys(polys))
        elif isinstance(words_payload, dict):
            line_text = _baidu_office_word_text(words_payload)
            line_poly = _baidu_location_to_poly(
                words_payload.get("poly_location")
                or words_payload.get("words_location")
                or words_payload.get("location")
                or []
            )
        else:
            line_text = str(result.get("word") or result.get("words") or "").strip()

        if not line_poly:
            line_poly = _baidu_location_to_poly(
                result.get("poly_location")
                or result.get("words_location")
                or result.get("location")
                or []
            )
        if not line_text:
            continue

        lines.append(
            {
                "line_num": line_num,
                "text": line_text,
                "confidence": round(
                    _baidu_probability_value(result.get("line_probability") or result.get("probability") or 0.0),
                    4,
                ),
                "bbox": line_poly,
                "bbox_type": "poly" if line_poly else "rect",
            }
        )
    return lines


def _baidu_office_layout_indices(layout: dict[str, Any]) -> list[int]:
    raw_indices = layout.get("layout_idx") or []
    if not isinstance(raw_indices, (list, tuple)):
        raw_indices = [raw_indices]

    indices: list[int] = []
    for raw_value in raw_indices:
        try:
            value = int(raw_value)
        except (TypeError, ValueError):
            continue
        if value >= 0:
            indices.append(value)
    return indices


def _baidu_office_layout_lines(layout: dict[str, Any], page_lines: list[dict[str, Any]]) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    seen: set[int] = set()
    for index in _baidu_office_layout_indices(layout):
        if index in seen or index < 0 or index >= len(page_lines):
            continue
        seen.add(index)
        selected.append(_copy_line_payload(page_lines[index]))
    return selected


def _baidu_office_seal_text(seal_result: dict[str, Any]) -> str:
    segments: list[str] = []
    major = seal_result.get("major")
    if isinstance(major, dict):
        major_text = str(major.get("words") or major.get("word") or "").strip()
        if major_text:
            segments.append(major_text)

    for minor in seal_result.get("minor") or []:
        if not isinstance(minor, dict):
            continue
        minor_text = str(minor.get("words") or minor.get("word") or "").strip()
        if minor_text:
            segments.append(minor_text)

    return _normalize_seal_content("\n".join(segments))


def _extract_baidu_office_seal_regions(raw_result: dict[str, Any]) -> list[dict[str, Any]]:
    page_lines = _extract_baidu_office_page_lines(raw_result)
    seal_regions: list[dict[str, Any]] = []

    for layout in raw_result.get("layouts") or []:
        raw_type = str(layout.get("layout") or layout.get("type") or "").strip().lower()
        if raw_type not in {"seal", "stamp"}:
            continue

        bbox = _baidu_location_to_bbox(
            layout.get("layout_location")
            or layout.get("position")
            or layout.get("location")
            or []
        )
        if len(bbox) < 4:
            continue

        region_lines = _baidu_office_layout_lines(layout, page_lines)
        raw_content = "\n".join(
            str(line.get("text") or "").strip()
            for line in region_lines
            if str(line.get("text") or "").strip()
        )
        content = _seal_content_from_lines(bbox, page_lines, raw_content=raw_content)

        region: dict[str, Any] = {
            "type": "seal",
            "bbox": bbox,
            "bbox_type": "rect",
            "layout_bbox": bbox,
            "content": content,
            "agent_meta": {
                "detected_by": "baidu_doc_analysis_office_layout",
                "detector_confidence": round(
                    _baidu_probability_value(layout.get("layout_probability") or layout.get("probability") or 0.0),
                    4,
                ),
            },
        }
        if region_lines:
            region["region_lines"] = region_lines
        seal_regions.append(region)

    for seal_result in raw_result.get("seal_recog_results") or []:
        if not isinstance(seal_result, dict):
            continue

        bbox = _baidu_location_to_bbox(
            seal_result.get("location")
            or seal_result.get("seal_location")
            or []
        )
        if len(bbox) < 4:
            continue

        raw_content = _baidu_office_seal_text(seal_result)
        content = _seal_content_from_lines(bbox, page_lines, raw_content=raw_content)
        region: dict[str, Any] = {
            "type": "seal",
            "bbox": bbox,
            "bbox_type": "rect",
            "layout_bbox": bbox,
            "content": content,
            "agent_meta": {
                "detected_by": "baidu_doc_analysis_office_seal",
                "detector_confidence": round(_baidu_probability_value(seal_result.get("probability") or 0.0), 4),
            },
        }

        seal_type = str(seal_result.get("type") or "").strip()
        if seal_type:
            region["agent_meta"]["seal_type"] = seal_type
        seal_regions.append(region)

    return seal_regions


def _call_baidu_doc_analysis_office(
    file_path: str,
    *,
    page_num: int | None = None,
    token: str | None = None,
    encoded_file: str | None = None,
) -> dict[str, Any]:
    import requests as _requests

    access_token = token or _get_baidu_access_token()
    payload_file = encoded_file
    if payload_file is None:
        payload_file = base64.b64encode(Path(file_path).read_bytes()).decode("utf-8")

    suffix = Path(file_path).suffix.lower()
    data: dict[str, Any] = {
        "layout_analysis": "true",
        "recog_seal": "true",
        "disp_line_poly": "true",
        "line_probability": "true",
    }
    if suffix == ".pdf":
        data["pdf_file"] = payload_file
        if page_num is not None:
            data["pdf_file_num"] = str(page_num)
    elif suffix == ".ofd":
        data["ofd_file"] = payload_file
        if page_num is not None:
            data["ofd_file_num"] = str(page_num)
    else:
        data["image"] = payload_file

    response = _requests.post(
        f"https://aip.baidubce.com/rest/2.0/ocr/v1/doc_analysis_office?access_token={access_token}",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        data=data,
        timeout=120,
    )
    response.raise_for_status()
    payload = response.json()
    error_code = payload.get("error_code")
    if error_code not in (0, "0", None, ""):
        raise RuntimeError(
            f"百度办公文档识别失败 ({error_code}): {payload.get('error_msg', '')}"
        )
    return payload


def _page_requires_baidu_office_seal_enrichment(page: dict[str, Any]) -> bool:
    seal_regions = [
        region
        for region in (page.get("regions") or [])
        if str(region.get("type") or "").strip().lower() == "seal"
    ]
    if not seal_regions:
        return True
    return all(len(_region_rect(region)) < 4 for region in seal_regions)


def _enrich_document_with_baidu_office_seals(document: dict[str, Any], file_path: str) -> dict[str, Any]:
    pages = document.get("pages") or []
    if not isinstance(pages, list) or not pages or not _can_use_baidu_document_api():
        return document

    suffix = Path(file_path).suffix.lower()
    if suffix not in {".png", ".jpg", ".jpeg", ".bmp", ".webp", ".tif", ".tiff", ".pdf", ".ofd"}:
        return document

    try:
        token = _get_baidu_access_token()
        encoded_file = base64.b64encode(Path(file_path).read_bytes()).decode("utf-8")
    except Exception as exc:
        logger.warning("百度办公文档印章增强初始化失败，跳过该步骤：%s", exc)
        return document

    office_cache: dict[int, dict[str, Any]] = {}
    for index, page in enumerate(pages, start=1):
        if not isinstance(page, dict) or not _page_requires_baidu_office_seal_enrichment(page):
            continue

        office_page_num = index if suffix in {".pdf", ".ofd"} else 1
        try:
            if office_page_num not in office_cache:
                office_cache[office_page_num] = _call_baidu_doc_analysis_office(
                    file_path,
                    page_num=office_page_num if suffix in {".pdf", ".ofd"} else None,
                    token=token,
                    encoded_file=encoded_file,
                )
            seal_regions = _extract_baidu_office_seal_regions(office_cache[office_page_num])
        except Exception as exc:
            logger.warning("百度办公文档印章增强失败（page=%s），已跳过：%s", office_page_num, exc)
            continue

        if seal_regions:
            pages[index - 1] = _merge_seal_regions(
                page,
                seal_regions,
                detector_name="baidu_doc_analysis_office",
            )

    document["pages"] = pages
    return document


def _map_baidu_page(baidu_page: dict) -> dict:
    layouts = baidu_page.get("layouts") or []
    tables_by_id = {
        t["layout_id"]: t
        for t in (baidu_page.get("tables") or [])
        if t.get("layout_id")
    }
    images_by_id = {
        img["layout_id"]: img
        for img in (baidu_page.get("images") or [])
        if img.get("layout_id")
    }

    regions = []
    for layout in layouts:
        try:
            layout_id = layout.get("layout_id", "")
            raw_type = str(layout.get("type") or "text")
            text = str(layout.get("text") or "").strip()
            bbox = _baidu_location_to_bbox(layout.get("position") or [])

            label = _canonical_baidu_type(raw_type)
            table_data = None
            table_html = None

            if raw_type == "table" and layout_id in tables_by_id:
                tbl = tables_by_id[layout_id]
                table_data = _extract_baidu_table_data(tbl)
                md = tbl.get("markdown") or ""
                if md:
                    table_html = _markdown_table_to_html(md)
                text = ""
            elif raw_type == "image" and layout_id in images_by_id:
                text = ""

            region_lines = []
            for span in (layout.get("span_boxes") or []):
                try:
                    span_text = str(span.get("text") or "").strip()
                    span_bbox = _baidu_location_to_bbox(span.get("location") or [])
                    if span_text:
                        region_lines.append({
                            "text": span_text,
                            "bbox": span_bbox,
                            "bbox_type": "rect",
                            "confidence": 0.99,
                        })
                except Exception as span_exc:
                    logger.warning("Baidu span 瑙ｆ瀽宸茶烦杩囷細%s", span_exc)

            region: dict[str, Any] = {
                "type": label,
                "bbox": bbox,
                "bbox_type": "rect",
                "layout_bbox": bbox,
                "content": text,
            }
            if table_html:
                region["html"] = table_html
            if table_data is not None:
                region["table_data"] = table_data
            if region_lines:
                region["region_lines"] = region_lines
            regions.append(region)
        except Exception as layout_exc:
            logger.warning("Baidu layout 瑙ｆ瀽宸茶烦杩囷細%s", layout_exc)

    return {"regions": _filter_output_regions(regions), "lines": []}


def _map_baidu_result_to_document(raw: dict) -> dict:
    pages = []
    all_texts = []

    for baidu_page in raw.get("pages") or []:
        page_num = int(baidu_page.get("page_num") or 0) + 1
        mapped = _map_baidu_page(baidu_page)
        mapped["page_num"] = page_num
        pages.append(mapped)

        page_texts = []
        for region in mapped.get("regions") or []:
            if region["type"] == "table":
                page_texts.append("[表格]")
            elif region.get("content"):
                page_texts.append(region["content"])
        all_texts.append("\n".join(page_texts))

    if not pages:
        pages = [{"page_num": 1, "regions": [], "lines": []}]
        all_texts = [""]

    if len(pages) > 1:
        full_text = "\n\n".join(
            f"--- 第 {i + 1} 页 ---\n{t}" for i, t in enumerate(all_texts)
        )
    else:
        full_text = all_texts[0] if all_texts else ""

    return {"page_count": len(pages), "pages": pages, "full_text": full_text, "mode": "baidu_vl"}


def ocr_document_baidu_vl(file_path: str) -> dict:
    """
    使用百度 AI 云文档解析 API（PaddleOCR-VL-1.5）识别文档（图片或 PDF）。
    返回格式与 ocr_document() 一致。
    """
    import base64

    import requests as _requests

    token = _get_baidu_access_token()
    file_name = Path(file_path).name

    logger.info("百度 AI 文档解析：提交文件 %s", file_name)
    with open(file_path, "rb") as f:
        file_data = base64.b64encode(f.read()).decode("utf-8")

    submit_url = (
        "https://aip.baidubce.com/rest/2.0/brain/online/v2/paddle-vl-parser/task"
        f"?access_token={token}"
    )
    submit_resp = _requests.post(
        submit_url,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        data={
            "file_data": file_data,
            "file_name": file_name,
            "recognize_seal": "true",
            "return_span_boxes": "true",
            "analysis_chart": "true",
        },
        timeout=120,
    )
    submit_resp.raise_for_status()
    submit_data = submit_resp.json()

    error_code = submit_data.get("error_code")
    if error_code not in (0, "0", None, ""):
        raise RuntimeError(
            f"百度文档解析提交失败 ({error_code}): {submit_data.get('error_msg', '')}"
        )

    baidu_task_id = (submit_data.get("result") or {}).get("task_id")
    if not baidu_task_id:
        raise RuntimeError(f"百度文档解析未返回 task_id: {submit_data}")

    logger.info("百度任务已提交 task_id=%s，开始轮询结果...", baidu_task_id)
    query_url = (
        "https://aip.baidubce.com/rest/2.0/brain/online/v2/paddle-vl-parser/task/query"
        f"?access_token={token}"
    )

    for poll_idx in range(60):
        time.sleep(5)
        query_resp = _requests.post(
            query_url,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            data={"task_id": baidu_task_id},
            timeout=30,
        )
        query_resp.raise_for_status()
        query_data = query_resp.json()
        result = query_data.get("result") or {}
        status = result.get("status")
        logger.info(
            "百度任务 %s 状态: %s（轮询 %d/60）", baidu_task_id, status, poll_idx + 1
        )

        if status == "success":
            parse_result_url = result.get("parse_result_url")
            if not parse_result_url:
                raise RuntimeError("百度任务成功但未返回 parse_result_url")
            raw_resp = _requests.get(parse_result_url, timeout=60)
            raw_resp.raise_for_status()
            document = _map_baidu_result_to_document(raw_resp.json())
            document = _enrich_document_with_baidu_office_seals(document, file_path)
            return _enrich_document_with_detected_seals(document, file_path)

        if status == "failed":
            raise RuntimeError(
                f"百度文档解析任务失败: {result.get('task_error') or '未知错误'}"
            )

    raise RuntimeError(f"百度文档解析任务超时 (task_id={baidu_task_id})")


# ===== 统一文档识别入口 =====
def ocr_document(file_path: str, mode: str = "layout") -> dict:
    """
    对文档执行 OCR 识别（支持图片和 PDF）

    mode:
      - "vl":     PaddleOCR-VL-1.5 视觉语言模型（官网同款，识别质量最佳，推荐）
      - "layout": PP-StructureV3 版面解析（含表格识别）
      - "ocr":    PP-OCRv5 基础文字识别（快速，无版面分析）

    返回: {"page_count", "pages": [{page_num, regions?, lines}], "full_text", "mode"}
    """
    use_baidu = _should_use_baidu_vl_backend(mode)
    use_layout_api = _should_use_layout_api(mode)
    logger.info(
        "ocr_document 路由: mode=%s, OCR_LAYOUT_BACKEND=%s, use_layout_api=%s, OCR_VL_BACKEND=%s, use_baidu=%s",
        mode, OCR_LAYOUT_BACKEND, use_layout_api, OCR_VL_BACKEND, use_baidu,
    )
    if use_layout_api:
        if mode == "vl":
            mode_label = "vl_api"
        elif mode == "ocr":
            mode_label = "ocr_api"
        else:
            mode_label = "layout_api"
        return ocr_document_layout_api(file_path, mode_label=mode_label)
    if use_baidu:
        return ocr_document_baidu_vl(file_path)

    file_ext = Path(file_path).suffix.lower()
    pages = []
    temp_images = []

    # 选择识别函数
    if mode == "vl":
        recognize_fn = ocr_image_with_vl
    elif mode == "layout":
        recognize_fn = ocr_image_with_layout
    else:
        recognize_fn = ocr_image_basic

    max_pixels = MAX_IMAGE_PIXELS if mode == "ocr" else STRUCTURED_MAX_IMAGE_PIXELS

    try:
        if file_ext == ".pdf":
            image_paths = pdf_to_images(file_path)
            temp_images = image_paths
            for page_idx, img_path in enumerate(image_paths):
                resized_path = _maybe_resize_image(img_path, max_pixels=max_pixels)
                if resized_path != img_path:
                    temp_images.append(resized_path)
                page_result = recognize_fn(resized_path)
                page_result["page_num"] = page_idx + 1
                pages.append(page_result)
        else:
            resized_path = _maybe_resize_image(file_path, max_pixels=max_pixels)
            if resized_path != file_path:
                temp_images.append(resized_path)
            page_result = recognize_fn(resized_path)
            page_result["page_num"] = 1
            pages.append(page_result)

        # 拼接全文
        all_texts = []
        for page in pages:
            page_texts = []
            for region in page.get("regions", []):
                if region["type"] == "table":
                    page_texts.append("[表格]")
                elif region["content"]:
                    page_texts.append(region["content"])
            if not page_texts and page.get("lines"):
                page_texts = [line["text"] for line in page["lines"]]
            all_texts.append("\n".join(page_texts))

        if len(pages) > 1:
            full_text = "\n\n".join(
                f"--- 第 {i + 1} 页 ---\n{t}" for i, t in enumerate(all_texts)
            )
        else:
            full_text = all_texts[0] if all_texts else ""

        return {
            "page_count": len(pages),
            "pages": pages,
            "full_text": full_text,
            "mode": mode,
        }
    except Exception as exc:
        if mode == "layout" and _can_use_baidu_document_api() and _is_known_layout_runtime_error(exc):
            logger.warning(
                "PP-StructureV3 local layout failed for %s with a known runtime error. "
                "Falling back to Baidu document parsing.",
                Path(file_path).name,
                exc_info=True,
            )
            return ocr_document_baidu_vl(file_path)
        raise
    finally:
        for tmp in temp_images:
            try:
                Path(tmp).unlink(missing_ok=True)
            except Exception:
                pass


class OCRStrategyEngine:
    """Compatibility adapter used by the hierarchical agent workflow."""

    def __init__(self, *, mode: str = "layout", strategy: str = "none"):
        self.mode = str(mode or "layout")
        self.strategy = str(strategy or "none")

    def recognize_page(self, image_path: str) -> dict:
        from app.utils.image_preprocess import cleanup_preprocessed_image, preprocess_image

        processed_path = preprocess_image(image_path, self.strategy)
        try:
            if self.mode == "baidu_vl":
                document = ocr_document_baidu_vl(processed_path)
                pages = document.get("pages") or []
                return pages[0] if pages else {"page_num": 1, "regions": [], "lines": []}
            if self.mode == "vl":
                return ocr_image_with_vl(processed_path)
            if self.mode == "ocr":
                return ocr_image_basic(processed_path)
            return ocr_image_with_layout(processed_path)
        finally:
            cleanup_preprocessed_image(image_path, processed_path)


def get_ocr_engine(*, strategy: str = "none", mode: str = "layout") -> OCRStrategyEngine:
    """Return a strategy-aware single-page OCR engine adapter."""
    return OCRStrategyEngine(mode=mode, strategy=strategy)
