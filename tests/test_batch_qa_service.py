import unittest
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from app.services import batch_qa_service


def _candidate(
    *,
    task_id: int = 1,
    filename: str = "demo.pdf",
    full_text: str = "",
    metadata_text: str = "",
) -> batch_qa_service.QATaskCandidate:
    return batch_qa_service.QATaskCandidate(
        task_id=task_id,
        filename=filename,
        full_text=full_text,
        metadata_text=metadata_text,
        updated_at=datetime(2026, 3, 31, 0, 0, 0),
    )


class BatchQAServiceUnitTests(unittest.TestCase):
    def test_split_text_chunks_respects_overlap(self):
        text = "".join(chr(65 + (index % 26)) for index in range(1500))
        chunks = batch_qa_service.split_text_chunks(text, chunk_size=600, overlap=120)

        self.assertGreaterEqual(len(chunks), 3)
        self.assertLessEqual(max(len(chunk) for chunk in chunks), 600)
        self.assertEqual(chunks[0][-120:], chunks[1][:120])

    def test_tokenize_query_mixed_language(self):
        tokens = batch_qa_service._tokenize_query("2024 ProjectA 文号 A-12")
        self.assertIn("2024", tokens)
        self.assertIn("projecta", tokens)
        self.assertIn("文号", tokens)

    def test_normalize_text_preserves_cjk_and_ascii(self):
        normalized = batch_qa_service._normalize_text("预算汇总表的工程直接工程费合计是多少？ Project-A/2024")
        self.assertIn("预算汇总表的工程直接工程费合计是多少", normalized)
        self.assertIn("projecta2024", normalized)

    def test_tokenize_query_pure_cjk_not_empty(self):
        tokens = batch_qa_service._tokenize_query("预算汇总表的工程直接工程费合计是多少？")
        self.assertGreater(len(tokens), 0)

    def test_tokenize_query_keeps_key_phrases_and_strips_fillers(self):
        tokens = batch_qa_service._tokenize_query("这批材料主要涉及什么会议或通知？会议时间是什么时候？")
        self.assertIn("会议时间", tokens)
        self.assertIn("会议", tokens)
        self.assertIn("通知", tokens)
        self.assertNotIn("这批", tokens)
        self.assertNotIn("什么", tokens)

    def test_ranked_evidence_prefers_phrase_match(self):
        candidates = [
            _candidate(
                task_id=10,
                filename="a.pdf",
                full_text="这是背景介绍。\n\n项目验收结论是：通过并归档。",
                metadata_text="项目验收 文号A-1",
            )
        ]
        evidence = batch_qa_service.build_ranked_evidence(candidates, "项目验收结论", top_k=1)

        self.assertEqual(len(evidence), 1)
        self.assertEqual(evidence[0]["task_id"], 10)
        self.assertIn("项目验收结论", evidence[0]["snippet"])
        self.assertGreater(evidence[0]["score"], 0)


