import unittest

from app.services import agent_ocr_workflow as workflow


def _page(page_num: int, confidence: float = 0.9):
    return {
        "page_num": page_num,
        "regions": [],
        "lines": [
            {
                "line_num": 1,
                "text": f"第 {page_num} 页测试文本",
                "confidence": confidence,
                "bbox": [],
                "bbox_type": "rect",
            }
        ],
        "agent_meta": {
            "confidence": confidence,
            "issues": [],
            "source": "ocr",
            "retry_count": 0,
            "processing_strategy": "none",
        },
    }


class AgentOCRWorkflowTests(unittest.IsolatedAsyncioTestCase):
    def test_parse_json_object_extracts_first_json_from_mixed_text(self):
        payload = """以下是结果：
```json
{"fields":{"题名":"测试材料"},"confidence":0.91,"issues":[]}
```
补充说明：字段已标准化。"""

        parsed = workflow._parse_json_object(payload)

        self.assertEqual("测试材料", parsed["fields"]["题名"])
        self.assertEqual(0.91, parsed["confidence"])

    def test_parse_json_object_handles_multiple_json_objects(self):
        payload = """{"fields":{"题名":"第一页"},"confidence":0.82}
{"fields":{"题名":"第二页"},"confidence":0.66}"""

        parsed = workflow._parse_json_object(payload)

        self.assertEqual("第一页", parsed["fields"]["题名"])
        self.assertEqual(0.82, parsed["confidence"])

    def test_merge_page_field_candidates_prefers_consensus_and_sets_page_count(self):
        merged = workflow._merge_page_field_candidates(
            [
                {
                    "page_num": 1,
                    "fields": {"题名": "关于档案整理工作的通知", "文号": "国档〔2026〕1号", "备注": "首页"},
                    "confidence": 0.92,
                },
                {
                    "page_num": 2,
                    "fields": {"题名": "关于档案整理工作的通知", "文号": "国档〔2026〕1号", "备注": "续页"},
                    "confidence": 0.88,
                },
                {
                    "page_num": 3,
                    "fields": {"题名": "关于档案整理工作的通知（扫描件）", "文号": "国档〔2026〕2号"},
                    "confidence": 0.4,
                },
            ]
        )

        self.assertEqual(merged["题名"], "关于档案整理工作的通知")
        self.assertEqual(merged["文号"], "国档〔2026〕1号")
        self.assertEqual(merged["页数"], "3")
        self.assertIn("首页", merged["备注"])

    async def test_route_after_page_merge_requests_retry_below_threshold(self):
        route = await workflow.route_after_page_merge(
            {
                "final_result": {"confidence": workflow.CONFIDENCE_THRESHOLD - 0.1},
                "retry_count": 0,
                "max_retries": 2,
            }
        )
        self.assertEqual(route, "node_adjust_strategy")

    async def test_node_human_router_marks_conflicts_for_review(self):
        result = await workflow.node_human_router(
            {
                "overall_confidence": 0.72,
                "issues": [],
                "merged_fields": {
                    "档号": "DA-001",
                    "文号": "国档〔2026〕1号",
                    "责任者": "档案局",
                    "题名": "测试文件",
                    "日期": "2026-01-01",
                    "页数": "2",
                    "密级": "",
                    "备注": "",
                },
                "consistency": {
                    "status": "conflict",
                    "conflicts": {
                        "文号": [
                            {"value": "国档〔2026〕1号", "pages": [{"page_num": 1, "confidence": 0.8}]},
                            {"value": "国档〔2026〕2号", "pages": [{"page_num": 2, "confidence": 0.7}]},
                        ]
                    },
                },
                "page_outputs": [
                    {
                        "page_num": 1,
                        "page": _page(1, 0.8),
                        "fields": {"文号": "国档〔2026〕1号"},
                        "confidence": 0.8,
                        "issues": [],
                    },
                    {
                        "page_num": 2,
                        "page": _page(2, 0.7),
                        "fields": {"文号": "国档〔2026〕2号"},
                        "confidence": 0.7,
                        "issues": [],
                    },
                ],
            }
        )

        self.assertTrue(result["human_review"])
        self.assertEqual(result["review_status"], "pending_human_review")
        self.assertIn("跨页关键字段冲突", result["review_reason"])
        self.assertTrue(result["page_outputs"][0]["page"]["agent_meta"]["human_review"])

    async def test_node_final_archiver_attaches_batch_summary_without_db(self):
        result = await workflow.node_final_archiver_and_quality(
            {
                "task_id": 1,
                "batch_id": "batch-001",
                "batch_folder": "D:/OCR/uploads",
                "merged_fields": {
                    "档号": "DA-001",
                    "文号": "国档〔2026〕1号",
                    "责任者": "档案局",
                    "题名": "测试文件",
                    "日期": "2026-01-01",
                    "页数": "2",
                    "密级": "公开",
                    "备注": "",
                },
                "combined_pages": [_page(1, 0.91), _page(2, 0.89)],
                "page_outputs": [
                    {"page_num": 1, "confidence": 0.91, "retry_count": 0, "issues": []},
                    {"page_num": 2, "confidence": 0.89, "retry_count": 1, "issues": ["重试后通过"]},
                ],
                "overall_confidence": 0.9,
                "issues": ["重试后通过"],
                "human_review": True,
                "review_status": "pending_human_review",
                "review_reason": "等待人工确认",
                "consistency": {"status": "ok", "conflicts": {}},
                "rag_examples": [{"archive_no": "HIS-001", "score": 0.93}],
                "db": None,
            }
        )

        self.assertFalse(result["archive_saved"])
        summary = result["combined_pages"][0]["agent_meta"]["batch_summary"]
        self.assertTrue(summary["human_review"])
        self.assertEqual(summary["quality_metrics"]["pages_with_retry"], 1)
        self.assertEqual(result["workflow_result"]["final_fields"]["档号"], "DA-001")


if __name__ == "__main__":
    unittest.main()
