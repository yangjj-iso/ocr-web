"""Rebuild logical PDF files from sequential scanned images."""

from __future__ import annotations

import argparse
import logging
import math
import re
import statistics
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Iterable

from PIL import Image, ImageFile, ImageOps

try:
    import numpy as np
except ImportError:  # pragma: no cover - optional dependency
    np = None


logger = logging.getLogger(__name__)

ImageFile.LOAD_TRUNCATED_IMAGES = True

SUPPORTED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".tif", ".tiff", ".bmp"}
PAGE_SUFFIX_PATTERN = re.compile(r"^(?P<prefix>.+)-(?P<page>\d{3})$")

DEFAULT_SIMILARITY_THRESHOLD = 12
DEFAULT_TEXT_SIMILARITY_THRESHOLD = 0.35

HASH_SIZE = 8
HIGH_FREQ_FACTOR = 4
LAYOUT_CANVAS_SIZE = 192
LAYOUT_GRID_SIZE = 16
PROFILE_BINS = 16


@dataclass(slots=True)
class PageComparison:
    phash_distance: int
    layout_distance: int = 0
    profile_distance: float = 0.0
    text_similarity: float | None = None
    combined_change_score: float = 0.0
    should_split: bool = False
    split_reason: str = ""


@dataclass(slots=True)
class PageFingerprint:
    path: Path
    prefix: str
    page_no: int
    phash: int
    layout_hash: int = 0
    ink_ratio: float = 0.0
    row_profile: tuple[float, ...] = ()
    col_profile: tuple[float, ...] = ()
    text_signature: str = ""
    distance_from_previous: int | None = None
    comparison_from_previous: PageComparison | None = None


@dataclass(slots=True)
class PDFGroup:
    prefix: str
    pages: list[PageFingerprint]
    split_from_previous: PageComparison | None = None
    output_path: Path | None = None

    @property
    def start_page(self) -> int:
        return self.pages[0].page_no

    @property
    def end_page(self) -> int:
        return self.pages[-1].page_no

    @property
    def page_count(self) -> int:
        return len(self.pages)

    @property
    def suggested_filename(self) -> str:
        return f"{self.prefix}-{self.start_page:03d}-{self.end_page:03d}.pdf"


@dataclass(slots=True)
class RebuildSummary:
    groups: list[PDFGroup]
    total_pages: int
    similarity_threshold: int
    recommended_similarity_threshold: int | None = None
    used_auto_threshold: bool = False
    enable_ocr_text: bool = False
    text_similarity_threshold: float = DEFAULT_TEXT_SIMILARITY_THRESHOLD
    sequence_recommendations: dict[str, int] = field(default_factory=dict)
    report_path: Path | None = None
    warnings: list[str] = field(default_factory=list)


def parse_page_file(path: Path) -> tuple[str, int] | None:
    if path.suffix.lower() not in SUPPORTED_IMAGE_EXTENSIONS:
        return None
    match = PAGE_SUFFIX_PATTERN.match(path.stem)
    if not match:
        return None
    return match.group("prefix"), int(match.group("page"))


def _discover_sequences(input_dir: Path) -> tuple[dict[str, list[Path]], list[str]]:
    sequences: dict[str, list[Path]] = {}
    warnings: list[str] = []

    for path in sorted(input_dir.iterdir(), key=lambda item: item.name):
        if not path.is_file():
            continue
        parsed = parse_page_file(path)
        if parsed is None:
            continue
        prefix, page_no = parsed
        sequences.setdefault(prefix, [])
        duplicate = next((item for item in sequences[prefix] if parse_page_file(item)[1] == page_no), None)
        if duplicate is not None:
            raise ValueError(f"发现重复页码文件：{duplicate.name} 与 {path.name}")
        sequences[prefix].append(path)

    for prefix, paths in sequences.items():
        page_numbers = sorted(parse_page_file(path)[1] for path in paths)
        if not page_numbers:
            continue
        page_number_set = set(page_numbers)
        expected = list(range(page_numbers[0], page_numbers[-1] + 1))
        missing = [value for value in expected if value not in page_number_set]
        if missing:
            formatted = ", ".join(f"{value:03d}" for value in missing)
            warnings.append(f"{prefix}: 页码存在缺口 -> {formatted}")
        paths.sort(key=lambda item: parse_page_file(item)[1])

    return sequences, warnings