class BatchQAServiceAsyncTests(unittest.IsolatedAsyncioTestCase):
    async def test_answer_batch_question_uses_cache(self):
        cached = {
            "batch_id": "batch-1",
            "question": "测试问题",
            "answer": "缓存答案",
            "evidence": [],
            "qa_id": 12,
            "support_level": "supported",
            "confidence": 0.88,
            "citations": [],
            "provider": "cache",
            "model": "cache",
            "raw_usage": {},
            "generated_at": "2026-03-31T00:00:00+00:00",
        }

        with (
            patch.object(batch_qa_service, "_load_batch_candidates", AsyncMock(return_value=[_candidate(full_text="abc")])),
            patch.object(batch_qa_service, "cache_get", return_value=cached),
            patch.object(batch_qa_service, "cache_set") as cache_set_mock,
            patch.object(batch_qa_service, "call_minimax_batch_qa_answer", AsyncMock()) as llm_mock,
        ):
            result = await batch_qa_service.answer_batch_question(
                db=SimpleNamespace(),
                batch_id="batch-1",
                question="测试问题",
                top_k=8,
                persist=False,
            )

        self.assertEqual(result, cached)
        llm_mock.assert_not_awaited()
        cache_set_mock.assert_not_called()

    async def test_answer_batch_question_rejects_low_score_without_llm(self):
        with (
            patch.object(
                batch_qa_service,
                "_load_batch_candidates",
                AsyncMock(return_value=[_candidate(full_text="abcdefg", metadata_text="demo")]),
            ),
            patch.object(batch_qa_service, "cache_get", return_value=None),
            patch.object(batch_qa_service, "cache_set") as cache_set_mock,
            patch.object(batch_qa_service, "call_minimax_batch_qa_answer", AsyncMock()) as llm_mock,
        ):
            result = await batch_qa_service.answer_batch_question(
                db=SimpleNamespace(),
                batch_id="batch-1",
                question="与证据完全不相关的问题",
                top_k=8,
                persist=False,
            )

        self.assertEqual(result["provider"], "retrieval")
        self.assertEqual(result["support_level"], "insufficient")
        self.assertIn("无法确认", result["answer"])
        llm_mock.assert_not_awaited()
        cache_set_mock.assert_called_once()

    async def test_answer_batch_question_calls_llm_and_support_check(self):
        llm_payload = {
            "provider": "minimax",
            "model": "minimax-2.7",
            "raw_usage": {"total_tokens": 10},
            "answer": "项目验收结论为通过。",
            "citations": [1],
        }
        check_payload = {
            "provider": "minimax",
            "model": "minimax-2.7",
            "raw_usage": {"output_tokens": 8},
            "support_level": "supported",
            "confidence": 0.92,
            "suggestion": "",
        }

        with (
            patch.object(
                batch_qa_service,
                "_load_batch_candidates",
                AsyncMock(
                    return_value=[
                        _candidate(
                            full_text="项目验收结论：通过。",
                            metadata_text="项目验收 文号A-1",
                        )
                    ]
                ),
            ),
            patch.object(batch_qa_service, "cache_get", return_value=None),
            patch.object(batch_qa_service, "cache_set") as cache_set_mock,
            patch.object(
                batch_qa_service,
                "call_minimax_batch_qa_answer",
                AsyncMock(return_value=llm_payload),
            ) as llm_mock,
            patch.object(
                batch_qa_service,
                "call_minimax_batch_qa_support_check",
                AsyncMock(return_value=check_payload),
            ) as check_mock,
        ):
            result = await batch_qa_service.answer_batch_question(
                db=SimpleNamespace(),
                batch_id="batch-1",
                question="项目验收结论是什么？",
                top_k=8,
                persist=False,
            )

        self.assertEqual(result["provider"], "minimax")
        self.assertEqual(result["support_level"], "supported")
        self.assertEqual(result["answer"], "项目验收结论为通过。")
        self.assertGreater(len(result["evidence"]), 0)
        self.assertEqual(result["citations"][0]["evidence_index"], 1)
        self.assertEqual(result["raw_usage"]["total_tokens"], 10)
        self.assertEqual(result["raw_usage"]["output_tokens"], 8)
        llm_mock.assert_awaited_once()
        check_mock.assert_awaited_once()
        cache_set_mock.assert_called_once()

    async def test_answer_batch_question_downgrades_when_support_insufficient(self):
        llm_payload = {
            "provider": "minimax",
            "model": "minimax-2.7",
            "raw_usage": {"total_tokens": 10},
            "answer": "一个可能不可靠的答案。",
            "citations": [1],
        }
        check_payload = {
            "provider": "minimax",
            "model": "minimax-2.7",
            "raw_usage": {"output_tokens": 8},
            "support_level": "insufficient",
            "confidence": 0.21,
            "suggestion": "证据不足",
        }

        with (
            patch.object(
                batch_qa_service,
                "_load_batch_candidates",
                AsyncMock(
                    return_value=[
                        _candidate(
                            full_text="这是一段非常短的内容。",
                            metadata_text="demo",
                        )
                    ]
                ),
            ),
            patch.object(batch_qa_service, "cache_get", return_value=None),
            patch.object(batch_qa_service, "cache_set"),
            patch.object(
                batch_qa_service,
                "call_minimax_batch_qa_answer",
                AsyncMock(return_value=llm_payload),
            ),
            patch.object(
                batch_qa_service,
                "call_minimax_batch_qa_support_check",
                AsyncMock(return_value=check_payload),
            ),
        ):
            result = await batch_qa_service.answer_batch_question(
                db=SimpleNamespace(),
                batch_id="batch-1",
                question="这份材料讲了什么？",
                top_k=8,
                persist=False,
            )

        self.assertEqual(result["support_level"], "insufficient")
        self.assertIn("无法确认", result["answer"])
        self.assertEqual(result["citations"], [])


if __name__ == "__main__":
    unittest.main()
