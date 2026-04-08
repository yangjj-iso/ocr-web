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
    "enhance_contrast",
    "crop_and_zoom",
    "deskew",
    "denoise",
    "sharpen",
]


def _temp_image_path(source_path: str | Path, suffix: str | None = None) -> str:
    source = Path(source_path)
    handle = tempfile.NamedTemporaryFile(
        prefix=f"ocr-pre-{source.stem[:16]}-",
        suffix=suffix or source.suffix or ".png",
        delete=False,
    )
    handle.close()
    return handle.name


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


def preprocess_image(image_path: str | Path, strategy: str = "none") -> str:
    """Apply a lightweight preprocessing strategy and return a derived file path."""
    source = Path(image_path)
    normalized = str(strategy or "none").strip().lower() or "none"
    if normalized == "none":
        return str(source)

    with Image.open(source) as raw_image:
        image = ImageOps.exif_transpose(raw_image).convert("RGB")

        if normalized == "enhance_contrast":
            image = ImageEnhance.Contrast(image).enhance(1.65)
            image = ImageEnhance.Sharpness(image).enhance(1.2)
        elif normalized == "crop_and_zoom":
            width, height = image.size
            margin_x = max(int(width * 0.04), 8)
            margin_y = max(int(height * 0.04), 8)
            image = image.crop((margin_x, margin_y, width - margin_x, height - margin_y))
            image = image.resize((image.width * 2, image.height * 2))
        elif normalized == "deskew":
            image = _deskew_with_cv(image)
        elif normalized == "denoise":
            image = image.filter(ImageFilter.MedianFilter(size=3))
        elif normalized == "sharpen":
            image = ImageEnhance.Sharpness(image).enhance(1.8)
        else:
            return str(source)

        output_path = _temp_image_path(source, suffix=".png")
        image.save(output_path, format="PNG")
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
