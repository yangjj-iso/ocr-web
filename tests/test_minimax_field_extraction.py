import json
import os
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes import router
from app.core.auth import require_auth, require_operator_access
from app.db.database import get_db
from app.services import llm_field_extraction_service as minimax_service

_MOCK_USER = {
    "username": "tester",
    "is_admin": True,
    "user_status": "active",
    "user_id": 1,
    "role": "admin",
    "capabilities": "operator",
    "tenant_id": "default",
}


class StubResponse:
    def __init__(self, *, status_code=200, payload=None):
        self.status_code = status_code
        self._payload = payload or {}

    def json(self):
        return self._payload


class StubAsyncClient:
    def __init__(self, *, response=None, error=None, timeout=None):
        self.response = response
        self.error = error
        self.timeout = timeout

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def post(self, *args, **kwargs):
        if self.error:
            raise self.error
        return self.response


class MiniMaxServiceTests(unittest.IsolatedAsyncioTestCase):
    def test_resolve_llm_runtime_config_falls_back_to_llm_env(self):
        with (
            patch.dict(
                os.environ,
                {
                    "LLM_BASE_URL": "https://api.minimaxi.com/v1",
                    "LLM_API_KEY": "sk-test-123",
                    "LLM_MODEL": "MiniMax-M2.7",
                    "LLM_TIMEOUT_SECONDS": "88",
                },
                clear=False,
            ),
            patch.object(minimax_service, "MINIMAX_ENABLED", False),
            patch.object(minimax_service, "MINIMAX_API_KEY", ""),
            patch.object(minimax_service, "MINIMAX_BASE_URL", "https://legacy.invalid/v1"),
            patch.object(minimax_service, "MINIMAX_MODEL", "legacy-model"),
            patch.object(minimax_service, "MINIMAX_TIMEOUT_SECONDS", 60.0),
        ):
            config = minimax_service._resolve_llm_runtime_config()

        self.assertTrue(config["enabled"])
        self.assertEqual(config["base_url"], "https://api.minimaxi.com/v1")
        self.assertEqual(config["api_key"], "sk-test-123")
        self.assertEqual(config["model"], "MiniMax-M2.7")
        self.assertEqual(config["timeout_seconds"], 88.0)

    def test_build_input_text_includes_front_middle_tail_and_candidates(self):
        full_text = "\n".join(f"第{i}行测试内容" for i in range(1, 500))
        excerpt = minimax_service.build_minimax_input_text(
            full_text,
            title_candidates=["关于测试项目的通知"],
            doc_no_candidates=["测试〔2024〕12号"],
            max_chars=800,
        )

        self.assertIn("标题候选", excerpt)
        self.assertIn("文号候选", excerpt)
        self.assertIn("[前部摘录]", excerpt)
        self.assertIn("[中部摘录]", excerpt)
        self.assertIn("[尾部摘录]", excerpt)
        self.assertLessEqual(len(excerpt), 800)

    def test_large_field_extraction_uses_longer_timeout(self):
        self.assertEqual(
            minimax_service._resolve_field_extraction_timeout(page_count=2, excerpt_text="短文本"),
            minimax_service.MINIMAX_TIMEOUT_SECONDS,
        )
        self.assertGreaterEqual(
            minimax_service._resolve_field_extraction_timeout(page_count=12, excerpt_text="短文本"),
            180.0,
        )

    def test_merge_rule_and_llm_fields_builds_recommended_and_conflicts(self):
        rule_fields = {
            "档号": "A-001",
            "文号": "",
            "责任者": "某单位",
            "题名": "关于测试的通知",
            "日期": "",
            "页数": "5",
            "密级": "",
            "备注": "",
        }
        llm_fields = {
            "档号": "A-001",
            "文号": "测试〔2024〕1号",
            "责任者": "另一单位",
            "题名": "关于测试的通知",
            "日期": "2024-01-02",
            "页数": "6",
            "密级": "",
            "备注": "",
            "evidence": {
                "责任者": "另一单位",
                "文号": "测试〔2024〕1号",
                "页数": "第6页",
            },
        }

        recommended, conflicts = minimax_service.merge_rule_and_llm_fields(rule_fields, llm_fields, page_count=5)

        self.assertEqual(recommended["档号"], "A-001")
        self.assertEqual(recommended["文号"], "测试〔2024〕1号")
        self.assertEqual(recommended["日期"], "2024-01-02")
        self.assertEqual(recommended["页数"], "5")
        self.assertEqual(recommended["责任者"], "")
        self.assertIn("责任者", conflicts)
        self.assertIn("页数", conflicts)

    async def test_missing_key_raises_configuration_error(self):
        with patch.object(minimax_service, "MINIMAX_ENABLED", True), patch.object(minimax_service, "MINIMAX_API_KEY", ""):
            with self.assertRaises(minimax_service.MiniMaxServiceError) as ctx:
                await minimax_service.call_minimax_field_extraction(
                    filename="demo.pdf",
                    page_count=1,
                    full_text="测试内容",
                    result_json=[],
                    rule_fields=minimax_service._blank_fields(),
                )
        self.assertEqual(ctx.exception.status_code, 503)

    async def test_timeout_is_translated_to_504(self):
        timeout_error = minimax_service.httpx.TimeoutException("timeout")
        with (
            patch.object(minimax_service, "MINIMAX_ENABLED", True),
            patch.object(minimax_service, "MINIMAX_API_KEY", "test-key"),
            patch.object(
                minimax_service.httpx,
                "AsyncClient",
                return_value=StubAsyncClient(error=timeout_error),
            ),
        ):
            with self.assertRaises(minimax_service.MiniMaxServiceError) as ctx:
                await minimax_service.call_minimax_field_extraction(
                    filename="demo.pdf",
                    page_count=1,
                    full_text="测试内容",
                    result_json=[],
                    rule_fields=minimax_service._blank_fields(),
                )
        self.assertEqual(ctx.exception.status_code, 504)

    async def test_invalid_json_is_translated_to_502(self):
        payload = {
            "choices": [{"message": {"content": "not json"}}],
            "usage": {"total_tokens": 10},
        }
        with (
            patch.object(minimax_service, "MINIMAX_ENABLED", True),
            patch.object(minimax_service, "MINIMAX_API_KEY", "test-key"),
            patch.object(
                minimax_service.httpx,
                "AsyncClient",
                return_value=StubAsyncClient(response=StubResponse(payload=payload)),
            ),
        ):
            with self.assertRaises(minimax_service.MiniMaxServiceError) as ctx:
                await minimax_service.call_minimax_field_extraction(
                    filename="demo.pdf",
                    page_count=1,
                    full_text="测试内容",
                    result_json=[],
                    rule_fields=minimax_service._blank_fields(),
                )
        self.assertEqual(ctx.exception.status_code, 502)

    async def test_valid_response_is_normalized(self):
        payload = {
            "model": "MiniMax-M2.7",
            "choices": [
                {
                    "message": {
                        "content": json.dumps(
                            {
                                "档号": "A-001",
                                "文号": "测试〔2024〕1号",
                                "责任者": "某单位",
                                "题名": "关于测试的通知",
                                "日期": "2024-01-02",
                                "页数": 3,
                                "密级": "内部",
                                "备注": "",
                                "evidence": {"题名": "关于测试的通知"},
                            },
                            ensure_ascii=False,
                        )
                    }
                }
            ],
            "usage": {"total_tokens": 20},
        }
        with (
            patch.object(minimax_service, "MINIMAX_ENABLED", True),
            patch.object(minimax_service, "MINIMAX_API_KEY", "test-key"),
            patch.object(
                minimax_service.httpx,
                "AsyncClient",
                return_value=StubAsyncClient(response=StubResponse(payload=payload)),
            ),
        ):
            result = await minimax_service.call_minimax_field_extraction(
                filename="demo.pdf",
                page_count=3,
                full_text="关于测试的通知",
                result_json=[],
                rule_fields=minimax_service._blank_fields(),
            )
        self.assertEqual(result["provider"], "minimax")
        self.assertEqual(result["llm_fields"]["题名"], "关于测试的通知")
        self.assertEqual(result["llm_fields"]["页数"], "3")
        self.assertEqual(result["raw_usage"]["total_tokens"], 20)

    async def test_same_document_prompt_explains_fragment_page_count(self):
        captured_payload = {}

        async def _fake_post(payload, timeout_seconds=None):
            captured_payload["payload"] = payload
            return {
                "model": "MiniMax-M2.7",
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {
                                    "same_document": True,
                                    "confidence": 0.83,
                                    "evidence": "连续页示例",
                                },
                                ensure_ascii=False,
                            )
                        }
                    }
                ],
                "usage": {"total_tokens": 12},
            }

        with patch.object(minimax_service, "_post_minimax_chat_completions", side_effect=_fake_post):
            result = await minimax_service.call_minimax_same_document_judgement(
                left_filename="KJ-JJ-2017-02-001-001.jpg",
                left_page_count=1,
                left_full_text="预算书封面",
                left_rule_fields=minimax_service._blank_fields(),
                right_filename="KJ-JJ-2017-02-001-002.jpg",
                right_page_count=1,
                right_full_text="预算汇总表",
                right_rule_fields=minimax_service._blank_fields(),
            )

        prompt = captured_payload["payload"]["messages"][1]["content"]
        self.assertIn("不代表原始文档总页数", prompt)
        self.assertIn("文件名前缀一致且末尾页码连续", prompt)
        self.assertIn("当前片段页数", prompt)
        self.assertTrue(result["same_document"])
        self.assertEqual(result["confidence"], 0.83)

    async def test_response_with_think_prefix_is_normalized(self):
        body = {
            "档号": "A-002",
            "文号": "测试〔2024〕2号",
            "责任者": "某单位",
            "题名": "关于带思考标签的通知",
            "日期": "2024-02-03",
            "页数": 4,
            "密级": "",
            "备注": "",
            "evidence": {"题名": "关于带思考标签的通知"},
        }
        payload = {
            "model": "MiniMax-M2.7",
            "choices": [
                {
                    "message": {
                        "content": "<think>\ninternal reasoning\n</think>\n\n" + json.dumps(body, ensure_ascii=False)
                    }
                }
            ],
            "usage": {"total_tokens": 24},
        }
        with (
            patch.object(minimax_service, "MINIMAX_ENABLED", True),
            patch.object(minimax_service, "MINIMAX_API_KEY", "test-key"),
            patch.object(
                minimax_service.httpx,
                "AsyncClient",
                return_value=StubAsyncClient(response=StubResponse(payload=payload)),
            ),
        ):
            result = await minimax_service.call_minimax_field_extraction(
                filename="demo.pdf",
                page_count=4,
                full_text="关于带思考标签的通知",
                result_json=[],
                rule_fields=minimax_service._blank_fields(),
            )
        self.assertEqual(result["llm_fields"]["题名"], "关于带思考标签的通知")
        self.assertEqual(result["raw_usage"]["total_tokens"], 24)

    async def test_response_with_prose_wrapper_is_normalized(self):
        body = {
            "档号": "A-003",
            "文号": "测试〔2024〕3号",
            "责任者": "某单位",
            "题名": "关于带说明文本的通知",
            "日期": "2024-03-04",
            "页数": 2,
            "密级": "",
            "备注": "",
            "evidence": {"题名": "关于带说明文本的通知"},
        }
        payload = {
            "model": "MiniMax-M2.7",
            "choices": [
                {
                    "message": {
                        "content": "以下为抽取结果，请以 JSON 为准：\n" + json.dumps(body, ensure_ascii=False) + "\n说明：字段按证据整理。"
                    }
                }
            ],
            "usage": {"total_tokens": 26},
        }
        with (
            patch.object(minimax_service, "MINIMAX_ENABLED", True),
            patch.object(minimax_service, "MINIMAX_API_KEY", "test-key"),
            patch.object(
                minimax_service.httpx,
                "AsyncClient",
                return_value=StubAsyncClient(response=StubResponse(payload=payload)),
            ),
        ):
            result = await minimax_service.call_minimax_field_extraction(
                filename="demo.pdf",
                page_count=2,
                full_text="关于带说明文本的通知",
                result_json=[],
                rule_fields=minimax_service._blank_fields(),
            )
        self.assertEqual(result["llm_fields"]["题名"], "关于带说明文本的通知")
        self.assertEqual(result["raw_usage"]["total_tokens"], 26)


