import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch

from app.core import ocr_engine
from app.utils import image_preprocess
from PIL import Image, ImageDraw


class _FakePipeline:
    def __init__(self, side_effects, *, has_doc_preprocessor=True):
        self.side_effects = list(side_effects)
        self.calls = []
        self.doc_preprocessor_pipeline = object() if has_doc_preprocessor else None

    def predict(self, **kwargs):
        self.calls.append(kwargs)
        effect = self.side_effects.pop(0)
        if isinstance(effect, Exception):
            raise effect
        return effect


class _FakeOCR:
    def predict(self, image_path):
        return [
            {
                "rec_texts": ["第一行", "第二行"],
                "rec_scores": [0.98, 0.87],
                "dt_polys": [
                    [[0, 0], [10, 0], [10, 10], [0, 10]],
                    [[0, 12], [20, 12], [20, 22], [0, 22]],
                ],
            }
        ]


def _make_red_seal_image(target: Path) -> None:
    image = Image.new("RGB", (420, 260), "white")
    draw = ImageDraw.Draw(image)
    draw.ellipse((85, 35, 275, 225), outline=(220, 20, 40), width=14)
    draw.ellipse((150, 100, 210, 160), fill=(225, 30, 45))
    draw.rectangle((20, 20, 70, 40), fill=(0, 0, 0))
    image.save(target, format="PNG")


