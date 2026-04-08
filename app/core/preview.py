from io import BytesIO
from pathlib import Path

from PIL import Image, ImageDraw, ImageOps

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


def build_pdf_page_preview(file_path: str | Path, page_num: int, scale: float = 2.0) -> bytes:
    path = Path(file_path)
    if fitz is None:
        raise RuntimeError("PyMuPDF is not installed.")

    page_index = max(0, int(page_num) - 1)
    document = fitz.open(path)
    try:
        if page_index >= document.page_count:
            raise IndexError("PDF page index out of range.")
        page = document.load_page(page_index)
        pix = page.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False)
        return pix.tobytes("png")
    finally:
        document.close()


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