class FakeExecuteResult:
    def __init__(self, value=None):
        self.value = value

    def scalar_one_or_none(self):
        return self.value


class FakeDB:
    def __init__(self, existing_record=None):
        self.existing_record = existing_record

    async def execute(self, *_args, **_kwargs):
        return FakeExecuteResult(self.existing_record)


class MiniMaxRouteTests(unittest.TestCase):
    def setUp(self):
        self.db = FakeDB()
        self.app = FastAPI()
        self.app.include_router(router)

        async def override_get_db():
            yield self.db

        self.app.dependency_overrides[get_db] = override_get_db
        self.app.dependency_overrides[require_auth] = lambda: _MOCK_USER
        self.app.dependency_overrides[require_operator_access] = lambda: _MOCK_USER
        self.client = TestClient(self.app)

    def tearDown(self):
        self.client.close()

    def test_done_task_returns_comparison_payload(self):
        task = SimpleNamespace(
            id=1,
            status="done",
            filename="demo.pdf",
            file_path=str(Path("uploads") / "demo.pdf"),
            full_text="测试内容",
            result_json=[],
            page_count=1,
        )
        comparison = {
            "task_id": 1,
            "rule_fields": minimax_service._blank_fields(),
            "llm_fields": {**minimax_service._blank_fields(), "evidence": {}},
            "recommended_fields": minimax_service._blank_fields(),
            "conflicts": {},
            "agreement": {
                "matched": 8,
                "total": 8,
                "ratio": 1.0,
                "matched_fields": minimax_service.ARCHIVE_FIELDS,
                "mismatch_fields": [],
            },
            "provider": "minimax",
            "model": "MiniMax-M2.7",
            "raw_usage": {"total_tokens": 12},
        }

        with (
            patch("app.api.routes.get_task_detail", AsyncMock(return_value=task)),
            patch("app.api.routes.compare_rule_and_llm_fields", AsyncMock(return_value=comparison)),
        ):
            response = self.client.post("/api/ocr/tasks/1/ai-extract-fields")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["provider"], "minimax")

    def test_pending_task_is_rejected(self):
        task = SimpleNamespace(id=2, status="processing")
        compare_mock = AsyncMock()
        with (
            patch("app.api.routes.get_task_detail", AsyncMock(return_value=task)),
            patch("app.api.routes.compare_rule_and_llm_fields", compare_mock),
        ):
            response = self.client.post("/api/ocr/tasks/2/ai-extract-fields")

        self.assertEqual(response.status_code, 409)
        compare_mock.assert_not_awaited()

    def test_persist_without_conflicts_writes_archive_record(self):
        task = SimpleNamespace(
            id=3,
            status="done",
            filename="demo.pdf",
            file_path=r"D:\OCR\uploads\demo.pdf",
            full_text="测试内容",
            result_json=[],
            page_count=2,
        )
        self.db = FakeDB(existing_record=SimpleNamespace(batch_id="batch-1", batch_folder=r"D:\OCR\uploads"))
        self.app.dependency_overrides[get_db] = lambda: None

        async def override_get_db():
            yield self.db

        self.app.dependency_overrides[get_db] = override_get_db

        comparison = {
            "task_id": 3,
            "rule_fields": minimax_service._blank_fields(),
            "llm_fields": {**minimax_service._blank_fields(), "evidence": {}},
            "recommended_fields": {
                "档号": "A-001",
                "文号": "",
                "责任者": "某单位",
                "题名": "关于测试的通知",
                "日期": "2024-01-02",
                "页数": "2",
                "密级": "",
                "备注": "",
            },
            "conflicts": {},
            "agreement": {
                "matched": 6,
                "total": 8,
                "ratio": 0.75,
                "matched_fields": ["档号"],
                "mismatch_fields": ["责任者"],
            },
            "provider": "minimax",
            "model": "MiniMax-M2.7",
            "raw_usage": {},
        }

        save_mock = AsyncMock()
        with (
            patch("app.api.routes.get_task_detail", AsyncMock(return_value=task)),
            patch("app.api.routes.compare_rule_and_llm_fields", AsyncMock(return_value=comparison)),
            patch("app.api.routes.save_archive_record", save_mock),
        ):
            response = self.client.post("/api/ocr/tasks/3/ai-extract-fields", json={"persist": True})

        self.assertEqual(response.status_code, 200)
        save_mock.assert_awaited_once()
        self.assertEqual(save_mock.await_args.args[2], "batch-1")
        self.assertEqual(save_mock.await_args.args[4]["题名"], "关于测试的通知")

    def test_persist_with_conflicts_returns_409(self):
        task = SimpleNamespace(
            id=4,
            status="done",
            filename="demo.pdf",
            file_path=r"D:\OCR\uploads\demo.pdf",
            full_text="测试内容",
            result_json=[],
            page_count=2,
        )
        comparison = {
            "task_id": 4,
            "rule_fields": minimax_service._blank_fields(),
            "llm_fields": {**minimax_service._blank_fields(), "evidence": {}},
            "recommended_fields": minimax_service._blank_fields(),
            "conflicts": {"责任者": {"rule": "甲", "llm": "乙", "evidence": "乙"}}, 
            "agreement": {
                "matched": 7,
                "total": 8,
                "ratio": 0.875,
                "matched_fields": ["档号"],
                "mismatch_fields": ["责任者"],
            },
            "provider": "minimax",
            "model": "MiniMax-M2.7",
            "raw_usage": {},
        }

        save_mock = AsyncMock()
        with (
            patch("app.api.routes.get_task_detail", AsyncMock(return_value=task)),
            patch("app.api.routes.compare_rule_and_llm_fields", AsyncMock(return_value=comparison)),
            patch("app.api.routes.save_archive_record", save_mock),
        ):
            response = self.client.post("/api/ocr/tasks/4/ai-extract-fields", json={"persist": True})

        self.assertEqual(response.status_code, 409)
        save_mock.assert_not_awaited()


