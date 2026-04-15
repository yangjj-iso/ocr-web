import pathlib
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from app.domains.page_processing import page_service


class _FakeScalarResult:
    def __init__(self, items):
        self._items = items

    def all(self):
        return list(self._items)


class _FakeExecuteResult:
    def __init__(self, items):
        self._items = items

    def scalars(self):
        return _FakeScalarResult(self._items)


class _FakeSession:
    def __init__(self, items):
        self._items = items
        self.commit = AsyncMock()

    async def execute(self, stmt):
        return _FakeExecuteResult(self._items)

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False


def _page(**kwargs):
    defaults = {
        "page_id": "page-1",
        "batch_id": "batch-a",
        "page_index": 0,
        "image_uri": "archive/raw/page-1.png",
        "preview_uri": None,
        "ocr_text": None,
        "ocr_blocks_json": None,
        "layout_type": None,
        "rotation": 0,
        "phash": None,
        "duplicate_score": 0.0,
        "first_page_score": 0.0,
        "candidates_json": None,
    }
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


class PageProcessingQueueServiceTests(unittest.IsolatedAsyncioTestCase):
    async def test_preprocess_pages_stores_preview_uri(self):
        page = _page()
        session = _FakeSession([page])

        with tempfile.TemporaryDirectory() as tmpdir:
            source_path = pathlib.Path(tmpdir) / "source.png"
            source_path.write_bytes(b"raw-image")
            processed_path = pathlib.Path(tmpdir) / "processed.png"
            processed_path.write_bytes(b"processed-image")

            with patch("app.domains.page_processing.page_service.async_session", new=lambda: session), patch(
                "app.domains.page_processing.page_service._materialize_storage_uri",
                new=AsyncMock(return_value=(str(source_path), None)),
            ), patch("app.utils.image_preprocess.preprocess_image", return_value=str(processed_path)), patch(
                "app.infrastructure.storage.put_object_bytes",
                return_value="archive/preprocessed/batch-a/page-1.png",
            ) as put_mock, patch("app.utils.image_preprocess.cleanup_preprocessed_image"):
                await page_service.preprocess_pages(batch_id="batch-a", page_ids=["page-1"])

        self.assertEqual(page.preview_uri, "archive/preprocessed/batch-a/page-1.png")
        put_mock.assert_called_once()
        session.commit.assert_awaited_once()

    async def test_run_ocr_pages_updates_text_and_blocks(self):
        page = _page(preview_uri="archive/preprocessed/batch-a/page-1.png")
        session = _FakeSession([page])

        with patch("app.domains.page_processing.page_service.async_session", new=lambda: session), patch(
            "app.domains.page_processing.page_service._materialize_storage_uri",
            new=AsyncMock(return_value=("preview-local.png", None)),
        ), patch(
            "app.core.ocr_engine.ocr_image_basic",
            return_value={"lines": [{"text": "第一行"}, {"text": "第二行"}]},
        ):
            await page_service.run_ocr_pages(batch_id="batch-a", page_ids=["page-1"])

        self.assertEqual(page.ocr_text, "第一行\n第二行")
        self.assertEqual(page.layout_type, "text")
        self.assertEqual(page.ocr_blocks_json["lines"][0]["text"], "第一行")
        session.commit.assert_awaited_once()

    async def test_extract_page_features_updates_candidates_and_duplicate_score(self):
        previous_page = _page(
            page_id="page-0",
            page_index=0,
            ocr_text="前页正文",
            phash="ffffffffffffffff",
            layout_type="text",
        )
        page = _page(
            page_id="page-1",
            page_index=1,
            ocr_text="关于开展档案整理工作的通知\n2024年1月1日\n政办〔2024〕1号",
        )
        session = _FakeSession([previous_page, page])

        with patch("app.domains.page_processing.page_service.async_session", new=lambda: session), patch(
            "app.domains.page_processing.page_service.compute_phash_from_uri",
            new=AsyncMock(return_value="0000000000000000"),
        ), patch("app.domains.page_processing.page_service.score_duplicate_page", return_value=0.25):
            await page_service.extract_page_features(batch_id="batch-a", page_ids=["page-1"])

        self.assertEqual(page.phash, "0000000000000000")
        self.assertEqual(page.duplicate_score, 0.25)
        self.assertTrue(page.first_page_score > 0)
        self.assertIn("2024年1月1日", page.candidates_json["dates"])
        self.assertIn("政办〔2024〕1号", page.candidates_json["doc_nos"])
        session.commit.assert_awaited_once()


if __name__ == "__main__":
    unittest.main()