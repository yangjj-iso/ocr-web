import unittest
from datetime import datetime, timezone
from types import SimpleNamespace

from app.api.archive_workflow import _serialize_batch


class ArchiveBatchProgressSerializationTests(unittest.TestCase):
    def test_serialize_batch_includes_queue_progress_stages(self):
        batch = SimpleNamespace(
            id=1,
            batch_id="batch-a",
            page_count=10,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
            policy_snapshot_id="policy-v1",
            draft_status="running",
            final_status="pending",
            review_status="none",
            export_status="none",
            status="processing",
        )
        latest_run = SimpleNamespace(
            current_stage="extract_page_features",
            run_status="running",
            state_json={
                "queue_progress": {
                    "page_preprocess": {"total": 10, "completed": 10, "status": "done"},
                    "ocr": {"total": 10, "completed": 8, "status": "processing"},
                    "page_features": {"total": 10, "completed": 6, "status": "processing"},
                    "relation_analysis": {"total": 1, "completed": 0, "status": "pending"},
                }
            },
        )

        payload = _serialize_batch(
            batch,
            latest_run=latest_run,
            source_count=2,
            total_docs=0,
            done_docs=0,
            review_counts={},
            created_by="tester",
            policy_version="v1",
        )

        self.assertIn("queue_progress", payload)
        self.assertEqual(payload["queue_progress"]["ocr"]["completed"], 8)
        stage_names = [stage["name"] for stage in payload["workflow_stages"]]
        self.assertIn("page_preprocess", stage_names)
        self.assertIn("ocr", stage_names)
        self.assertIn("page_features", stage_names)
        self.assertIn("relation_analysis", stage_names)

        ocr_stage = next(stage for stage in payload["workflow_stages"] if stage["name"] == "ocr")
        relation_stage = next(stage for stage in payload["workflow_stages"] if stage["name"] == "relation_analysis")

        self.assertEqual(ocr_stage["count"], "8/10")
        self.assertEqual(ocr_stage["status"], "processing")
        self.assertEqual(relation_stage["count"], "0/1")
        self.assertEqual(relation_stage["status"], "pending")


if __name__ == "__main__":
    unittest.main()