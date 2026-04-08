import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from app.services import batch_evaluation_service as evaluation_service


ARCHIVE_FIELDS = ["档号", "文号", "责任者", "题名", "日期", "页数", "密级", "备注"]


def _filled_fields(title: str) -> dict[str, str]:
    return {
        "档号": f"A-{title}",
        "文号": f"文号-{title}",
        "责任者": "测试单位",
        "题名": title,
        "日期": "2026-01-01",
        "页数": "2",
        "密级": "内部",
        "备注": "无",
    }


def _merge_result() -> dict:
    doc_a = _filled_fields("文档A")
    doc_b = _filled_fields("文档B")
    return {
        "batch_id": "batch-1",
        "generated_at": "2026-03-31T00:00:00+00:00",
        "groups": [
            {
                "group_id": "group-1",
                "task_ids": [1, 2],
                "filenames": ["a1.pdf", "a2.pdf"],
                "same_document_confidence": 0.95,
                "decision_reasons": ["文号一致"],
            },
            {
                "group_id": "group-2",
                "task_ids": [3],
                "filenames": ["b1.pdf"],
                "same_document_confidence": 1.0,
                "decision_reasons": ["单文件组"],
            },
        ],
        "documents": [
            {
                "group_id": "group-1",
                "merged_page_count": 2,
                "rule_fields": dict(doc_a),
                "llm_fields": {**doc_a, "evidence": {field: "" for field in ARCHIVE_FIELDS}},
                "recommended_fields": dict(doc_a),
                "conflicts": {},
                "agreement": {"ratio": 1.0},
            },
            {
                "group_id": "group-2",
                "merged_page_count": 1,
                "rule_fields": dict(doc_b),
                "llm_fields": {**doc_b, "evidence": {field: "" for field in ARCHIVE_FIELDS}},
                "recommended_fields": dict(doc_b),
                "conflicts": {"文号": {"rule": "x", "llm": "y", "evidence": "y"}},
                "agreement": {"ratio": 0.875},
            },
        ],
    }


def _truth_data() -> dict:
    return {
        "batch_id": "batch-1",
        "tasks": [
            {"task_id": 1, "doc_key": "doc-A"},
            {"task_id": 2, "doc_key": "doc-A"},
            {"task_id": 3, "doc_key": "doc-B"},
        ],
        "documents": [
            {"doc_key": "doc-A", "fields": _filled_fields("文档A")},
            {"doc_key": "doc-B", "fields": _filled_fields("文档B")},
        ],
        "truth_updated_at": "2026-03-31T00:00:10+00:00",
    }


