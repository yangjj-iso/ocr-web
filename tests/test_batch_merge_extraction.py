import unittest
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from app.services import batch_merge_extraction_service as batch_service


ARCHIVE_KEYS = ["档号", "文号", "责任者", "题名", "日期", "页数", "密级", "备注"]


def _fields(**kwargs):
    base = {key: "" for key in ARCHIVE_KEYS}
    base.update(kwargs)
    return base


def _comparison_payload():
    return {
        "rule_fields": _fields(题名="合并文档"),
        "llm_fields": {**_fields(题名="合并文档"), "evidence": {key: "" for key in ARCHIVE_KEYS}},
        "recommended_fields": _fields(题名="合并文档"),
        "conflicts": {},
        "agreement": {
            "matched": 8,
            "total": 8,
            "ratio": 1.0,
            "matched_fields": ARCHIVE_KEYS,
            "mismatch_fields": [],
        },
        "provider": "minimax",
        "model": "minimax-2.7",
        "raw_usage": {"total_tokens": 20},
    }


def _task(task_id: int, filename: str, *, status: str = "done", full_text: str = "测试内容", page_count: int = 1):
    created_at = datetime(2026, 1, 1) + timedelta(minutes=task_id)
    return SimpleNamespace(
        id=task_id,
        filename=filename,
        file_path=f"D:/OCR/uploads/{filename}",
        file_type=".pdf",
        status=status,
        full_text=full_text,
        result_json=[],
        page_count=page_count,
        created_at=created_at,
    )