@lru_cache(maxsize=4)
def _dct_transform_matrix(size: int) -> tuple[tuple[float, ...], ...]:
    matrix: list[tuple[float, ...]] = []
    factor = math.pi / (2.0 * size)
    base = math.sqrt(1.0 / size)
    scale = math.sqrt(2.0 / size)
    for row in range(size):
        alpha = base if row == 0 else scale
        matrix.append(
            tuple(alpha * math.cos((2 * column + 1) * row * factor) for column in range(size))
        )
    return tuple(matrix)


def _to_grayscale_matrix(image: Image.Image, size: int) -> list[list[float]]:
    resized = image.convert("L").resize((size, size), Image.Resampling.LANCZOS)
    return [
        [float(resized.getpixel((column, row))) for column in range(size)]
        for row in range(size)
    ]


def _dct_2d(values: list[list[float]]) -> list[list[float]]:
    size = len(values)
    matrix = _dct_transform_matrix(size)

    if np is not None:
        transform = np.asarray(matrix, dtype=float)
        data = np.asarray(values, dtype=float)
        return (transform @ data @ transform.T).tolist()

    temp = [[0.0 for _ in range(size)] for _ in range(size)]
    for row in range(size):
        for col in range(size):
            temp[row][col] = sum(matrix[row][k] * values[k][col] for k in range(size))

    result = [[0.0 for _ in range(size)] for _ in range(size)]
    for row in range(size):
        for col in range(size):
            result[row][col] = sum(temp[row][k] * matrix[col][k] for k in range(size))
    return result


