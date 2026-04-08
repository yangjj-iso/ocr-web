from html.parser import HTMLParser
from typing import Any


class ResultValidationError(ValueError):
    pass


class _TableHTMLParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.rows: list[list[str]] = []
        self._current_row: list[str] | None = None
        self._current_cell: list[str] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "tr":
            self._current_row = []
        elif tag in {"td", "th"}:
            if self._current_row is None:
                self._current_row = []
            self._current_cell = []
        elif tag == "br" and self._current_cell is not None:
            self._current_cell.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in {"td", "th"} and self._current_row is not None and self._current_cell is not None:
            self._current_row.append(_clean_text("".join(self._current_cell)))
            self._current_cell = None
        elif tag == "tr":
            if self._current_row is not None and self._current_row:
                self.rows.append(self._current_row)
            self._current_row = None

    def handle_data(self, data: str) -> None:
        if self._current_cell is not None:
            self._current_cell.append(data)


def _clean_text(value: Any) -> str:
    text = str(value or "")
    return text.replace("\x00", "").strip()


def _normalize_metadata(value: Any, depth: int = 0) -> Any:
    if depth > 5:
        return None
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value
    if isinstance(value, str):
        return _clean_text(value)
    if isinstance(value, list):
        normalized = [_normalize_metadata(item, depth + 1) for item in value]
        return [item for item in normalized if item is not None]
    if isinstance(value, dict):
        normalized: dict[str, Any] = {}
        for key, item in value.items():
            child = _normalize_metadata(item, depth + 1)
            if child is None:
                continue
            normalized[str(key)] = child
        return normalized
    return _clean_text(value)


def _compact_for_compare(value: Any) -> str:
    return "".join(_clean_text(value).split())


def normalize_table_data(raw_table: Any) -> list[list[str]]:
    if raw_table is None:
        return [[""]]
    if not isinstance(raw_table, list):
        raise ResultValidationError("table_data must be a list of rows.")

    rows: list[list[str]] = []
    for row in raw_table:
        if isinstance(row, (list, tuple)):
            rows.append([_clean_text(cell) for cell in row])
        else:
            rows.append([_clean_text(row)])

    return rows or [[""]]


def table_html_to_data(html: str) -> list[list[str]]:
    parser = _TableHTMLParser()
    parser.feed(html or "")
    return normalize_table_data(parser.rows)


def table_data_to_text(table_data: list[list[str]]) -> str:
    lines = []
    for row in table_data:
        cleaned = [_clean_text(cell) for cell in row]
        if any(cleaned):
            lines.append("\t".join(cleaned))
    return "\n".join(lines)


def _table_data_matches_html(table_data: list[list[str]], html: str) -> bool:
    try:
        html_rows = table_html_to_data(html)
    except Exception:
        return False
    return normalize_table_data(table_data) == normalize_table_data(html_rows)


def _normalize_bbox(raw_bbox: Any) -> tuple[Any, str]:
    if not raw_bbox:
        return [], "rect"

    if isinstance(raw_bbox, list) and raw_bbox and isinstance(raw_bbox[0], (list, tuple)):
        normalized = []
        for point in raw_bbox:
            if len(point) < 2:
                continue
            normalized.append([float(point[0]), float(point[1])])
        return normalized, "poly"

    if isinstance(raw_bbox, list) and len(raw_bbox) >= 4:
        return [float(raw_bbox[0]), float(raw_bbox[1]), float(raw_bbox[2]), float(raw_bbox[3])], "rect"

    raise ResultValidationError("Invalid bbox payload.")


