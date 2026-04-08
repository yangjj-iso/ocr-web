import unittest
from unittest.mock import patch

from app.services import ocr_service


class OCRServiceTests(unittest.TestCase):
    def test_run_ocr_document_skips_vl_dtype_check_for_remote_vl_backend(self):
        fake_result = {
            "page_count": 1,
            "pages": [{"page_num": 1, "regions": [], "lines": []}],
            "full_text": "ok",
            "mode": "vl_api",
        }

        with (
            patch.object(ocr_service, "_ensure_vl_dtype_support", side_effect=AssertionError("should not be called")),
            patch("app.core.ocr_engine.should_require_local_vl_runtime", return_value=False),
            patch("app.core.ocr_engine.ocr_document", return_value=fake_result) as ocr_mock,
        ):
            result = ocr_service._run_ocr_document("demo.png", "vl")

        ocr_mock.assert_called_once_with("demo.png", "vl")
        self.assertEqual(result["mode"], "vl_api")


if __name__ == "__main__":
    unittest.main()
