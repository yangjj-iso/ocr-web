import tempfile
import unittest
from pathlib import Path

from app.infrastructure.queue.callback_client import build_progress
from app.infrastructure.queue.publisher import OCRJob, _build_command


class QueueContractTests(unittest.TestCase):
    def test_build_command_from_legacy_job(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            file_path = Path(temp_dir) / "sample.jpg"
            file_path.write_bytes(b"fake-image")
            job = OCRJob(
                task_id=12,
                mode="vl",
                filename="sample.jpg",
                file_path=str(file_path),
                file_type=".jpg",
                batch_id="batch-demo",
                excel_path="archive.xlsx",
                output_dir="output",
            )

            command = _build_command(job)

            self.assertEqual(command.task_id, 12)
            self.assertEqual(command.batch_id, "batch-demo")
            self.assertEqual(command.file.filename, "sample.jpg")
            self.assertTrue(command.file.file_url.startswith("file:///"))
            self.assertEqual(command.execution.max_retries, 2)
            self.assertEqual(command.business.archive_context["excel_path"], "archive.xlsx")

    def test_build_progress_clamps_percent(self):
        progress = build_progress(3, 12)
        self.assertEqual(progress.current_page, 3)
        self.assertEqual(progress.total_pages, 12)
        self.assertEqual(progress.percent, 25.0)


if __name__ == "__main__":
    unittest.main()