class BatchEvaluationServiceTests(unittest.IsolatedAsyncioTestCase):
    def test_operational_metrics_contains_expected_sections(self):
        payload = evaluation_service._build_operational_metrics(_merge_result())
        self.assertEqual(payload["groups_count"], 2)
        self.assertEqual(payload["documents_count"], 2)
        self.assertIn("field_fill_rate", payload)
        self.assertGreater(payload["field_fill_rate"]["recommended"], 0.9)
        self.assertGreater(payload["conflict_rate"], 0)

    def test_truth_metrics_perfect_alignment(self):
        metrics = evaluation_service._build_truth_metrics(_merge_result(), _truth_data())
        self.assertIsNotNone(metrics)
        self.assertEqual(metrics["grouping"]["pairwise_f1"], 1.0)
        self.assertEqual(metrics["grouping"]["task_assignment_accuracy"], 1.0)
        self.assertEqual(metrics["field_accuracy"]["recommended"]["overall_accuracy"], 1.0)

    def test_truth_metrics_returns_none_without_truth(self):
        metrics = evaluation_service._build_truth_metrics(_merge_result(), {"tasks": [], "documents": []})
        self.assertIsNone(metrics)

    async def test_get_metrics_uses_cache_when_available(self):
        cached = {"batch_id": "batch-1", "cached": True}
        with (
            patch.object(
                evaluation_service,
                "get_batch_merge_extract_result",
                AsyncMock(return_value=_merge_result()),
            ),
            patch.object(
                evaluation_service,
                "get_batch_evaluation_truth",
                AsyncMock(return_value=_truth_data()),
            ),
            patch.object(evaluation_service, "cache_get", return_value=cached),
            patch.object(evaluation_service, "cache_set") as cache_set_mock,
        ):
            result = await evaluation_service.get_batch_evaluation_metrics(
                db=SimpleNamespace(),
                batch_id="batch-1",
                force_refresh=False,
            )
        self.assertEqual(result, cached)
        cache_set_mock.assert_not_called()

    async def test_save_truth_rejects_task_outside_batch(self):
        db = SimpleNamespace(execute=AsyncMock(), commit=AsyncMock())
        with patch.object(evaluation_service, "_load_valid_batch_task_ids", AsyncMock(return_value={1})):
            with self.assertRaises(ValueError):
                await evaluation_service.save_batch_evaluation_truth(
                    db=db,
                    batch_id="batch-1",
                    tasks=[{"task_id": 9, "doc_key": "doc-x"}],
                    documents=[],
                )

    async def test_get_ai_report_returns_none_when_merge_missing(self):
        with patch.object(evaluation_service, "get_batch_merge_extract_result", AsyncMock(return_value=None)):
            result = await evaluation_service.get_batch_evaluation_ai_report(
                db=SimpleNamespace(),
                batch_id="batch-1",
                force_refresh=False,
            )
        self.assertIsNone(result)

    async def test_get_ai_report_uses_cache_when_available(self):
        cached = {"batch_id": "batch-1", "summary": "cached"}
        with (
            patch.object(evaluation_service, "get_batch_merge_extract_result", AsyncMock(return_value=_merge_result())),
            patch.object(evaluation_service, "get_batch_evaluation_truth", AsyncMock(return_value=_truth_data())),
            patch.object(evaluation_service, "cache_get", return_value=cached),
            patch.object(evaluation_service, "get_batch_evaluation_metrics", AsyncMock()) as metrics_mock,
            patch.object(evaluation_service, "call_minimax_batch_evaluation_report", AsyncMock()) as llm_mock,
        ):
            result = await evaluation_service.get_batch_evaluation_ai_report(
                db=SimpleNamespace(),
                batch_id="batch-1",
                force_refresh=False,
            )
        self.assertEqual(result, cached)
        metrics_mock.assert_not_awaited()
        llm_mock.assert_not_awaited()

    async def test_get_ai_report_builds_payload(self):
        llm_payload = {
            "summary": "诊断总结",
            "strengths": ["优势"],
            "risks": ["风险"],
            "recommendations": ["建议"],
            "provider": "minimax",
            "model": "minimax-2.7",
            "raw_usage": {"total_tokens": 12},
        }
        metrics_payload = {
            "batch_id": "batch-1",
            "operational_metrics": {},
            "truth_metrics": None,
            "compare_targets": ["rule", "llm", "recommended"],
            "generated_at": "2026-03-31T00:00:00+00:00",
            "truth_updated_at": None,
        }
        with (
            patch.object(evaluation_service, "get_batch_merge_extract_result", AsyncMock(return_value=_merge_result())),
            patch.object(evaluation_service, "get_batch_evaluation_truth", AsyncMock(return_value=_truth_data())),
            patch.object(evaluation_service, "cache_get", return_value=None),
            patch.object(evaluation_service, "get_batch_evaluation_metrics", AsyncMock(return_value=metrics_payload)),
            patch.object(
                evaluation_service,
                "call_minimax_batch_evaluation_report",
                AsyncMock(return_value=llm_payload),
            ) as llm_mock,
            patch.object(evaluation_service, "cache_set") as cache_set_mock,
        ):
            result = await evaluation_service.get_batch_evaluation_ai_report(
                db=SimpleNamespace(),
                batch_id="batch-1",
                force_refresh=False,
            )

        self.assertEqual(result["summary"], "诊断总结")
        self.assertEqual(result["provider"], "minimax")
        self.assertEqual(result["raw_usage"]["total_tokens"], 12)
        self.assertIn("generated_at", result)
        llm_mock.assert_awaited_once()
        cache_set_mock.assert_called_once()


if __name__ == "__main__":
    unittest.main()
