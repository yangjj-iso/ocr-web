import io
import tempfile
import unittest
from pathlib import Path

from PIL import Image, ImageDraw

from app.core.preview import build_region_preview


def _make_seal_sample(path: Path) -> None:
    image = Image.new("RGB", (320, 220), "white")
    draw = ImageDraw.Draw(image)
    draw.rectangle((24, 28, 92, 58), fill=(0, 0, 0))
    draw.ellipse((90, 45, 230, 185), outline=(225, 35, 45), width=12)
    draw.ellipse((138, 93, 182, 137), fill=(230, 35, 45))
    image.save(path, format="PNG")


class PreviewTests(unittest.TestCase):
    def test_build_region_preview_crops_requested_box(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            source = Path(temp_dir) / "seal.png"
            _make_seal_sample(source)

            payload = build_region_preview(source, [90, 45, 230, 185], isolate_red=False)

        with Image.open(io.BytesIO(payload)) as cropped:
            self.assertEqual(cropped.mode, "RGBA")
            self.assertGreaterEqual(cropped.size[0], 140)
            self.assertGreaterEqual(cropped.size[1], 140)
            self.assertEqual(cropped.getpixel((0, 0))[3], 255)

    def test_build_region_preview_can_isolate_red_seal(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            source = Path(temp_dir) / "seal.png"
            _make_seal_sample(source)

            payload = build_region_preview(source, [90, 45, 230, 185], isolate_red=True)

        with Image.open(io.BytesIO(payload)) as cropped:
            self.assertEqual(cropped.mode, "RGBA")
            self.assertEqual(cropped.getpixel((0, 0))[3], 0)
            center = cropped.getpixel((cropped.size[0] // 2, cropped.size[1] // 2))
            self.assertGreater(center[3], 0)
            self.assertGreater(center[0], center[1])
            self.assertGreater(center[0], center[2])


if __name__ == "__main__":
    unittest.main()