class OCREngineTests(unittest.TestCase):
    def test_predict_structured_retries_without_unsupported_argument(self):
        pipeline = _FakePipeline(
            [
                TypeError("predict() got an unexpected keyword argument 'format_block_content'"),
                [{"page": 1}],
            ]
        )

        result = ocr_engine._predict_structured(pipeline, "demo.png", profile="layout")

        self.assertEqual(result, [{"page": 1}])
        self.assertEqual(len(pipeline.calls), 2)
        self.assertIn("format_block_content", pipeline.calls[0])
        self.assertNotIn("format_block_content", pipeline.calls[1])

    def test_predict_structured_retries_when_doc_preprocessor_is_missing(self):
        pipeline = _FakePipeline(
            [
                RuntimeError("doc_preprocessor_pipeline is not initialized"),
                [{"page": 1}],
            ]
        )

        result = ocr_engine._predict_structured(pipeline, "demo.png", profile="layout")

        self.assertEqual(result, [{"page": 1}])
        self.assertEqual(len(pipeline.calls), 2)
        self.assertIn("use_doc_orientation_classify", pipeline.calls[0])
        self.assertIn("use_doc_unwarping", pipeline.calls[0])
        self.assertNotIn("use_doc_orientation_classify", pipeline.calls[1])
        self.assertNotIn("use_doc_unwarping", pipeline.calls[1])

    def test_geometry_helpers_return_expected_values(self):
        rect = ocr_engine._rect_from_polys(
            [
                [[0, 0], [10, 0], [10, 10], [0, 10]],
                [[5, 5], [15, 5], [15, 20], [5, 20]],
            ]
        )

        self.assertEqual(rect, [0, 0, 15, 20])
        self.assertEqual(ocr_engine._rect_area(rect), 300)
        self.assertEqual(ocr_engine._rect_intersection_area([0, 0, 10, 10], [5, 5, 15, 20]), 25)
        self.assertTrue(ocr_engine._rect_contains_point([0, 0, 10, 10], 6, 6))
        self.assertFalse(ocr_engine._rect_contains_point([0, 0, 10, 10], 12, 6))

    def test_baidu_location_to_bbox_supports_point_dict_polygons(self):
        bbox = ocr_engine._baidu_location_to_bbox(
            [
                {"x": 12, "y": 18},
                {"x": 48, "y": 18},
                {"x": 48, "y": 60},
                {"x": 12, "y": 60},
            ]
        )

        self.assertEqual(bbox, [12, 18, 48, 60])

    def test_ocr_image_basic_returns_lines(self):
        with patch.object(ocr_engine, "_should_use_layout_api", return_value=False), patch.object(
            ocr_engine,
            "get_ocr",
            return_value=_FakeOCR(),
        ):
            result = ocr_engine.ocr_image_basic("demo.png")

        self.assertEqual(len(result["lines"]), 2)
        self.assertEqual(result["lines"][0]["text"], "第一行")
        self.assertEqual(result["lines"][0]["bbox"], [[0.0, 0.0], [10.0, 0.0], [10.0, 10.0], [0.0, 10.0]])
        self.assertEqual(result["lines"][1]["line_num"], 2)

    def test_ocr_image_basic_routes_to_api_when_configured(self):
        remote_payload = {
            "page_count": 1,
            "pages": [{"page_num": 1, "regions": [], "lines": [{"line_num": 1, "text": "远端 OCR", "confidence": 0.95, "bbox": []}]}],
            "full_text": "远端 OCR",
            "mode": "ocr_api",
        }

        with (
            patch.object(ocr_engine, "_should_use_layout_api", side_effect=lambda mode: mode == "ocr"),
            patch.object(ocr_engine, "ocr_document_layout_api", return_value=remote_payload) as api_mock,
        ):
            result = ocr_engine.ocr_image_basic("demo.png")

        api_mock.assert_called_once_with("demo.png", mode_label="ocr_api")
        self.assertEqual(result["lines"][0]["text"], "远端 OCR")

    @unittest.skipIf(ocr_engine.cv2 is None or ocr_engine.np is None, "OpenCV stack unavailable")
    def test_detect_red_seal_regions_finds_stamp_candidates(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            source = Path(temp_dir) / "seal-sample.png"
            _make_red_seal_image(source)

            regions = ocr_engine._detect_red_seal_regions(str(source))

        self.assertGreaterEqual(len(regions), 1)
        self.assertEqual(regions[0]["type"], "seal")
        self.assertEqual(regions[0]["agent_meta"]["detected_by"], "opencv_red_seal_detector")
        self.assertGreater(regions[0]["agent_meta"]["detector_confidence"], 0.4)

    @unittest.skipIf(ocr_engine.cv2 is None or ocr_engine.np is None, "OpenCV stack unavailable")
    def test_ocr_image_basic_appends_detected_seal_regions(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            source = Path(temp_dir) / "seal-sample.png"
            _make_red_seal_image(source)

            with patch.object(ocr_engine, "_should_use_layout_api", return_value=False), patch.object(
                ocr_engine,
                "get_ocr",
                return_value=_FakeOCR(),
            ):
                result = ocr_engine.ocr_image_basic(str(source))

        self.assertEqual(len(result["lines"]), 2)
        self.assertTrue(any(region["type"] == "seal" for region in result["regions"]))

    def test_preprocess_image_resizes_large_images_even_when_strategy_is_none(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            source = Path(temp_dir) / "large-scan.jpg"
            Image.new("RGB", (4000, 2000), "white").save(source, format="JPEG")

            processed = image_preprocess.preprocess_image(source, "none")
            self.assertNotEqual(str(source), processed)

            with Image.open(processed) as resized:
                self.assertLessEqual(max(resized.size), image_preprocess.MAX_PREPROCESS_DIM)
                self.assertEqual(resized.size, (2500, 1250))

            image_preprocess.cleanup_preprocessed_image(source, processed)

    @unittest.skipIf(image_preprocess.cv2 is None or image_preprocess.np is None, "OpenCV stack unavailable")
    def test_preprocess_image_reads_unicode_paths_with_cv_safe_loader(self):
        with tempfile.TemporaryDirectory(prefix="中文目录-") as temp_dir:
            source = Path(temp_dir) / "测试图片.jpg"
            Image.new("RGB", (600, 300), "white").save(source, format="JPEG")

            with (
                patch.object(image_preprocess.np, "fromfile", wraps=image_preprocess.np.fromfile) as fromfile_mock,
                patch.object(image_preprocess.cv2, "imdecode", wraps=image_preprocess.cv2.imdecode) as imdecode_mock,
            ):
                processed = image_preprocess.preprocess_image(source, "enhance_contrast")

            self.assertNotEqual(str(source), processed)
            self.assertTrue(fromfile_mock.called)
            self.assertTrue(imdecode_mock.called)
            image_preprocess.cleanup_preprocessed_image(source, processed)

    def test_predict_structured_vl_sets_device(self):
        pipeline = _FakePipeline([[{"page": 1}]])

        fake_device = type("FakeDevice", (), {"set_device": lambda self, value: None})()
        fake_paddle = type("FakePaddle", (), {"device": fake_device})()

        with patch.dict("sys.modules", {"paddle": fake_paddle}):
            result = ocr_engine._predict_structured(pipeline, "demo.png", profile="vl")

        self.assertEqual(result, [{"page": 1}])
        self.assertEqual(pipeline.calls[0]["input"], "demo.png")

    def test_map_layout_api_result_to_document_preserves_tables_and_text(self):
        result = ocr_engine._map_layout_api_result_to_document(
            {
                "layoutParsingResults": [
                    {
                        "markdown": {
                            "text": "# 标题\n\n这是正文第一行\n这是正文第二行\n\n| 字段 | 值 |\n| --- | --- |\n| 文号 | 测试字[2026]1号 |"
                        }
                    }
                ]
            }
        )

        self.assertEqual(result["page_count"], 1)
        self.assertEqual(result["pages"][0]["regions"][0]["type"], "text")
        self.assertEqual(result["pages"][0]["regions"][0]["content"], "标题")
        self.assertEqual(result["pages"][0]["regions"][1]["content"], "这是正文第一行\n这是正文第二行")
        self.assertEqual(result["pages"][0]["regions"][2]["type"], "table")
        self.assertEqual(result["pages"][0]["regions"][2]["table_data"][1][1], "测试字[2026]1号")

    def test_ocr_document_routes_layout_mode_to_api_when_configured(self):
        remote_payload = {
            "page_count": 1,
            "pages": [{"page_num": 1, "regions": [], "lines": []}],
            "full_text": "远端识别结果",
            "mode": "layout_api",
        }

        with (
            patch.object(ocr_engine, "_should_use_layout_api", return_value=True),
            patch.object(ocr_engine, "ocr_document_layout_api", return_value=remote_payload) as api_mock,
        ):
            result = ocr_engine.ocr_document("demo.pdf", mode="layout")

        api_mock.assert_called_once_with("demo.pdf", mode_label="layout_api")
        self.assertEqual(result["mode"], "layout_api")
        self.assertEqual(result["full_text"], "远端识别结果")

    def test_ocr_document_routes_ocr_mode_to_api_when_configured(self):
        remote_payload = {
            "page_count": 1,
            "pages": [{"page_num": 1, "regions": [], "lines": []}],
            "full_text": "远端 OCR 识别结果",
            "mode": "ocr_api",
        }

        with (
            patch.object(ocr_engine, "_should_use_baidu_vl_backend", return_value=False),
            patch.object(ocr_engine, "_should_use_layout_api", side_effect=lambda mode: mode == "ocr"),
            patch.object(ocr_engine, "ocr_document_layout_api", return_value=remote_payload) as api_mock,
        ):
            result = ocr_engine.ocr_document("demo.png", mode="ocr")

        api_mock.assert_called_once_with("demo.png", mode_label="ocr_api")
        self.assertEqual(result["mode"], "ocr_api")
        self.assertEqual(result["full_text"], "远端 OCR 识别结果")

    def test_ocr_document_routes_vl_mode_to_api_when_configured(self):
        remote_payload = {
            "page_count": 1,
            "pages": [{"page_num": 1, "regions": [], "lines": []}],
            "full_text": "远端 VL 识别结果",
            "mode": "vl_api",
        }

        with (
            patch.object(ocr_engine, "_should_use_baidu_vl_backend", return_value=False),
            patch.object(ocr_engine, "_should_use_layout_api", side_effect=lambda mode: mode == "vl"),
            patch.object(ocr_engine, "ocr_document_layout_api", return_value=remote_payload) as api_mock,
        ):
            result = ocr_engine.ocr_document("demo.png", mode="vl")

        api_mock.assert_called_once_with("demo.png", mode_label="vl_api")
        self.assertEqual(result["mode"], "vl_api")
        self.assertEqual(result["full_text"], "远端 VL 识别结果")

    def test_ocr_image_with_vl_routes_to_api_when_configured(self):
        remote_payload = {
            "page_count": 1,
            "pages": [{"page_num": 1, "regions": [{"type": "text", "content": "测试", "bbox": []}], "lines": []}],
            "full_text": "测试",
            "mode": "vl_api",
        }

        with (
            patch.object(ocr_engine, "_should_use_layout_api", side_effect=lambda mode: mode == "vl"),
            patch.object(ocr_engine, "ocr_document_layout_api", return_value=remote_payload) as api_mock,
        ):
            result = ocr_engine.ocr_image_with_vl("demo.png")

        api_mock.assert_called_once_with("demo.png", mode_label="vl_api")
        self.assertEqual(result["regions"][0]["content"], "测试")

    def test_enrich_document_with_baidu_office_seals_appends_seal_region(self):
        office_payload = {
            "results": [
                {
                    "words": {
                        "word": "重庆海凌装饰设计工程有限公司",
                        "poly_location": [
                            {"x": 116, "y": 120},
                            {"x": 206, "y": 120},
                            {"x": 206, "y": 144},
                            {"x": 116, "y": 144},
                        ],
                    },
                    "line_probability": {"average": 0.98},
                },
                {
                    "words": {
                        "word": "合同专用章",
                        "poly_location": [
                            {"x": 126, "y": 148},
                            {"x": 192, "y": 148},
                            {"x": 192, "y": 170},
                            {"x": 126, "y": 170},
                        ],
                    },
                    "line_probability": {"average": 0.96},
                },
            ],
            "layouts": [
                {
                    "layout": "seal",
                    "layout_location": [
                        {"x": 100, "y": 100},
                        {"x": 220, "y": 100},
                        {"x": 220, "y": 220},
                        {"x": 100, "y": 220},
                    ],
                    "layout_idx": [0, 1],
                    "layout_probability": 0.93,
                }
            ],
            "seal_recog_results": [
                {
                    "type": "circle",
                    "probability": 0.99,
                    "location": {"left": 100, "top": 100, "width": 120, "height": 120},
                    "major": {"words": "重庆海凌装饰设计工程有限公司"},
                    "minor": [{"words": "合同专用章"}],
                }
            ],
        }

        document = {
            "page_count": 1,
            "pages": [{"page_num": 1, "regions": [{"type": "text", "content": "施工说明", "bbox": []}], "lines": []}],
            "full_text": "施工说明",
            "mode": "baidu_vl",
        }

        with tempfile.TemporaryDirectory() as temp_dir:
            source = Path(temp_dir) / "seal-office.png"
            Image.new("RGB", (320, 240), "white").save(source, format="PNG")

            with (
                patch.object(ocr_engine, "_can_use_baidu_document_api", return_value=True),
                patch.object(ocr_engine, "_get_baidu_access_token", return_value="token"),
                patch.object(ocr_engine, "_call_baidu_doc_analysis_office", return_value=office_payload),
            ):
                result = ocr_engine._enrich_document_with_baidu_office_seals(document, str(source))

        seal_regions = [region for region in result["pages"][0]["regions"] if region["type"] == "seal"]
        self.assertEqual(len(seal_regions), 1)
        self.assertEqual(seal_regions[0]["layout_bbox"], [100.0, 100.0, 220.0, 220.0])
        self.assertIn("重庆海凌装饰设计工程有限公司", seal_regions[0]["content"])
        self.assertEqual(
            seal_regions[0]["agent_meta"]["detected_by"],
            "baidu_doc_analysis_office_layout",
        )

    @unittest.skipIf(ocr_engine.cv2 is None or ocr_engine.np is None, "OpenCV stack unavailable")
    def test_ocr_document_layout_api_enriches_pages_with_detected_seals(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            source = Path(temp_dir) / "seal-sample.png"
            _make_red_seal_image(source)

            with patch.object(
                ocr_engine,
                "_call_layout_api",
                return_value={"layoutParsingResults": [{"markdown": {"text": "合同正文"}}]},
            ):
                result = ocr_engine.ocr_document_layout_api(str(source), mode_label="layout_api")

        self.assertEqual(result["pages"][0]["regions"][0]["type"], "text")
        self.assertTrue(any(region["type"] == "seal" for region in result["pages"][0]["regions"]))


if __name__ == "__main__":
    unittest.main()
