import asyncio
import hashlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.infrastructure.queue.contracts import CommandFilePayload, OcrTaskCommand
from app.infrastructure.queue.worker_executor import _stage_input_file


class _FakeHttpResponse:
    def __init__(self, content: bytes) -> None:
        self.content = content

    def raise_for_status(self) -> None:
        return None


class _FakeAsyncClient:
    def __init__(self, *args, **kwargs) -> None:
        self.calls = kwargs.setdefault("_calls", [])
        self._shared_calls = kwargs.pop("calls_sink")

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return None

    async def get(self, url: str, headers: dict[str, str] | None = None):
        self._shared_calls.append((url, dict(headers or {})))
        return _FakeHttpResponse(b"remote-image-bytes")


class WorkerExecutorTests(unittest.TestCase):
    def test_stage_input_file_downloads_http_source_to_temp_path(self):
        expected_sha256 = hashlib.sha256(b"remote-image-bytes").hexdigest()
        command = OcrTaskCommand(
            task_id=165,
            file=CommandFilePayload(
                storage_provider="local",
                file_url="http://127.0.0.1:8080/internal/api/v1/ocr/tasks/165/source-file",
                filename="sample.jpg",
                content_type="image/jpeg",
                sha256=expected_sha256,
            ),
        )
        http_calls: list[tuple[str, dict[str, str]]] = []

        def fake_async_client(*args, **kwargs):
            return _FakeAsyncClient(*args, calls_sink=http_calls, **kwargs)

        with patch("app.infrastructure.queue.worker_executor.httpx.AsyncClient", side_effect=fake_async_client), patch.dict(
            "os.environ",
            {"CONTROL_PLANE_INTERNAL_TOKEN": "internal-token"},
            clear=False,
        ):
            staged_path, should_cleanup = asyncio.run(_stage_input_file(command))

        try:
            self.assertTrue(should_cleanup)
            self.assertTrue(Path(staged_path).exists())
            self.assertEqual(b"remote-image-bytes", Path(staged_path).read_bytes())
            self.assertEqual(1, len(http_calls))
            self.assertEqual(command.file.file_url, http_calls[0][0])
            self.assertEqual("Bearer internal-token", http_calls[0][1]["Authorization"])
        finally:
            Path(staged_path).unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