class BatchMergeExtractionTests(unittest.IsolatedAsyncioTestCase):
    def test_filename_sequence_prefers_trailing_serial(self):
        sequence = batch_service._extract_filename_sequence("模版文件/0313/WS·2024·D10-0313-014.jpg")
        self.assertEqual(sequence, 14)

    async def test_same_series_neighbors_merge_without_llm(self):
        tasks = [
            _task(1, "模版文件/0313/WS·2024·D10-0313-001.jpg", page_count=1),
            _task(2, "模版文件/0313/WS·2024·D10-0313-002.jpg", page_count=1),
            _task(3, "模版文件/0313/WS·2024·D10-0313-003.jpg", page_count=1),
        ]
        llm_same_doc = AsyncMock()
        with (
            patch.object(batch_service, "_load_batch_tasks", AsyncMock(return_value=tasks)),
            patch.object(
                batch_service,
                "extract_fields",
                side_effect=[
                    _fields(),
                    _fields(),
                    _fields(),
                ],
            ),
            patch.object(
                batch_service,
                "compare_rule_and_llm_fields_for_content",
                AsyncMock(return_value=_comparison_payload()),
            ) as compare_mock,
            patch.object(batch_service, "call_minimax_same_document_judgement", llm_same_doc),
        ):
            result = await batch_service.batch_merge_extract_fields(
                db=SimpleNamespace(),
                batch_id="batch-seq",
                include_evidence=True,
            )

        self.assertEqual(result["summary"]["groups_count"], 1)
        llm_same_doc.assert_not_awaited()
        compare_mock.assert_awaited_once()

    async def test_returns_none_when_no_eligible_tasks(self):
        tasks = [
            _task(1, "A.pdf", status="processing"),
            _task(2, "B.pdf", status="done", full_text=""),
        ]
        with patch.object(batch_service, "_load_batch_tasks", AsyncMock(return_value=tasks)):
            result = await batch_service.batch_merge_extract_fields(
                db=SimpleNamespace(),
                batch_id="batch-x",
                include_evidence=True,
            )
        self.assertIsNone(result)

    async def test_doc_no_match_groups_without_llm(self):
        tasks = [
            _task(1, "part-1.pdf", page_count=2),
            _task(2, "part-2.pdf", page_count=3),
        ]
        llm_same_doc = AsyncMock()
        with (
            patch.object(batch_service, "_load_batch_tasks", AsyncMock(return_value=tasks)),
            patch.object(
                batch_service,
                "extract_fields",
                side_effect=[
                    _fields(文号="国档〔2026〕1号", 题名="关于测试的通知"),
                    _fields(文号="国档〔2026〕1号", 题名="关于测试的通知"),
                ],
            ),
            patch.object(
                batch_service,
                "compare_rule_and_llm_fields_for_content",
                AsyncMock(return_value=_comparison_payload()),
            ) as compare_mock,
            patch.object(
                batch_service,
                "call_minimax_same_document_judgement",
                llm_same_doc,
            ),
        ):
            result = await batch_service.batch_merge_extract_fields(
                db=SimpleNamespace(),
                batch_id="batch-doc-no",
                include_evidence=True,
            )

        self.assertIsNotNone(result)
        self.assertEqual(result["summary"]["groups_count"], 1)
        self.assertEqual(result["groups"][0]["task_ids"], [1, 2])
        self.assertIn("文号完全一致", result["groups"][0]["decision_reasons"][0])
        llm_same_doc.assert_not_awaited()
        compare_mock.assert_awaited_once()

    async def test_uncertain_pair_uses_llm_when_above_threshold(self):
        tasks = [
            _task(1, "项目总结上册.pdf", page_count=2),
            _task(2, "项目总结下册.pdf", page_count=2),
        ]
        with (
            patch.object(batch_service, "_load_batch_tasks", AsyncMock(return_value=tasks)),
            patch.object(
                batch_service,
                "extract_fields",
                side_effect=[
                    _fields(题名="项目总结（上）", 日期="2026-01-01", 责任者="测试单位"),
                    _fields(题名="项目总结（下）", 日期="2026-01-01", 责任者="测试单位"),
                ],
            ),
            patch.object(
                batch_service,
                "call_minimax_same_document_judgement",
                AsyncMock(
                    return_value={
                        "provider": "minimax",
                        "model": "minimax-2.7",
                        "raw_usage": {"total_tokens": 15},
                        "same_document": True,
                        "confidence": 0.96,
                        "evidence": "标题和日期均连续一致。",
                    }
                ),
            ),
            patch.object(
                batch_service,
                "compare_rule_and_llm_fields_for_content",
                AsyncMock(return_value=_comparison_payload()),
            ),
        ):
            result = await batch_service.batch_merge_extract_fields(
                db=SimpleNamespace(),
                batch_id="batch-llm-pass",
                include_evidence=True,
            )

        self.assertEqual(result["summary"]["groups_count"], 1)
        reasons_text = " ".join(result["groups"][0]["decision_reasons"])
        self.assertIn("LLM高置信判定同文档", reasons_text)

    async def test_low_confidence_llm_keeps_tasks_separate(self):
        tasks = [
            _task(1, "项目总结上册.pdf", page_count=2),
            _task(2, "项目总结下册.pdf", page_count=2),
        ]
        compare_mock = AsyncMock(return_value=_comparison_payload())
        with (
            patch.object(batch_service, "_load_batch_tasks", AsyncMock(return_value=tasks)),
            patch.object(
                batch_service,
                "extract_fields",
                side_effect=[
                    _fields(题名="项目总结（上）", 日期="2026-01-01", 责任者="测试单位"),
                    _fields(题名="项目总结（下）", 日期="2026-01-01", 责任者="测试单位"),
                ],
            ),
            patch.object(
                batch_service,
                "call_minimax_same_document_judgement",
                AsyncMock(
                    return_value={
                        "provider": "minimax",
                        "model": "minimax-2.7",
                        "raw_usage": {"total_tokens": 15},
                        "same_document": True,
                        "confidence": 0.75,
                        "evidence": "信息接近，但不够确定。",
                    }
                ),
            ),
            patch.object(batch_service, "compare_rule_and_llm_fields_for_content", compare_mock),
        ):
            result = await batch_service.batch_merge_extract_fields(
                db=SimpleNamespace(),
                batch_id="batch-llm-fail",
                include_evidence=True,
            )

        self.assertEqual(result["summary"]["groups_count"], 2)
        self.assertEqual(len(result["groups"]), 2)
        self.assertEqual(compare_mock.await_count, 2)

    async def test_weak_uncertain_pair_is_skipped_without_llm(self):
        tasks = [
            _task(1, "alpha-report.pdf", page_count=1),
            _task(2, "beta-report.pdf", page_count=1),
        ]
        llm_same_doc = AsyncMock()
        compare_mock = AsyncMock(return_value=_comparison_payload())
        with (
            patch.object(batch_service, "_load_batch_tasks", AsyncMock(return_value=tasks)),
            patch.object(
                batch_service,
                "extract_fields",
                side_effect=[
                    _fields(日期="2026-01-01"),
                    _fields(日期="2026-01-01"),
                ],
            ),
            patch.object(batch_service, "call_minimax_same_document_judgement", llm_same_doc),
            patch.object(batch_service, "compare_rule_and_llm_fields_for_content", compare_mock),
        ):
            result = await batch_service.batch_merge_extract_fields(
                db=SimpleNamespace(),
                batch_id="batch-skip-weak-pair",
                include_evidence=True,
            )

        self.assertEqual(result["summary"]["groups_count"], 2)
        llm_same_doc.assert_not_awaited()
        self.assertEqual(compare_mock.await_count, 2)

    async def test_same_document_judgement_error_does_not_abort_batch(self):
        tasks = [
            _task(1, "项目总结上册.pdf", page_count=1),
            _task(2, "项目总结下册.pdf", page_count=1),
        ]
        compare_mock = AsyncMock(return_value=_comparison_payload())
        with (
            patch.object(batch_service, "_load_batch_tasks", AsyncMock(return_value=tasks)),
            patch.object(
                batch_service,
                "extract_fields",
                side_effect=[
                    _fields(题名="项目总结（上）", 日期="2026-01-01", 责任者="测试单位"),
                    _fields(题名="项目总结（下）", 日期="2026-01-01", 责任者="测试单位"),
                ],
            ),
            patch.object(
                batch_service,
                "call_minimax_same_document_judgement",
                AsyncMock(side_effect=RuntimeError("bad llm payload")),
            ),
            patch.object(batch_service, "compare_rule_and_llm_fields_for_content", compare_mock),
        ):
            result = await batch_service.batch_merge_extract_fields(
                db=SimpleNamespace(),
                batch_id="batch-llm-error",
                include_evidence=True,
            )

        self.assertEqual(result["summary"]["groups_count"], 2)
        self.assertEqual(compare_mock.await_count, 2)

    async def test_get_batch_merge_extract_result_uses_cache_when_task_set_matches(self):
        cached = {
            "batch_id": "batch-cache",
            "groups": [{"group_id": "group-1", "task_ids": [1], "filenames": ["a.pdf"], "same_document_confidence": 1.0, "decision_reasons": []}],
            "documents": [],
            "provider": "minimax",
            "model": "MiniMax-M2.7",
            "raw_usage": {},
            "summary": {
                "total_tasks": 1,
                "done_tasks": 1,
                "eligible_tasks": 1,
                "skipped_tasks": [],
                "groups_count": 1,
                "documents_count": 0,
            },
            "generated_at": "2026-04-01T00:00:00+00:00",
        }
        tasks = [_task(1, "a.pdf", status="done", full_text="内容")]
        with (
            patch.object(batch_service, "cache_get", return_value=cached),
            patch.object(batch_service, "_load_batch_tasks", AsyncMock(return_value=tasks)),
            patch.object(batch_service, "cache_delete") as cache_delete_mock,
            patch.object(batch_service, "batch_merge_extract_fields", AsyncMock()) as compute_mock,
        ):
            result = await batch_service.get_batch_merge_extract_result(
                db=SimpleNamespace(),
                batch_id="batch-cache",
                include_evidence=True,
                force_refresh=False,
            )
        self.assertEqual(result["batch_id"], "batch-cache")
        self.assertEqual(result["groups"][0]["task_ids"], [1])
        cache_delete_mock.assert_not_called()
        compute_mock.assert_not_awaited()

    async def test_get_batch_merge_extract_result_recomputes_when_cached_group_is_stale(self):
        cached = {
            "batch_id": "batch-stale",
            "groups": [{"group_id": "group-1", "task_ids": [999], "filenames": ["x.pdf"], "same_document_confidence": 1.0, "decision_reasons": []}],
            "documents": [],
            "provider": "minimax",
            "model": "MiniMax-M2.7",
            "raw_usage": {},
            "summary": {
                "total_tasks": 1,
                "done_tasks": 1,
                "eligible_tasks": 1,
                "skipped_tasks": [],
                "groups_count": 1,
                "documents_count": 0,
            },
            "generated_at": "2026-04-01T00:00:00+00:00",
        }
        tasks = [_task(1, "a.pdf", status="done", full_text="内容")]
        computed = {
            "batch_id": "batch-stale",
            "groups": [{"group_id": "group-1", "task_ids": [1], "filenames": ["a.pdf"], "same_document_confidence": 1.0, "decision_reasons": []}],
            "documents": [],
            "provider": "minimax",
            "model": "MiniMax-M2.7",
            "raw_usage": {},
            "summary": {
                "total_tasks": 1,
                "done_tasks": 1,
                "eligible_tasks": 1,
                "skipped_tasks": [],
                "groups_count": 1,
                "documents_count": 0,
            },
        }
        with (
            patch.object(batch_service, "cache_get", return_value=cached),
            patch.object(batch_service, "_load_batch_tasks", AsyncMock(return_value=tasks)),
            patch.object(batch_service, "cache_delete") as cache_delete_mock,
            patch.object(batch_service, "batch_merge_extract_fields", AsyncMock(return_value=computed)) as compute_mock,
            patch.object(batch_service, "cache_set") as cache_set_mock,
        ):
            result = await batch_service.get_batch_merge_extract_result(
                db=SimpleNamespace(),
                batch_id="batch-stale",
                include_evidence=True,
                force_refresh=False,
            )
        self.assertEqual(result["groups"][0]["task_ids"], [1])
        cache_delete_mock.assert_called_once()
        compute_mock.assert_awaited_once()
        cache_set_mock.assert_called_once()


if __name__ == "__main__":
    unittest.main()
