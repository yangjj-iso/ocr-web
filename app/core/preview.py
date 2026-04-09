from io import BytesIO
from pathlib import Path

from PIL import Image, ImageDraw, ImageOps

try:
    import numpy as np
except ImportError:  # pragma: no cover - environment dependent
    np = None

try:
    import fitz  # type: ignore[import-not-found]
except ImportError:  # pragma: no cover - environment dependent
    fitz = None


def _placeholder_thumbnail(path: Path, max_size: tuple[int, int]) -> Image.Image:
    image = Image.new("RGB", max_size, color=(243, 244, 246))
    draw = ImageDraw.Draw(image)
    ext = path.suffix.lower().lstrip(".").upper() or "FILE"
    draw.rectangle((12, 12, max_size[0] - 12, max_size[1] - 12), outline=(148, 163, 184), width=2)
    draw.text((24, 24), ext, fill=(31, 41, 55))
    draw.text((24, 56), "Preview unavailable", fill=(75, 85, 99))
    return image


def _pdf_thumbnail(path: Path) -> Image.Image:
    if fitz is None:
        raise RuntimeError("PyMuPDF is not installed.")

    document = fitz.open(path)
    try:
        page = document.load_page(0)
        pix = page.get_pixmap(matrix=fitz.Matrix(1.2, 1.2), alpha=False)
        return Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
    finally:
        document.close()


def _pdf_page_image(path: Path, page_num: int, scale: float = 2.0) -> Image.Image:
    if fitz is None:
        raise RuntimeError("PyMuPDF is not installed.")

    page_index = max(0, int(page_num) - 1)
    document = fitz.open(path)
    try:
        if page_index >= document.page_count:
            raise IndexError("PDF page index out of range.")
        page = document.load_page(page_index)
        pix = page.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False)
        return Image.frombytes("RGB", [pix.width, pix.height], pix.samples).convert("RGBA")
    finally:
        document.close()


def _open_preview_image(path: Path, page_num: int = 1, scale: float = 2.0) -> Image.Image:
    if path.suffix.lower() == ".pdf":
        return _pdf_page_image(path, page_num, scale=scale)
    if page_num != 1:
        raise IndexError("Image file contains only one page.")
    image = Image.open(path)
    image = ImageOps.exif_transpose(image)
    return image.convert("RGBA")


def _rect_from_bbox(bbox: list | tuple) -> list[float]:
    if isinstance(bbox, (list, tuple)) and len(bbox) >= 4 and not isinstance(bbox[0], (list, tuple)):
        return [float(bbox[0]), float(bbox[1]), float(bbox[2]), float(bbox[3])]
    if isinstance(bbox, (list, tuple)) and bbox and isinstance(bbox[0], (list, tuple)):
        xs = [float(point[0]) for point in bbox if isinstance(point, (list, tuple)) and len(point) >= 2]
        ys = [float(point[1]) for point in bbox if isinstance(point, (list, tuple)) and len(point) >= 2]
        if xs and ys:
            return [min(xs), min(ys), max(xs), max(ys)]
    return []


def _crop_box_from_bbox(
    bbox: list | tuple,
    image_size: tuple[int, int],
    *,
    padding_ratio: float = 0.08,
) -> tuple[int, int, int, int]:
    rect = _rect_from_bbox(bbox)
    if len(rect) < 4:
        raise ValueError("Region bbox is missing or invalid.")

    image_width, image_height = image_size
    x1, y1, x2, y2 = rect
    if x2 <= x1 or y2 <= y1:
        raise ValueError("Region bbox is missing or invalid.")

    rect_width = max(1.0, x2 - x1)
    rect_height = max(1.0, y2 - y1)
    padding_x = max(4.0, rect_width * padding_ratio)
    padding_y = max(4.0, rect_height * padding_ratio)

    left = max(0, int(round(x1 - padding_x)))
    top = max(0, int(round(y1 - padding_y)))
    right = min(image_width, int(round(x2 + padding_x)))
    bottom = min(image_height, int(round(y2 + padding_y)))

    if right <= left or bottom <= top:
        raise ValueError("Region bbox is outside the preview image.")
    return left, top, right, bottom


def _isolate_red_foreground(image: Image.Image) -> Image.Image:
    rgba = image.convert("RGBA")
    if np is None:
        return rgba

    pixels = np.array(rgba, dtype=np.uint8)
    if pixels.size == 0:
        return rgba

    red = pixels[:, :, 0].astype(np.int16)
    green = pixels[:, :, 1].astype(np.int16)
    blue = pixels[:, :, 2].astype(np.int16)

    dominant_red = red >= 72
    red_bias = red - np.maximum(green, blue) >= 18
    warm_red = (red >= 92) & (red >= green + 10) & (red >= blue + 10)
    mask = dominant_red & (red_bias | warm_red)

    if int(mask.sum()) < max(36, int(mask.size * 0.008)):
        return rgba

    pixels[:, :, 3] = np.where(mask, 255, 0).astype(np.uint8)
    return Image.fromarray(pixels, mode="RGBA")


def build_pdf_page_preview(file_path: str | Path, page_num: int, scale: float = 2.0) -> bytes:
    path = Path(file_path)
    image = _pdf_page_image(path, page_num, scale=scale)
    buffer = BytesIO()
    image.save(buffer, format="PNG", optimize=True)
    return buffer.getvalue()


def build_region_preview(
    file_path: str | Path,
    bbox: list | tuple,
    *,
    page_num: int = 1,
    scale: float = 2.0,
    isolate_red: bool = False,
) -> bytes:
    path = Path(file_path)
    image = _open_preview_image(path, page_num=page_num, scale=scale)
    crop_box = _crop_box_from_bbox(bbox, image.size)
    cropped = image.crop(crop_box)
    if isolate_red:
        cropped = _isolate_red_foreground(cropped)
    buffer = BytesIO()
    cropped.save(buffer, format="PNG", optimize=True)
    return buffer.getvalue()


def build_thumbnail(file_path: str | Path, max_size: tuple[int, int] = (320, 240)) -> bytes:
    path = Path(file_path)

    try:
        if path.suffix.lower() == ".pdf":
            image = _pdf_thumbnail(path)
        else:
            image = Image.open(path)
            image = ImageOps.exif_transpose(image)
            image = image.convert("RGB")
    except Exception:
        image = _placeholder_thumbnail(path, max_size)

    image.thumbnail(max_size)
    buffer = BytesIO()
    image.save(buffer, format="PNG", optimize=True)
    return buffer.getvalue()
