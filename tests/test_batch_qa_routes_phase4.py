import unittest
from unittest.mock import AsyncMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes import router
from app.db.database import get_db
from app.services.llm_field_extraction_service import MiniMaxServiceError


class FakeDB:
    async def execute(self, *_args, **_kwargs):
        raise RuntimeError("should not hit db in mocked route tests")


class BatchQARoutePhase4Tests(unittest.TestCase):
    def setUp(self):
        self.db = FakeDB()
        self.app = FastAPI()
        self.app.include_router(router)

        async def override_get_db():
            yield self.db

        self.app.dependency_overrides[get_db] = override_get_db
        self.client = TestClient(self.app)

    def tearDown(self):
        self.client.close()

    def test_batch_qa_success_with_new_fields(self):
        payload = {
            "batch_id": "batch-1",
            "question": "该批次核心结论是什么？",
            "answer": "证据显示结论为通过。",
            "evidence": [{"task_id": 1, "filename": "a.pdf", "snippet": "结论：通过", "score": 0.9}],
            "qa_id": 101,
            "support_level": "supported",
            "confidence": 0.91,
            "citations": [{"evidence_index": 1, "task_id": 1, "filename": "a.pdf"}],
            "provider": "minimax",
            "model": "minimax-2.7",
            "raw_usage": {"total_tokens": 12},
            "generated_at": "2026-03-31T00:00:00+00:00",
        }
        with patch("app.api.routes.answer_batch_question", AsyncMock(return_value=payload)) as qa_mock:
            response = self.client.post(
                "/api/ocr/batches/batch-1/qa",
                json={"question": "该批次核心结论是什么？", "top_k": 8, "persist": True},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["qa_id"], 101)
        self.assertEqual(response.json()["support_level"], "supported")
        self.assertTrue(qa_mock.await_args.kwargs["persist"])

    def test_batch_qa_maps_minimax_error(self):
        with patch(
            "app.api.routes.answer_batch_question",
            AsyncMock(side_effect=MiniMaxServiceError(504, "timeout")),
        ):
            response = self.client.post(
                "/api/ocr/batches/batch-1/qa",
                json={"question": "测试问题", "top_k": 8},
            )
        self.assertEqual(response.status_code, 504)

    def test_batch_qa_history_success(self):
        payload = {
            "batch_id": "batch-1",
            "total": 1,
            "page": 1,
            "page_size": 20,
            "items": [
                {
                    "qa_id": 1,
                    "batch_id": "batch-1",
                    "question": "测试问题",
                    "answer": "测试答案",
                    "evidence": [],
                    "support_level": "supported",
                    "confidence": 0.8,
                    "citations": [],
                    "provider": "minimax",
                    "model": "minimax-2.7",
                    "raw_usage": {},
                    "generated_at": "2026-03-31T00:00:00+00:00",
                    "feedback": None,
                }
            ],
        }
        with patch("app.api.routes.get_batch_qa_history", AsyncMock(return_value=payload)):
            response = self.client.get("/api/ocr/batches/batch-1/qa/history")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["total"], 1)

    def test_batch_qa_feedback_validation_error(self):
        with patch(
            "app.api.routes.submit_batch_qa_feedback",
            AsyncMock(side_effect=ValueError("reason is required when rating is not_helpful.")),
        ):
            response = self.client.post(
                "/api/ocr/batches/batch-1/qa/1/feedback",
                json={"rating": "not_helpful"},
            )
        self.assertEqual(response.status_code, 400)

    def test_batch_qa_feedback_not_found(self):
        with patch("app.api.routes.submit_batch_qa_feedback", AsyncMock(return_value=None)):
            response = self.client.post(
                "/api/ocr/batches/batch-1/qa/1/feedback",
                json={"rating": "helpful"},
            )
        self.assertEqual(response.status_code, 404)

    def test_batch_qa_metrics_success(self):
        payload = {
            "batch_id": "batch-1",
            "helpful_rate": 0.5,
            "insufficient_rate": 0.25,
            "feedback_count": 4,
            "recent_trend": [],
            "generated_at": "2026-03-31T00:00:00+00:00",
        }
        with patch("app.api.routes.get_batch_qa_metrics", AsyncMock(return_value=payload)):
            response = self.client.get("/api/ocr/batches/batch-1/qa/metrics")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["feedback_count"], 4)


if __name__ == "__main__":
    unittest.main()