def _normalize_region(region: Any) -> dict[str, Any]:
    if not isinstance(region, dict):
        raise ResultValidationError("Each region must be an object.")

    bbox, bbox_type = _normalize_bbox(region.get("bbox", []))
    layout_bbox, _ = _normalize_bbox(region.get("layout_bbox", region.get("bbox", [])))
    region_type = _clean_text(region.get("type", "text")) or "text"
    content = _clean_text(region.get("content", ""))
    region_lines = _normalize_region_lines(region.get("region_lines"))

    # When manual edits update `content` but stale OCR line fragments remain,
    # prefer the edited content and drop mismatched line fragments.
    if region_type != "table" and content and region_lines:
        lines_text = "\n".join(_clean_text(line.get("text", "")) for line in region_lines if _clean_text(line.get("text", "")))
        if _compact_for_compare(lines_text) and _compact_for_compare(lines_text) != _compact_for_compare(content):
            region_lines = []

    normalized: dict[str, Any] = {
        "type": region_type,
        "bbox": bbox,
        "bbox_type": region.get("bbox_type", bbox_type) if bbox else bbox_type,
        "layout_bbox": layout_bbox if layout_bbox else bbox,
        "content": content,
    }

    if region_lines:
        normalized["region_lines"] = region_lines

    if region_type == "table":
        raw_table = region.get("table_data")
        html = str(region.get("html") or "").strip()
        if raw_table is None and html:
            raw_table = table_html_to_data(html)
        table_data = normalize_table_data(raw_table)
        normalized["table_data"] = table_data
        normalized["content"] = table_data_to_text(table_data)
        if html and _table_data_matches_html(table_data, html):
            normalized["html"] = html

    metadata = _normalize_metadata(region.get("agent_meta"))
    if isinstance(metadata, dict) and metadata:
        normalized["agent_meta"] = metadata

    return normalized


def _normalize_region_lines(raw_lines: Any) -> list[dict[str, Any]]:
    if not isinstance(raw_lines, list):
        return []
    return [_normalize_line(line, index) for index, line in enumerate(raw_lines) if isinstance(line, dict)]


def _normalize_line(line: Any, index: int) -> dict[str, Any]:
    if not isinstance(line, dict):
        raise ResultValidationError("Each line must be an object.")
    bbox, bbox_type = _normalize_bbox(line.get("bbox", []))
    confidence = line.get("confidence", 0.0)
    try:
        confidence_value = float(confidence)
    except (TypeError, ValueError):
        confidence_value = 0.0

    return {
        "line_num": int(line.get("line_num", index + 1)),
        "text": _clean_text(line.get("text", "")),
        "confidence": round(confidence_value, 4),
        "bbox": bbox,
        "bbox_type": bbox_type,
    }


def normalize_result_pages(raw_pages: Any) -> list[dict[str, Any]]:
    pages = raw_pages if isinstance(raw_pages, list) else [raw_pages]
    normalized_pages: list[dict[str, Any]] = []
    for index, page in enumerate(pages):
        if not isinstance(page, dict):
            raise ResultValidationError("Each page must be an object.")
        normalized_pages.append(
            {
                "page_num": int(page.get("page_num", index + 1)),
                "regions": [_normalize_region(region) for region in page.get("regions", [])],
                "lines": [_normalize_line(line, line_index) for line_index, line in enumerate(page.get("lines", []))],
            }
        )
        metadata = _normalize_metadata(page.get("agent_meta"))
        if isinstance(metadata, dict) and metadata:
            normalized_pages[-1]["agent_meta"] = metadata
    return normalized_pages


def serialize_pages_text(pages: list[dict[str, Any]]) -> str:
    chunks: list[str] = []
    for index, page in enumerate(pages, start=1):
        page_lines: list[str] = []
        for region in page.get("regions", []):
            content = _clean_text(region.get("content", ""))
            if content:
                page_lines.append(content)
        if not page_lines:
            for line in page.get("lines", []):
                text = _clean_text(line.get("text", ""))
                if text:
                    page_lines.append(text)
        page_text = "\n".join(page_lines).strip()
        if page_text:
            chunks.append(f"--- Page {index} ---\n{page_text}" if len(pages) > 1 else page_text)
    return "\n\n".join(chunks).strip()