class BatchMergeRouteTests(unittest.TestCase):
    def setUp(self):
        self.db = FakeDB()
        self.app = FastAPI()
        self.app.include_router(router)

        async def override_get_db():
            yield self.db

        self.app.dependency_overrides[get_db] = override_get_db
        self.app.dependency_overrides[require_auth] = lambda: _MOCK_USER
        self.app.dependency_overrides[require_operator_access] = lambda: _MOCK_USER
        self.client = TestClient(self.app)

    def tearDown(self):
        self.client.close()

    def test_batch_merge_extract_success(self):
        payload = {
            "batch_id": "batch-1",
            "groups": [
                {
                    "group_id": "group-1",
                    "task_ids": [1, 2],
                    "filenames": ["a.pdf", "b.pdf"],
                    "same_document_confidence": 0.95,
                    "decision_reasons": ["文号完全一致。"],
                }
            ],
            "documents": [
                {
                    "group_id": "group-1",
                    "merged_page_count": 3,
                    "rule_fields": minimax_service._blank_fields(),
                    "llm_fields": {**minimax_service._blank_fields(), "evidence": {}},
                    "recommended_fields": minimax_service._blank_fields(),
                    "conflicts": {},
                    "agreement": {
                        "matched": 8,
                        "total": 8,
                        "ratio": 1.0,
                        "matched_fields": minimax_service.ARCHIVE_FIELDS,
                        "mismatch_fields": [],
                    },
                }
            ],
            "provider": "minimax",
            "model": "minimax-2.7",
            "raw_usage": {"total_tokens": 10},
            "generated_at": "2026-03-31T00:00:00+00:00",
            "summary": {
                "total_tasks": 2,
                "done_tasks": 2,
                "eligible_tasks": 2,
                "skipped_tasks": [],
                "groups_count": 1,
                "documents_count": 1,
            },
        }
        with patch("app.api.routes.get_batch_merge_extract_result", AsyncMock(return_value=payload)):
            response = self.client.post("/api/ocr/batches/batch-1/ai-merge-extract")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["batch_id"], "batch-1")
        self.assertEqual(response.json()["summary"]["groups_count"], 1)

    def test_batch_merge_extract_rejects_persist_true(self):
        service_mock = AsyncMock()
        with patch("app.api.routes.get_batch_merge_extract_result", service_mock):
            response = self.client.post("/api/ocr/batches/batch-1/ai-merge-extract", json={"persist": True})

        self.assertEqual(response.status_code, 400)
        service_mock.assert_not_awaited()

    def test_batch_merge_extract_returns_404_when_no_tasks(self):
        with patch("app.api.routes.get_batch_merge_extract_result", AsyncMock(return_value=None)):
            response = self.client.post("/api/ocr/batches/batch-empty/ai-merge-extract")

        self.assertEqual(response.status_code, 404)

    def test_batch_merge_extract_maps_minimax_error(self):
        with patch(
            "app.api.routes.get_batch_merge_extract_result",
            AsyncMock(side_effect=minimax_service.MiniMaxServiceError(504, "timeout")),
        ):
            response = self.client.post("/api/ocr/batches/batch-timeout/ai-merge-extract")

        self.assertEqual(response.status_code, 504)

    def test_batch_merge_extract_passes_force_refresh(self):
        payload = {
            "batch_id": "batch-1",
            "groups": [],
            "documents": [],
            "provider": "minimax",
            "model": "minimax-2.7",
            "raw_usage": {},
            "generated_at": "2026-03-31T00:00:00+00:00",
            "summary": {
                "total_tasks": 0,
                "done_tasks": 0,
                "eligible_tasks": 0,
                "skipped_tasks": [],
                "groups_count": 0,
                "documents_count": 0,
            },
        }
        merge_mock = AsyncMock(return_value=payload)
        with patch("app.api.routes.get_batch_merge_extract_result", merge_mock):
            self.client.post("/api/ocr/batches/batch-1/ai-merge-extract", json={"force_refresh": True})

        self.assertTrue(merge_mock.await_args.kwargs["force_refresh"])