def _pad_to_square(image: Image.Image, *, fill: int = 255) -> Image.Image:
    width, height = image.size
    side = max(width, height)
    canvas = Image.new("L", (side, side), fill)
    canvas.paste(image, ((side - width) // 2, (side - height) // 2))
    return canvas


def _binarize_layout(image: Image.Image) -> tuple[list[list[int]], float]:
    normalized = _pad_to_square(ImageOps.autocontrast(image.convert("L")))
    resized = normalized.resize((LAYOUT_CANVAS_SIZE, LAYOUT_CANVAS_SIZE), Image.Resampling.LANCZOS)
    pixels = [
        [int(resized.getpixel((column, row))) for column in range(LAYOUT_CANVAS_SIZE)]
        for row in range(LAYOUT_CANVAS_SIZE)
    ]
    flattened = [value for row in pixels for value in row]
    median = statistics.median(flattened)
    threshold = min(238.0, max(110.0, median - 18.0))

    binary: list[list[int]] = []
    ink_count = 0
    for row in pixels:
        binary_row = []
        for value in row:
            bit = 1 if value < threshold else 0
            binary_row.append(bit)
            ink_count += bit
        binary.append(binary_row)

    ink_ratio = ink_count / float(LAYOUT_CANVAS_SIZE * LAYOUT_CANVAS_SIZE)
    return binary, round(ink_ratio, 6)


def _downsample_profile(values: list[float], bins: int) -> tuple[float, ...]:
    if not values:
        return ()
    if len(values) == bins:
        return tuple(round(value, 4) for value in values)

    bucket_size = len(values) / float(bins)
    downsampled: list[float] = []
    for bucket_index in range(bins):
        start = int(round(bucket_index * bucket_size))
        end = int(round((bucket_index + 1) * bucket_size))
        chunk = values[start:end] or [values[min(start, len(values) - 1)]]
        downsampled.append(round(sum(chunk) / len(chunk), 4))
    return tuple(downsampled)


def _compute_layout_signature(image_path: Path) -> tuple[int, tuple[float, ...], tuple[float, ...], float]:
    with Image.open(image_path) as image:
        binary, ink_ratio = _binarize_layout(image)

    canvas_size = len(binary)
    row_profile = _downsample_profile(
        [sum(row) / float(canvas_size) for row in binary],
        PROFILE_BINS,
    )
    col_profile = _downsample_profile(
        [sum(binary[row][col] for row in range(canvas_size)) / float(canvas_size) for col in range(canvas_size)],
        PROFILE_BINS,
    )

    cell_size = canvas_size // LAYOUT_GRID_SIZE
    cell_threshold = max(0.015, ink_ratio * 0.85)
    layout_hash = 0
    for grid_row in range(LAYOUT_GRID_SIZE):
        for grid_col in range(LAYOUT_GRID_SIZE):
            y0 = grid_row * cell_size
            y1 = y0 + cell_size
            x0 = grid_col * cell_size
            x1 = x0 + cell_size
            cell_total = cell_size * cell_size
            cell_ink = sum(binary[row][col] for row in range(y0, y1) for col in range(x0, x1))
            density = cell_ink / float(cell_total)
            layout_hash = (layout_hash << 1) | int(density > cell_threshold)

    return layout_hash, row_profile, col_profile, ink_ratio


def compute_phash(image_path: Path, *, hash_size: int = HASH_SIZE, high_freq_factor: int = HIGH_FREQ_FACTOR) -> int:
    sample_size = hash_size * high_freq_factor
    with Image.open(image_path) as image:
        dct = _dct_2d(_to_grayscale_matrix(image, sample_size))

    low_frequency = [dct[row][col] for row in range(hash_size) for col in range(hash_size)]
    median = statistics.median(low_frequency[1:] or low_frequency)
    value = 0
    for coefficient in low_frequency:
        value = (value << 1) | int(coefficient > median)
    return value


def hamming_distance(left: int, right: int) -> int:
    return (left ^ right).bit_count()


def _profile_distance(left: PageFingerprint, right: PageFingerprint) -> float:
    if not left.row_profile or not right.row_profile or not left.col_profile or not right.col_profile:
        return abs(left.ink_ratio - right.ink_ratio)

    row_gap = sum(abs(a - b) for a, b in zip(left.row_profile, right.row_profile)) / len(left.row_profile)
    col_gap = sum(abs(a - b) for a, b in zip(left.col_profile, right.col_profile)) / len(left.col_profile)
    return round((row_gap + col_gap + abs(left.ink_ratio - right.ink_ratio)) / 3.0, 4)


def _normalize_text_signature(value: str) -> str:
    buffer: list[str] = []
    for char in str(value or ""):
        if char.isalnum() or "\u4e00" <= char <= "\u9fff":
            buffer.append(char.lower())
    return "".join(buffer)


def _text_ngrams(value: str) -> set[str]:
    text = _normalize_text_signature(value)
    if not text:
        return set()
    gram_size = 2 if len(text) < 24 else 3
    if len(text) <= gram_size:
        return {text}
    return {text[index : index + gram_size] for index in range(len(text) - gram_size + 1)}


def compute_text_similarity(left: str, right: str) -> float | None:
    left_grams = _text_ngrams(left)
    right_grams = _text_ngrams(right)
    if not left_grams or not right_grams:
        return None
    intersection = len(left_grams & right_grams)
    union = len(left_grams | right_grams)
    if union == 0:
        return None
    return round(intersection / float(union), 4)


@lru_cache(maxsize=1)
def _get_basic_ocr_callable():
    from app.core.ocr_engine import ocr_image_basic

    return ocr_image_basic


def extract_text_signature(image_path: Path) -> str:
    try:
        ocr_callable = _get_basic_ocr_callable()
        result = ocr_callable(str(image_path))
    except Exception:
        logger.debug("OCR text assist unavailable for %s", image_path, exc_info=True)
        return ""

    lines = [str(line.get("text") or "").strip() for line in result.get("lines", []) if str(line.get("text") or "").strip()]
    if not lines:
        for region in result.get("regions", []):
            content = str(region.get("content") or "").strip()
            if content:
                lines.append(content)
    return _normalize_text_signature(" ".join(lines))[:3000]


def compare_page_fingerprints(previous: PageFingerprint, current: PageFingerprint) -> PageComparison:
    return PageComparison(
        phash_distance=hamming_distance(previous.phash, current.phash),
        layout_distance=hamming_distance(previous.layout_hash, current.layout_hash),
        profile_distance=_profile_distance(previous, current),
        text_similarity=compute_text_similarity(previous.text_signature, current.text_signature),
    )


def suggest_similarity_threshold(
    fingerprints: list[PageFingerprint],
    *,
    minimum: int = 8,
    maximum: int = 18,
) -> int:
    distances = sorted(
        int(fingerprint.distance_from_previous)
        for fingerprint in fingerprints[1:]
        if fingerprint.distance_from_previous is not None
    )
    if not distances:
        return DEFAULT_SIMILARITY_THRESHOLD

    if len(distances) == 1:
        suggestion = distances[0] + 2
        return max(minimum, min(maximum, suggestion))

    largest_gap = -1
    gap_index = -1
    for index in range(len(distances) - 1):
        gap = distances[index + 1] - distances[index]
        if gap > largest_gap:
            largest_gap = gap
            gap_index = index

    if largest_gap >= 3 and gap_index >= 0:
        lower = distances[gap_index]
        upper = distances[gap_index + 1]
        suggestion = int(round((lower + upper) / 2.0))
    else:
        median = statistics.median(distances)
        spread = statistics.pstdev(distances) if len(distances) > 1 else 0.0
        suggestion = int(round(median + max(2.0, spread * 1.25)))

    return max(minimum, min(maximum, suggestion))


def decide_page_split(
    comparison: PageComparison,
    *,
    similarity_threshold: int = DEFAULT_SIMILARITY_THRESHOLD,
    text_similarity_threshold: float = DEFAULT_TEXT_SIMILARITY_THRESHOLD,
) -> PageComparison:
    layout_threshold = max(similarity_threshold + 4, 12)
    profile_threshold = max(0.14, min(0.32, similarity_threshold / 40.0))

    phash_score = min(1.0, comparison.phash_distance / max(1.0, similarity_threshold * 1.75))
    layout_score = min(1.0, comparison.layout_distance / max(1.0, layout_threshold * 1.3))
    profile_score = min(1.0, comparison.profile_distance / max(0.01, profile_threshold * 1.25))
    text_score = 0.0
    if comparison.text_similarity is not None:
        text_score = 1.0 - comparison.text_similarity

    comparison.combined_change_score = round(
        (phash_score * 0.55) + (layout_score * 0.25) + (profile_score * 0.20) + (text_score * 0.15),
        4,
    )

    strong_phash_change = comparison.phash_distance > similarity_threshold
    strong_layout_change = comparison.layout_distance > layout_threshold
    strong_profile_change = comparison.profile_distance > profile_threshold
    strong_text_change = (
        comparison.text_similarity is not None
        and comparison.text_similarity < text_similarity_threshold
    )

    comparison.should_split = bool(
        strong_phash_change
        and (
            strong_layout_change
            or strong_profile_change
            or strong_text_change
            or comparison.combined_change_score >= 0.95
        )
    )

    metric_parts = [
        f"pHash={comparison.phash_distance}/{similarity_threshold}",
        f"layout={comparison.layout_distance}/{layout_threshold}",
        f"profile={comparison.profile_distance:.3f}/{profile_threshold:.3f}",
    ]
    if comparison.text_similarity is not None:
        metric_parts.append(
            f"text={comparison.text_similarity:.2f}/{text_similarity_threshold:.2f}"
        )
    metric_parts.append(f"score={comparison.combined_change_score:.2f}")
    comparison.split_reason = (
        ("切分新文件: " if comparison.should_split else "保持同组: ")
        + ", ".join(metric_parts)
    )
    return comparison


def build_fingerprints(
    paths: Iterable[Path],
    *,
    enable_ocr_text: bool = False,
) -> list[PageFingerprint]:
    fingerprints: list[PageFingerprint] = []
    previous: PageFingerprint | None = None
    for path in paths:
        prefix, page_no = parse_page_file(path)
        layout_hash, row_profile, col_profile, ink_ratio = _compute_layout_signature(path)
        fingerprint = PageFingerprint(
            path=path,
            prefix=prefix,
            page_no=page_no,
            phash=compute_phash(path),
            layout_hash=layout_hash,
            ink_ratio=ink_ratio,
            row_profile=row_profile,
            col_profile=col_profile,
            text_signature=extract_text_signature(path) if enable_ocr_text else "",
        )
        if previous is not None:
            comparison = compare_page_fingerprints(previous, fingerprint)
            fingerprint.distance_from_previous = comparison.phash_distance
            fingerprint.comparison_from_previous = comparison
        fingerprints.append(fingerprint)
        previous = fingerprint
    return fingerprints


def group_pages_by_similarity(
    fingerprints: list[PageFingerprint],
    *,
    similarity_threshold: int = DEFAULT_SIMILARITY_THRESHOLD,
    text_similarity_threshold: float = DEFAULT_TEXT_SIMILARITY_THRESHOLD,
) -> list[PDFGroup]:
    if not fingerprints:
        return []

    groups: list[PDFGroup] = []
    current_pages = [fingerprints[0]]
    current_group_split: PageComparison | None = None

    for fingerprint in fingerprints[1:]:
        comparison = fingerprint.comparison_from_previous
        if comparison is not None:
            comparison = decide_page_split(
                comparison,
                similarity_threshold=similarity_threshold,
                text_similarity_threshold=text_similarity_threshold,
            )
            fingerprint.comparison_from_previous = comparison
            should_split = comparison.should_split
        else:
            should_split = (fingerprint.distance_from_previous or 0) > similarity_threshold
            comparison = PageComparison(
                phash_distance=int(fingerprint.distance_from_previous or 0),
                should_split=should_split,
                split_reason=f"pHash={int(fingerprint.distance_from_previous or 0)}/{similarity_threshold}",
            )

        if should_split:
            groups.append(
                PDFGroup(
                    prefix=current_pages[0].prefix,
                    pages=current_pages,
                    split_from_previous=current_group_split,
                )
            )
            current_pages = [fingerprint]
            current_group_split = comparison
        else:
            current_pages.append(fingerprint)

    groups.append(
        PDFGroup(
            prefix=current_pages[0].prefix,
            pages=current_pages,
            split_from_previous=current_group_split,
        )
    )
    return groups


def _prepare_pdf_image(image: Image.Image) -> Image.Image:
    if image.mode in {"RGBA", "LA"} or (image.mode == "P" and "transparency" in image.info):
        background = Image.new("RGBA", image.size, (255, 255, 255, 255))
        return Image.alpha_composite(background, image.convert("RGBA")).convert("RGB")
    return image.convert("RGB")


def save_group_as_pdf(group: PDFGroup, output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / group.suggested_filename

    converted_images: list[Image.Image] = []
    try:
        for page in group.pages:
            with Image.open(page.path) as image:
                converted_images.append(_prepare_pdf_image(image).copy())
        if not converted_images:
            raise ValueError("当前分组没有可写入 PDF 的图片。")
        if output_path.exists():
            output_path.unlink()
        first, *rest = converted_images
        first.save(output_path, "PDF", save_all=True, append_images=rest, resolution=200.0)
    finally:
        for image in converted_images:
            image.close()

    group.output_path = output_path
    return output_path


def build_summary_report(summary: RebuildSummary) -> dict:
    transitions = []
    for group in summary.groups:
        for page in group.pages:
            comparison = page.comparison_from_previous
            if comparison is None:
                continue
            transitions.append(
                {
                    "prefix": page.prefix,
                    "from_page": page.page_no - 1,
                    "to_page": page.page_no,
                    "phash_distance": comparison.phash_distance,
                    "layout_distance": comparison.layout_distance,
                    "profile_distance": comparison.profile_distance,
                    "text_similarity": comparison.text_similarity,
                    "combined_change_score": comparison.combined_change_score,
                    "should_split": comparison.should_split,
                    "split_reason": comparison.split_reason,
                }
            )

    group_payload = []
    for group in summary.groups:
        group_payload.append(
            {
                "prefix": group.prefix,
                "start_page": group.start_page,
                "end_page": group.end_page,
                "page_count": group.page_count,
                "suggested_filename": group.suggested_filename,
                "output_path": str(group.output_path) if group.output_path else "",
                "pages": [page.path.name for page in group.pages],
                "split_from_previous": (
                    {
                        "phash_distance": group.split_from_previous.phash_distance,
                        "layout_distance": group.split_from_previous.layout_distance,
                        "profile_distance": group.split_from_previous.profile_distance,
                        "text_similarity": group.split_from_previous.text_similarity,
                        "combined_change_score": group.split_from_previous.combined_change_score,
                        "split_reason": group.split_from_previous.split_reason,
                    }
                    if group.split_from_previous is not None
                    else None
                ),
            }
        )

    return {
        "total_files": len(summary.groups),
        "total_pages": summary.total_pages,
        "similarity_threshold": summary.similarity_threshold,
        "recommended_similarity_threshold": summary.recommended_similarity_threshold,
        "used_auto_threshold": summary.used_auto_threshold,
        "enable_ocr_text": summary.enable_ocr_text,
        "text_similarity_threshold": summary.text_similarity_threshold,
        "sequence_recommendations": summary.sequence_recommendations,
        "groups": group_payload,
        "transitions": transitions,
        "warnings": summary.warnings,
    }


def write_summary_report(summary: RebuildSummary, output_path: str | Path) -> Path:
    import json

    target = Path(output_path).expanduser().resolve(strict=False)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(build_summary_report(summary), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    summary.report_path = target
    return target


def rebuild_pdfs_from_images(
    input_dir: str | Path,
    *,
    output_dir: str | Path | None = None,
    similarity_threshold: int = DEFAULT_SIMILARITY_THRESHOLD,
    auto_threshold: bool = False,
    enable_ocr_text: bool = False,
    text_similarity_threshold: float = DEFAULT_TEXT_SIMILARITY_THRESHOLD,
    report_json: str | Path | None = None,
    dry_run: bool = False,
) -> RebuildSummary:
    source_dir = Path(input_dir).expanduser().resolve(strict=True)
    target_dir = (
        Path(output_dir).expanduser().resolve(strict=False)
        if output_dir
        else (source_dir / "rebuilt_pdfs").resolve(strict=False)
    )

    sequences, warnings = _discover_sequences(source_dir)
    if not sequences:
        raise FileNotFoundError(
            f"目录 {source_dir} 中没有找到符合 `前缀-页码.扩展名` 规则的图片文件。"
        )

    sequence_fingerprints: dict[str, list[PageFingerprint]] = {}
    sequence_recommendations: dict[str, int] = {}
    for prefix in sorted(sequences):
        fingerprints = build_fingerprints(
            sequences[prefix],
            enable_ocr_text=enable_ocr_text,
        )
        sequence_fingerprints[prefix] = fingerprints
        sequence_recommendations[prefix] = suggest_similarity_threshold(fingerprints)

    recommended_threshold = None
    if sequence_recommendations:
        recommended_threshold = int(
            round(statistics.median(sequence_recommendations.values()))
        )

    effective_threshold = recommended_threshold if (auto_threshold and recommended_threshold is not None) else similarity_threshold
    if auto_threshold and len(set(sequence_recommendations.values())) > 1:
        warnings.append(
            "不同前缀序列的建议阈值存在差异，已使用中位数作为全局阈值。"
        )

    groups: list[PDFGroup] = []
    for prefix in sorted(sequences):
        fingerprints = sequence_fingerprints[prefix]
        groups.extend(
            group_pages_by_similarity(
                fingerprints,
                similarity_threshold=effective_threshold,
                text_similarity_threshold=text_similarity_threshold,
            )
        )

    if not dry_run:
        for group in groups:
            save_group_as_pdf(group, target_dir)

    summary = RebuildSummary(
        groups=groups,
        total_pages=sum(group.page_count for group in groups),
        similarity_threshold=effective_threshold,
        recommended_similarity_threshold=recommended_threshold,
        used_auto_threshold=auto_threshold and recommended_threshold is not None,
        enable_ocr_text=enable_ocr_text,
        text_similarity_threshold=text_similarity_threshold,
        sequence_recommendations=sequence_recommendations,
        warnings=warnings,
    )
    if report_json:
        write_summary_report(summary, report_json)
    return summary


def format_summary(summary: RebuildSummary) -> str:
    lines = [
        f"共识别出 {len(summary.groups)} 个文件，覆盖 {summary.total_pages} 页。",
        f"similarity_threshold = {summary.similarity_threshold}",
        f"自动阈值 = {'开启' if summary.used_auto_threshold else '关闭'}",
        f"OCR 文本辅助 = {'开启' if summary.enable_ocr_text else '关闭'}",
    ]
    if summary.recommended_similarity_threshold is not None:
        lines.append(f"建议阈值 = {summary.recommended_similarity_threshold}")
    if summary.enable_ocr_text:
        lines.append(f"text_similarity_threshold = {summary.text_similarity_threshold:.2f}")
    if summary.sequence_recommendations:
        sequence_summary = ", ".join(
            f"{prefix}:{threshold}"
            for prefix, threshold in sorted(summary.sequence_recommendations.items())
        )
        lines.append(f"序列建议阈值 = {sequence_summary}")

    for index, group in enumerate(summary.groups, start=1):
        filename = group.output_path.name if group.output_path else group.suggested_filename
        lines.append(
            f"{index:02d}. {filename} | 页码 {group.start_page:03d}-{group.end_page:03d} | {group.page_count} 页"
        )
        if group.split_from_previous is not None:
            lines.append(f"    {group.split_from_previous.split_reason}")

    if summary.report_path is not None:
        lines.append(f"报告文件: {summary.report_path}")
    for warning in summary.warnings:
        lines.append(f"警告: {warning}")
    return "\n".join(lines)


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="按相邻页 pHash 差异自动切分扫描图片，并重建多个独立 PDF。",
    )
    parser.add_argument("input_dir", help="图片所在目录")
    parser.add_argument(
        "--output-dir",
        default="",
        help="PDF 输出目录，默认写入 input_dir/rebuilt_pdfs",
    )
    parser.add_argument(
        "--similarity-threshold",
        type=int,
        default=DEFAULT_SIMILARITY_THRESHOLD,
        help="相邻页 pHash Hamming 距离阈值。默认 12，越大越宽松，越小越严格。",
    )
    parser.add_argument(
        "--auto-threshold",
        action="store_true",
        help="根据当前图片序列的相邻页差异自动建议并使用阈值。",
    )
    parser.add_argument(
        "--enable-ocr-text",
        action="store_true",
        help="额外启用 OCR 文本辅助比较，准确率更高但会更慢。",
    )
    parser.add_argument(
        "--text-similarity-threshold",
        type=float,
        default=DEFAULT_TEXT_SIMILARITY_THRESHOLD,
        help="OCR 文本相似度阈值，默认 0.35，越小越宽松。",
    )
    parser.add_argument(
        "--report-json",
        default="",
        help="将切分结果和页间比较指标写入 JSON 报告文件。",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="只打印分组结果，不实际生成 PDF。",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    summary = rebuild_pdfs_from_images(
        args.input_dir,
        output_dir=args.output_dir or None,
        similarity_threshold=args.similarity_threshold,
        auto_threshold=args.auto_threshold,
        enable_ocr_text=args.enable_ocr_text,
        text_similarity_threshold=args.text_similarity_threshold,
        report_json=args.report_json or None,
        dry_run=args.dry_run,
    )
    print(format_summary(summary))
    return 0


__all__ = [
    "DEFAULT_SIMILARITY_THRESHOLD",
    "DEFAULT_TEXT_SIMILARITY_THRESHOLD",
    "PDFGroup",
    "PageComparison",
    "PageFingerprint",
    "RebuildSummary",
    "build_fingerprints",
    "build_arg_parser",
    "build_summary_report",
    "compare_page_fingerprints",
    "compute_phash",
    "compute_text_similarity",
    "decide_page_split",
    "extract_text_signature",
    "format_summary",
    "group_pages_by_similarity",
    "hamming_distance",
    "main",
    "parse_page_file",
    "rebuild_pdfs_from_images",
    "save_group_as_pdf",
    "suggest_similarity_threshold",
    "write_summary_report",
]
