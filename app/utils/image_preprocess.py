"""Image preprocessing helpers used by the hierarchical OCR workflow."""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path
from typing import Literal

from PIL import Image, ImageEnhance, ImageFilter, ImageOps

try:
    import cv2
except ImportError:  # pragma: no cover - optional dependency
    cv2 = None

try:
    import numpy as np
except ImportError:  # pragma: no cover - optional dependency
    np = None


ProcessingStrategy = Literal[
    "none",
    "opencv_document",
    "enhance_contrast",
    "crop_and_zoom",
    "deskew",
    "denoise",
    "sharpen",
]

MAX_PREPROCESS_DIM = 2500
_LANCZOS = getattr(getattr(Image, "Resampling", Image), "LANCZOS")


def _temp_image_path(source_path: str | Path, suffix: str | None = None) -> str:
    source = Path(source_path)
    handle = tempfile.NamedTemporaryFile(
        prefix=f"ocr-pre-{source.stem[:16]}-",
        suffix=suffix or source.suffix or ".png",
        delete=False,
    )
    handle.close()
    return handle.name


def _load_image_for_preprocess(source_path: str | Path) -> Image.Image:
    source = Path(source_path)
    if cv2 is not None and np is not None:
        data = np.fromfile(str(source), dtype=np.uint8)
        if data.size > 0:
            decoded = cv2.imdecode(data, cv2.IMREAD_COLOR)
            if decoded is not None:
                rgb = cv2.cvtColor(decoded, cv2.COLOR_BGR2RGB)
                return Image.fromarray(rgb)

    with Image.open(source) as raw_image:
        return ImageOps.exif_transpose(raw_image).convert("RGB")


def _save_image_for_preprocess(image: Image.Image, output_path: str | Path) -> None:
    target = Path(output_path)
    if cv2 is not None and np is not None:
        rgb = np.array(image.convert("RGB"))
        bgr = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
        suffix = target.suffix or ".png"
        ok, buf = cv2.imencode(suffix, bgr)
        if ok:
            buf.tofile(str(target))
            return
    image.save(target, format="PNG")


def _resize_if_needed(image: Image.Image, max_dim: int = MAX_PREPROCESS_DIM) -> tuple[Image.Image, bool]:
    width, height = image.size
    longest_edge = max(width, height)
    if longest_edge <= max_dim:
        return image, False

    scale = max_dim / float(longest_edge)
    resized = image.resize(
        (max(1, int(round(width * scale))), max(1, int(round(height * scale)))),
        _LANCZOS,
    )
    return resized, True


def _deskew_with_cv(image: Image.Image) -> Image.Image:
    if cv2 is None or np is None:
        return image

    grayscale = np.array(image.convert("L"))
    _, threshold = cv2.threshold(grayscale, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    coordinates = np.column_stack(np.where(threshold > 0))
    if len(coordinates) < 10:
        return image

    angle = cv2.minAreaRect(coordinates)[-1]
    if angle < -45:
        angle = -(90 + angle)
    else:
        angle = -angle

    if abs(angle) < 0.3:
        return image

    return image.rotate(angle, expand=True, fillcolor="white")


def _estimate_skew_angle(grayscale) -> float:
    if cv2 is None or np is None:
        return 0.0

    blurred = cv2.GaussianBlur(grayscale, (3, 3), 0)
    _, threshold = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    coordinates = np.column_stack(np.where(threshold > 0))
    if len(coordinates) < 10:
        return 0.0

    angle = cv2.minAreaRect(coordinates)[-1]
    if angle < -45:
        angle = -(90 + angle)
    else:
        angle = -angle
    return float(angle)


def _rotate_grayscale_with_cv(grayscale, angle: float):
    if cv2 is None or np is None or abs(angle) < 0.3:
        return grayscale

    height, width = grayscale.shape[:2]
    center = (width / 2.0, height / 2.0)
    matrix = cv2.getRotationMatrix2D(center, angle, 1.0)
    cos = abs(matrix[0, 0])
    sin = abs(matrix[0, 1])
    bound_w = int((height * sin) + (width * cos))
    bound_h = int((height * cos) + (width * sin))

    matrix[0, 2] += (bound_w / 2.0) - center[0]
    matrix[1, 2] += (bound_h / 2.0) - center[1]
    return cv2.warpAffine(
        grayscale,
        matrix,
        (bound_w, bound_h),
        flags=cv2.INTER_CUBIC,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=255,
    )


def _opencv_document_preprocess(image: Image.Image) -> Image.Image:
    if cv2 is None or np is None:
        image = ImageEnhance.Contrast(image).enhance(1.65)
        image = image.filter(ImageFilter.MedianFilter(size=3))
        return _deskew_with_cv(image)

    grayscale = np.array(image.convert("L"))
    clahe = cv2.createCLAHE(clipLimit=2.4, tileGridSize=(8, 8))
    contrast_enhanced = clahe.apply(grayscale)
    denoised = cv2.medianBlur(contrast_enhanced, 3)
    angle = _estimate_skew_angle(denoised)
    corrected = _rotate_grayscale_with_cv(denoised, angle)
    return Image.fromarray(corrected).convert("RGB")


def preprocess_image(image_path: str | Path, strategy: str = "none") -> str:
    """Apply a lightweight preprocessing strategy and return a derived file path."""
    source = Path(image_path)
    normalized = str(strategy or "none").strip().lower() or "none"
    image = _load_image_for_preprocess(source)
    image, resized = _resize_if_needed(image)
    transformed = resized

    if normalized == "opencv_document":
        image = _opencv_document_preprocess(image)
        transformed = True
    elif normalized == "enhance_contrast":
        image = ImageEnhance.Contrast(image).enhance(1.65)
        image = ImageEnhance.Sharpness(image).enhance(1.2)
        transformed = True
    elif normalized == "crop_and_zoom":
        width, height = image.size
        margin_x = max(int(width * 0.04), 8)
        margin_y = max(int(height * 0.04), 8)
        image = image.crop((margin_x, margin_y, width - margin_x, height - margin_y))
        image = image.resize((image.width * 2, image.height * 2))
        transformed = True
    elif normalized == "deskew":
        image = _deskew_with_cv(image)
        transformed = True
    elif normalized == "denoise":
        image = image.filter(ImageFilter.MedianFilter(size=3))
        transformed = True
    elif normalized == "sharpen":
        image = ImageEnhance.Sharpness(image).enhance(1.8)
        transformed = True
    elif normalized != "none":
        return str(source)

    if not transformed:
        return str(source)

    output_path = _temp_image_path(source, suffix=".png")
    _save_image_for_preprocess(image, output_path)
    return output_path


def cleanup_preprocessed_image(original_path: str | Path, processed_path: str | Path) -> None:
    original = Path(original_path)
    processed = Path(processed_path)
    if processed.resolve(strict=False) == original.resolve(strict=False):
        return
    processed.unlink(missing_ok=True)


def clone_to_temp_image(image_path: str | Path) -> str:
    source = Path(image_path)
    target = _temp_image_path(source)
    shutil.copyfile(source, target)
    return target