class BatchEvaluationRouteTests(unittest.TestCase):
    def setUp(self):
        self.db = FakeDB()
        self.app = FastAPI()
        self.app.include_router(router)

        async def override_get_db():
            yield self.db

        self.app.dependency_overrides[get_db] = override_get_db
        self.app.dependency_overrides[get_db] = override_get_db
        self.app.dependency_overrides[require_auth] = lambda: _MOCK_USER
        self.app.dependency_overrides[require_operator_access] = lambda: _MOCK_USER
        self.client = TestClient(self.app)

    def tearDown(self):
        self.client.close()

    def test_get_truth_success(self):
        payload = {
            "batch_id": "batch-1",
            "tasks": [{"task_id": 1, "doc_key": "doc-a"}],
            "documents": [{"doc_key": "doc-a", "fields": minimax_service._blank_fields()}],
            "truth_updated_at": None,
        }
        with patch("app.api.routes.get_batch_evaluation_truth", AsyncMock(return_value=payload)):
            response = self.client.get("/api/ocr/batches/batch-1/evaluation-truth")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["batch_id"], "batch-1")

    def test_get_truth_maps_runtime_error_to_503(self):
        with patch("app.api.routes.get_batch_evaluation_truth", AsyncMock(side_effect=RuntimeError("db locked"))):
            response = self.client.get("/api/ocr/batches/batch-1/evaluation-truth")
        self.assertEqual(response.status_code, 503)

    def test_put_truth_validation_error(self):
        with patch("app.api.routes.save_batch_evaluation_truth", AsyncMock(side_effect=ValueError("invalid task"))):
            response = self.client.put(
                "/api/ocr/batches/batch-1/evaluation-truth",
                json={"tasks": [{"task_id": 1, "doc_key": "doc-a"}], "documents": []},
            )
        self.assertEqual(response.status_code, 400)

    def test_get_metrics_success(self):
        payload = {
            "batch_id": "batch-1",
            "operational_metrics": {"groups_count": 1},
            "truth_metrics": None,
            "compare_targets": ["rule", "llm", "recommended"],
            "generated_at": "2026-03-31T00:00:00+00:00",
            "truth_updated_at": None,
        }
        with patch("app.api.routes.get_batch_evaluation_metrics", AsyncMock(return_value=payload)):
            response = self.client.get("/api/ocr/batches/batch-1/evaluation-metrics")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["compare_targets"], ["rule", "llm", "recommended"])

    def test_get_metrics_404_when_missing_batch(self):
        with patch("app.api.routes.get_batch_evaluation_metrics", AsyncMock(return_value=None)):
            response = self.client.get("/api/ocr/batches/batch-1/evaluation-metrics")
        self.assertEqual(response.status_code, 404)

    def test_get_metrics_maps_runtime_error_to_503(self):
        with patch("app.api.routes.get_batch_evaluation_metrics", AsyncMock(side_effect=RuntimeError("cache miss"))):
            response = self.client.get("/api/ocr/batches/batch-1/evaluation-metrics")
        self.assertEqual(response.status_code, 503)

    def test_get_ai_report_success(self):
        payload = {
            "batch_id": "batch-1",
            "summary": "测试总结",
            "strengths": ["优势1"],
            "risks": ["风险1"],
            "recommendations": ["建议1"],
            "provider": "minimax",
            "model": "minimax-2.7",
            "generated_at": "2026-03-31T00:00:00+00:00",
            "raw_usage": {"total_tokens": 12},
        }
        with patch("app.api.routes.get_batch_evaluation_ai_report", AsyncMock(return_value=payload)):
            response = self.client.get("/api/ocr/batches/batch-1/evaluation-report")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["provider"], "minimax")

    def test_get_ai_report_404_when_missing_batch(self):
        with patch("app.api.routes.get_batch_evaluation_ai_report", AsyncMock(return_value=None)):
            response = self.client.get("/api/ocr/batches/batch-1/evaluation-report")

        self.assertEqual(response.status_code, 404)

    def test_get_ai_report_maps_minimax_error(self):
        with patch(
            "app.api.routes.get_batch_evaluation_ai_report",
            AsyncMock(side_effect=minimax_service.MiniMaxServiceError(504, "timeout")),
        ):
            response = self.client.get("/api/ocr/batches/batch-1/evaluation-report")

        self.assertEqual(response.status_code, 504)

    def test_batch_qa_success(self):
        payload = {
            "batch_id": "batch-1",
            "question": "该批次里有哪些验收结论？",
            "answer": "证据显示验收结论为通过。",
            "evidence": [
                {
                    "task_id": 1,
                    "filename": "a.pdf",
                    "snippet": "项目验收结论：通过。",
                    "score": 0.91,
                }
            ],
            "provider": "minimax",
            "model": "minimax-2.7",
            "raw_usage": {"total_tokens": 12},
            "generated_at": "2026-03-31T00:00:00+00:00",
        }
        with patch("app.api.routes.answer_batch_question", AsyncMock(return_value=payload)):
            response = self.client.post(
                "/api/ocr/batches/batch-1/qa",
                json={"question": "该批次里有哪些验收结论？", "top_k": 6},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["provider"], "minimax")

    def test_batch_qa_rejects_empty_question(self):
        qa_mock = AsyncMock()
        with patch("app.api.routes.answer_batch_question", qa_mock):
            response = self.client.post(
                "/api/ocr/batches/batch-1/qa",
                json={"question": "   ", "top_k": 6},
            )

        self.assertEqual(response.status_code, 400)
        qa_mock.assert_not_awaited()

    def test_batch_qa_returns_404_when_no_tasks(self):
        with patch("app.api.routes.answer_batch_question", AsyncMock(return_value=None)):
            response = self.client.post(
                "/api/ocr/batches/batch-empty/qa",
                json={"question": "测试问题", "top_k": 6},
            )

        self.assertEqual(response.status_code, 404)

    def test_batch_qa_maps_minimax_error(self):
        with patch(
            "app.api.routes.answer_batch_question",
            AsyncMock(side_effect=minimax_service.MiniMaxServiceError(504, "timeout")),
        ):
            response = self.client.post(
                "/api/ocr/batches/batch-timeout/qa",
                json={"question": "测试问题", "top_k": 6},
            )

        self.assertEqual(response.status_code, 504)


if __name__ == "__main__":
    unittest.main()
