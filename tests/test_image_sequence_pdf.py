import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image, ImageDraw

from app.utils import image_sequence_pdf as tool


def _create_demo_image(path: Path, *, layout: str) -> None:
    image = Image.new("RGB", (900, 1200), "white")
    draw = ImageDraw.Draw(image)
    if layout == "license":
        draw.rectangle((60, 60, 840, 180), outline="black", width=6)
        draw.rectangle((80, 260, 820, 420), outline="black", width=4)
        draw.text((100, 90), "BUSINESS LICENSE", fill="black")
        draw.text((110, 300), "Name: OCR-WEB", fill="black")
        draw.ellipse((650, 800, 840, 990), outline="red", width=10)
    elif layout == "contract":
        draw.line((90, 90, 810, 90), fill="black", width=5)
        draw.text((120, 120), "CONTRACT", fill="black")
        for row in range(8):
            top = 260 + row * 90
            draw.rectangle((100, top, 800, top + 60), outline="black", width=3)
        draw.rectangle((100, 1030, 400, 1130), outline="black", width=6)
    else:
        raise ValueError(layout)
    image.save(path)


class ImageSequencePDFTests(unittest.TestCase):
    def test_parse_page_file_extracts_prefix_and_page(self):
        parsed = tool.parse_page_file(Path("KJ-JJ-2017-02-001-033.jpg"))
        self.assertEqual(parsed, ("KJ-JJ-2017-02-001", 33))

    def test_suggest_similarity_threshold_prefers_gap_between_clusters(self):
        fingerprints = [
            tool.PageFingerprint(Path("a-000.jpg"), "a", 0, 0),
            tool.PageFingerprint(Path("a-001.jpg"), "a", 1, 0, distance_from_previous=2),
            tool.PageFingerprint(Path("a-002.jpg"), "a", 2, 0, distance_from_previous=3),
            tool.PageFingerprint(Path("a-003.jpg"), "a", 3, 0, distance_from_previous=4),
            tool.PageFingerprint(Path("a-004.jpg"), "a", 4, 0, distance_from_previous=14),
            tool.PageFingerprint(Path("a-005.jpg"), "a", 5, 0, distance_from_previous=15),
        ]

        suggestion = tool.suggest_similarity_threshold(fingerprints)

        self.assertEqual(suggestion, 9)

    def test_decide_page_split_uses_secondary_signals_to_avoid_false_split(self):
        comparison = tool.PageComparison(
            phash_distance=14,
            layout_distance=3,
            profile_distance=0.05,
            text_similarity=0.92,
        )

        decision = tool.decide_page_split(comparison, similarity_threshold=10)

        self.assertFalse(decision.should_split)
        self.assertIn("保持同组", decision.split_reason)

    def test_group_pages_by_similarity_splits_when_multiple_signals_change(self):
        first = tool.PageFingerprint(Path("a-000.jpg"), "a", 0, 0xAAAA, layout_hash=0x1111, ink_ratio=0.12)
        second = tool.PageFingerprint(Path("a-001.jpg"), "a", 1, 0xAAAF, layout_hash=0x1113, ink_ratio=0.13)
        third = tool.PageFingerprint(Path("a-002.jpg"), "a", 2, 0x0F0F, layout_hash=0xEEEE, ink_ratio=0.31)
        fourth = tool.PageFingerprint(Path("a-003.jpg"), "a", 3, 0x0F1F, layout_hash=0xEEEA, ink_ratio=0.29)

        second.comparison_from_previous = tool.PageComparison(phash_distance=2, layout_distance=2, profile_distance=0.03)
        second.distance_from_previous = 2
        third.comparison_from_previous = tool.PageComparison(phash_distance=15, layout_distance=18, profile_distance=0.28)
        third.distance_from_previous = 15
        fourth.comparison_from_previous = tool.PageComparison(phash_distance=3, layout_distance=4, profile_distance=0.04)
        fourth.distance_from_previous = 3

        groups = tool.group_pages_by_similarity([first, second, third, fourth], similarity_threshold=10)

        self.assertEqual(len(groups), 2)
        self.assertEqual([group.page_count for group in groups], [2, 2])
        self.assertEqual(groups[1].suggested_filename, "a-002-003.pdf")
        self.assertTrue(groups[1].split_from_previous.should_split)

    def test_compute_phash_matches_identical_images(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            base = Path(temp_dir)
            first = base / "KJ-JJ-2017-02-001-000.jpg"
            second = base / "KJ-JJ-2017-02-001-001.jpg"
            _create_demo_image(first, layout="license")
            _create_demo_image(second, layout="license")

            self.assertEqual(tool.compute_phash(first), tool.compute_phash(second))

    def test_rebuild_pdfs_creates_expected_outputs_and_report(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            source_dir = Path(temp_dir) / "input"
            output_dir = Path(temp_dir) / "output"
            report_path = Path(temp_dir) / "split-report.json"
            source_dir.mkdir(parents=True, exist_ok=True)

            filenames = [
                "KJ-JJ-2017-02-001-000.jpg",
                "KJ-JJ-2017-02-001-001.jpg",
                "KJ-JJ-2017-02-001-002.jpg",
                "KJ-JJ-2017-02-001-003.jpg",
            ]
            for name in filenames[:2]:
                _create_demo_image(source_dir / name, layout="license")
            for name in filenames[2:]:
                _create_demo_image(source_dir / name, layout="contract")

            fake_layout_signature = {
                "KJ-JJ-2017-02-001-000.jpg": (0x1111, tuple([0.10] * 16), tuple([0.12] * 16), 0.11),
                "KJ-JJ-2017-02-001-001.jpg": (0x1113, tuple([0.11] * 16), tuple([0.13] * 16), 0.12),
                "KJ-JJ-2017-02-001-002.jpg": (0xEEEE, tuple([0.28] * 16), tuple([0.30] * 16), 0.29),
                "KJ-JJ-2017-02-001-003.jpg": (0xEEEA, tuple([0.27] * 16), tuple([0.29] * 16), 0.28),
            }
            fake_hashes = {
                "KJ-JJ-2017-02-001-000.jpg": 0b0000000000000000,
                "KJ-JJ-2017-02-001-001.jpg": 0b0000000000000011,
                "KJ-JJ-2017-02-001-002.jpg": 0b0111111111111100,
                "KJ-JJ-2017-02-001-003.jpg": 0b0111111111111111,
            }

            with (
                patch.object(
                    tool,
                    "compute_phash",
                    side_effect=lambda path, **_: fake_hashes[Path(path).name],
                ),
                patch.object(
                    tool,
                    "_compute_layout_signature",
                    side_effect=lambda path: fake_layout_signature[Path(path).name],
                ),
            ):
                summary = tool.rebuild_pdfs_from_images(
                    source_dir,
                    output_dir=output_dir,
                    similarity_threshold=10,
                    auto_threshold=True,
                    report_json=report_path,
                )

            self.assertEqual(len(summary.groups), 2)
            self.assertEqual(summary.total_pages, 4)
            self.assertTrue(summary.used_auto_threshold)
            self.assertEqual(summary.recommended_similarity_threshold, 8)
            self.assertTrue((output_dir / "KJ-JJ-2017-02-001-000-001.pdf").exists())
            self.assertTrue((output_dir / "KJ-JJ-2017-02-001-002-003.pdf").exists())
            self.assertTrue(report_path.exists())
            report = tool.format_summary(summary)
            self.assertIn("共识别出 2 个文件", report)
            self.assertIn("自动阈值 = 开启", report)
            self.assertIn("OCR 文本辅助 = 关闭", report)
            self.assertIn("切分新文件", report)

            report_payload = tool.build_summary_report(summary)
            self.assertEqual(report_payload["recommended_similarity_threshold"], 8)
            self.assertTrue(report_payload["used_auto_threshold"])
            self.assertEqual(len(report_payload["transitions"]), 3)


if __name__ == "__main__":
    unittest.main()
