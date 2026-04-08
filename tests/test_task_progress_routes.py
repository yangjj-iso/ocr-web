import unittest
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes import router
from app.db.database import get_db


class _ScalarResult:
    def __init__(self, items):
        self._items = items

    def all(self):
        return self._items


class _ExecuteResult:
    def __init__(self, items):
        self._items = items

    def scalars(self):
        return _ScalarResult(self._items)


class FakeDB:
    def __init__(self, tasks=None):
        self._tasks = tasks or {}

    async def execute(self, _statement, *_args, **_kwargs):
        return _ExecuteResult(list(self._tasks.values()))


class TaskProgressRouteTests(unittest.TestCase):
    def setUp(self):
        self.db = FakeDB(
            tasks={
                1: SimpleNamespace(id=1, status="done", error_message=None),
                2: SimpleNamespace(id=2, status="processing", error_message=None),
                3: SimpleNamespace(id=3, status="failed", error_message="boom"),
            }
        )
        self.app = FastAPI()
        self.app.include_router(router)

        async def override_get_db():
            yield self.db

        self.app.dependency_overrides[get_db] = override_get_db
        self.client = TestClient(self.app)

    def tearDown(self):
        self.client.close()

    def test_progress_counts_requested_tasks(self):
        response = self.client.post("/api/ocr/tasks/progress", json={"task_ids": [1, 2, 3]})

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["total"], 3)
        self.assertEqual(payload["done_count"], 1)
        self.assertEqual(payload["processing_count"], 1)
        self.assertEqual(payload["failed_count"], 1)
        self.assertEqual(payload["pending_count"], 0)
        self.assertEqual([item["id"] for item in payload["tasks"]], [1, 2, 3])

    def test_progress_marks_missing_task_as_failed(self):
        response = self.client.post("/api/ocr/tasks/progress", json={"task_ids": [1, 99]})

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["total"], 2)
        self.assertEqual(payload["done_count"], 1)
        self.assertEqual(payload["failed_count"], 1)
        self.assertEqual(payload["tasks"][1]["status"], "failed")
        self.assertEqual(payload["tasks"][1]["error_message"], "Task not found.")

    def test_progress_handles_empty_payload(self):
        response = self.client.post("/api/ocr/tasks/progress", json={"task_ids": []})

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["total"], 0)
        self.assertEqual(payload["tasks"], [])


if __name__ == "__main__":
    unittest.main()
