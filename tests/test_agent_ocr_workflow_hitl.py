import asyncio
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.services import agent_ocr_workflow as workflow


class _FakePageGraph:
    async def ainvoke(self, state):
        page_num = int(state["page_num"])
        fields = {
            "档号": "TEST-001",
            "文号": "DOC-001",
            "责任者": "测试单位",
            "题名": "测试材料",
            "日期": "2026-04-09",
            "页数": "3",
            "密级": "",
            "备注": "",
        }
        confidence = 0.95
        human_review = False
        review_reason = ""
        if page_num == 2:
            confidence = 0.62
            human_review = True
            review_reason = "第二页金额模糊，需要人工确认。"
        page = {
            "page_num": page_num,
            "regions": [],
            "lines": [{"line_num": 1, "text": f"第{page_num}页正文", "confidence": confidence, "bbox": []}],
            "agent_meta": {
                "confidence": confidence,
                "issues": [] if page_num != 2 else ["金额模糊"],
                "source": "hybrid",
                "fields": fields,
                "human_review": human_review,
                "review_reason": review_reason,
            },
        }
        return {
            "page_output": {
                "page_num": page_num,
                "page": page,
                "fields": fields,
                "confidence": confidence,
                "issues": [] if page_num != 2 else ["金额模糊"],
                "source": "hybrid",
                "retry_count": 0,
                "processing_strategy": "none",
                "human_review": human_review,
                "review_reason": review_reason,
            }
        }


class AgentWorkflowHitlTests(unittest.TestCase):
    def setUp(self):
        workflow.get_batch_supervisor_graph.cache_clear()
        workflow.get_langgraph_checkpointer.cache_clear()

    def tearDown(self):
        workflow.get_batch_supervisor_graph.cache_clear()
        workflow.get_langgraph_checkpointer.cache_clear()

    def test_workflow_interrupts_and_resumes_with_same_thread(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            pdf_path = temp_root / "sample.pdf"
            pdf_path.write_bytes(b"%PDF-1.4 fake")
            page_paths = []
            callback_events = []
            for index in range(3):
                page_path = temp_root / f"page-{index + 1}.jpg"
                page_path.write_bytes(b"fake-jpg")
                page_paths.append(str(page_path))

            async def event_callback(event_type, payload, progress):
                callback_events.append(
                    {
                        "event_type": event_type,
                        "payload": dict(payload),
                        "progress": dict(progress),
                    }
                )

            with patch.object(workflow, "pdf_to_images", return_value=page_paths), patch.object(
                workflow,
                "get_page_agent_graph",
                return_value=_FakePageGraph(),
            ):
                interrupted = asyncio.run(
                    workflow.run_hierarchical_ocr_detached(
                        task_id=101,
                        filename="sample.pdf",
                        file_path=str(pdf_path),
                        mode="layout",
                        batch_id="batch-hitl",
                        event_callback=event_callback,
                        workflow_thread_id="thread-hitl-001",
                    )
                )
                self.assertEqual("INTERRUPTED", interrupted["status"])
                self.assertEqual("thread-hitl-001", interrupted["workflow_thread_id"])
                self.assertEqual(2, interrupted["page_count"])
                self.assertEqual(2, interrupted["interrupt_payload"]["page_num"])

                resumed = asyncio.run(
                    workflow.run_hierarchical_ocr_detached(
                        task_id=101,
                        filename="sample.pdf",
                        mode="layout",
                        batch_id="batch-hitl",
                        event_callback=event_callback,
                        workflow_thread_id="thread-hitl-001",
                        resume_payload={
                            "fields": {"题名": "测试材料-人工核定"},
                            "notes": "已人工确认第二页金额。",
                            "reviewed_by": "tester",
                        },
                    )
                )

        self.assertNotEqual("INTERRUPTED", resumed.get("status"))
        self.assertEqual("thread-hitl-001", resumed["workflow_thread_id"])
        self.assertEqual(3, resumed["page_count"])
        self.assertEqual("approved", resumed["review_status"])
        self.assertTrue(any(item["event_type"] == "PAGE_COMPLETED" for item in callback_events))


if __name__ == "__main__":
    unittest.main()
