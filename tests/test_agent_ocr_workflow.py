import unittest
import uuid
from unittest.mock import patch

from app.services import agent_ocr_workflow as workflow
from app.services import excel_export


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
    def test_build_workflow_thread_id_returns_uuid_string(self):
        thread_id = workflow._build_workflow_thread_id(168, "batch_foo")

        self.assertEqual(thread_id, str(uuid.UUID(thread_id)))

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

    async def test_node_page_plan_enables_ppocr_vl_for_complex_pages(self):
        with patch.object(workflow, "_estimate_page_complexity", return_value=0.9), patch.object(
            workflow,
            "uses_shared_layout_api_for_ocr_and_vl",
            return_value=False,
        ):
            result = await workflow.node_page_plan(
                {
                    "image_path": "unused.jpg",
                    "mode": "layout",
                    "retry_count": 0,
                }
            )

        self.assertTrue(result["should_use_vision"])
        self.assertEqual(result["secondary_mode"], "ppocr_vl")
        self.assertIn("PaddleOCR-VL-1.5", result["route_reason"])
        self.assertEqual(result["processing_strategy"], "opencv_document")
        self.assertIn("OpenCV", result["preprocess_reason"])

    async def test_node_page_plan_skips_redundant_secondary_api_pass(self):
        with patch.object(workflow, "_estimate_page_complexity", return_value=0.9), patch.object(
            workflow,
            "uses_shared_layout_api_for_ocr_and_vl",
            return_value=True,
        ):
            result = await workflow.node_page_plan(
                {
                    "image_path": "unused.jpg",
                    "mode": "layout",
                    "retry_count": 0,
                }
            )

        self.assertFalse(result["should_use_vision"])
        self.assertEqual(result["secondary_mode"], "skip")
        self.assertIn("复用同一远端 layout-parsing 接口", result["route_reason"])

    async def test_node_page_plan_preserves_existing_processing_strategy(self):
        with patch.object(workflow, "_estimate_page_complexity", return_value=0.9):
            result = await workflow.node_page_plan(
                {
                    "image_path": "unused.jpg",
                    "mode": "layout",
                    "retry_count": 0,
                    "processing_strategy": "crop_and_zoom",
                }
            )

        self.assertEqual(result["processing_strategy"], "crop_and_zoom")
        self.assertIn("裁边放大", result["preprocess_reason"])

    async def test_route_after_ocr_uses_llm_branch_when_llm_mode_enabled(self):
        route = await workflow.route_after_ocr({"secondary_mode": "ppocr_vl"})
        self.assertEqual(route, "node_ppocr_vl")

    async def test_route_after_ocr_skips_secondary_branch_when_disabled(self):
        route = await workflow.route_after_ocr({"secondary_mode": "skip"})
        self.assertEqual(route, "node_evaluate_and_merge")

    async def test_node_adjust_strategy_starts_with_opencv_document(self):
        result = await workflow.node_adjust_strategy(
            {
                "task_id": 1,
                "page_num": 1,
                "retry_count": 0,
                "processing_strategy": "none",
            }
        )

        self.assertEqual(result["retry_count"], 1)
        self.assertEqual(result["processing_strategy"], "opencv_document")

    async def test_node_ppocr_vl_uses_vl_engine(self):
        fake_page = {
            "page_num": 1,
            "regions": [{"type": "text", "content": "卷内目录"}],
            "lines": [{"line_num": 1, "text": "卷内目录", "confidence": 0.93, "bbox": [], "bbox_type": "rect"}],
        }

        class _FakeEngine:
            def recognize_page(self, image_path):
                return fake_page

        with patch.object(workflow, "get_ocr_engine", return_value=_FakeEngine()) as engine_mock, patch.object(
            workflow.field_service,
            "extract_fields",
            return_value={"题名": "卷内目录", "档号": "KJ-JJ-2017-02-001-000", "文号": "", "责任者": "", "日期": "", "页数": "1", "密级": "", "备注": ""},
        ):
            result = await workflow.node_ppocr_vl(
                {
                    "filename": "KJ-JJ-2017-02-001-000.jpg",
                    "page_num": 1,
                    "image_path": "D:/tmp/demo.jpg",
                    "processing_strategy": "opencv_document",
                }
            )

        engine_mock.assert_called_once_with(strategy="opencv_document", mode="vl")
        self.assertEqual(result["vl_result"]["fields"]["题名"], "卷内目录")
        self.assertEqual(result["vl_result"]["fields"]["档号"], "KJ-JJ-2017-02-001-000")
        self.assertEqual(result["vl_result"]["confidence"], 0.93)

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

    async def test_node_human_router_ignores_non_blocking_vision_warning(self):
        fields = {
            "档号": "DA-001",
            "文号": "国档〔2026〕1号",
            "责任者": "档案局",
            "题名": "测试文件",
            "日期": "2026-01-01",
            "页数": "1",
            "密级": "",
            "备注": "",
        }
        result = await workflow.node_human_router(
            {
                "overall_confidence": 0.95,
                "issues": ["Vision LLM unavailable"],
                "merged_fields": fields,
                "consistency": {"status": "ok", "conflicts": {}},
                "page_outputs": [
                    {
                        "page_num": 1,
                        "page": _page(1, 0.95),
                        "fields": fields,
                        "confidence": 0.95,
                        "issues": ["Vision LLM unavailable"],
                    }
                ],
            }
        )

        self.assertFalse(result["human_review"])
        self.assertEqual(result["review_status"], "approved")
        self.assertEqual(result["review_reason"], "")
        self.assertFalse(result["page_outputs"][0]["page"]["agent_meta"]["human_review"])

    async def test_node_human_router_catalog_can_pass_without_support_fields(self):
        fields = {
            "档号": "KJ-JJ-2017-02-001",
            "文号": "",
            "责任者": "",
            "题名": "卷内目录",
            "日期": "",
            "页数": "1",
            "密级": "",
            "备注": "",
        }
        page = {
            "page_num": 1,
            "regions": [{"type": "text", "content": "卷内目录"}],
            "lines": [{"line_num": 1, "text": "卷内目录", "confidence": 0.95, "bbox": [], "bbox_type": "rect"}],
            "agent_meta": {},
        }
        result = await workflow.node_human_router(
            {
                "overall_confidence": 0.95,
                "issues": [],
                "merged_fields": fields,
                "combined_pages": [page],
                "consistency": {"status": "ok", "conflicts": {}},
                "page_outputs": [
                    {
                        "page_num": 1,
                        "page": page,
                        "fields": fields,
                        "confidence": 0.95,
                        "issues": [],
                    }
                ],
            }
        )

        self.assertFalse(result["human_review"])
        self.assertEqual(result["review_status"], "approved")

    async def test_node_human_router_non_catalog_can_pass_without_support_fields(self):
        fields = {
            "档号": "DA-001",
            "文号": "",
            "责任者": "",
            "题名": "会议纪要",
            "日期": "",
            "页数": "1",
            "密级": "",
            "备注": "",
        }
        page = {
            "page_num": 1,
            "regions": [{"type": "text", "content": "会议纪要"}],
            "lines": [
                {"line_num": 1, "text": "会议纪要", "confidence": 0.95, "bbox": [], "bbox_type": "rect"},
                {"line_num": 2, "text": "会议传达当前重点工作安排。", "confidence": 0.94, "bbox": [], "bbox_type": "rect"},
            ],
            "agent_meta": {},
        }
        result = await workflow.node_human_router(
            {
                "overall_confidence": 0.95,
                "issues": [],
                "merged_fields": fields,
                "combined_pages": [page],
                "consistency": {"status": "ok", "conflicts": {}},
                "page_outputs": [
                    {
                        "page_num": 1,
                        "page": page,
                        "fields": fields,
                        "confidence": 0.95,
                        "issues": [],
                    }
                ],
            }
        )

        self.assertFalse(result["human_review"])
        self.assertEqual(result["review_status"], "approved")
        self.assertEqual(result["review_reason"], "")

    async def test_node_human_router_ignores_support_field_absence_issue(self):
        fields = {
            "档号": "DA-001",
            "文号": "",
            "责任者": "",
            "题名": "会议纪要",
            "日期": "",
            "页数": "1",
            "密级": "",
            "备注": "",
        }
        issue = "核心辅助字段均缺失：文号、责任者、日期"
        page = {
            "page_num": 1,
            "regions": [{"type": "text", "content": "会议纪要"}],
            "lines": [
                {"line_num": 1, "text": "会议纪要", "confidence": 0.95, "bbox": [], "bbox_type": "rect"},
                {"line_num": 2, "text": "会议传达当前重点工作安排。", "confidence": 0.94, "bbox": [], "bbox_type": "rect"},
            ],
            "agent_meta": {},
        }
        result = await workflow.node_human_router(
            {
                "overall_confidence": 0.95,
                "issues": [issue],
                "merged_fields": fields,
                "combined_pages": [page],
                "consistency": {"status": "ok", "conflicts": {}},
                "page_outputs": [
                    {
                        "page_num": 1,
                        "page": page,
                        "fields": fields,
                        "confidence": 0.95,
                        "issues": [issue],
                    }
                ],
            }
        )

        self.assertFalse(result["human_review"])
        self.assertEqual(result["review_status"], "approved")
        self.assertEqual(result["review_reason"], "")
        self.assertFalse(result["page_outputs"][0]["human_review"])

    async def test_node_human_router_ignores_catalog_normalization_note(self):
        fields = {
            "档号": "KJ-JJ-2017-02-001-000",
            "文号": "",
            "责任者": "",
            "题名": "卷内目录",
            "日期": "",
            "页数": "1",
            "密级": "",
            "备注": "",
        }
        page = {
            "page_num": 1,
            "regions": [
                {"type": "text", "content": "卷内目录"},
                {"type": "text", "content": "档号 KJ·JJ·2017·02-001"},
            ],
            "lines": [
                {"line_num": 1, "text": "卷内目录", "confidence": 0.95, "bbox": [], "bbox_type": "rect"},
                {"line_num": 2, "text": "档号 KJ·JJ·2017·02-001", "confidence": 0.95, "bbox": [], "bbox_type": "rect"},
            ],
            "agent_meta": {},
        }
        issue = "题名应为'卷内目录'，原始OCR值包含档号信息，需规范化"
        result = await workflow.node_human_router(
            {
                "overall_confidence": 0.95,
                "issues": [issue],
                "merged_fields": fields,
                "combined_pages": [page],
                "consistency": {"status": "ok", "conflicts": {}},
                "page_outputs": [
                    {
                        "page_num": 1,
                        "page": page,
                        "fields": fields,
                        "confidence": 0.95,
                        "issues": [issue],
                        "review_reason": "本任务已按建议完成规范化，无需人工复核。",
                    }
                ],
            }
        )

        self.assertFalse(result["human_review"])
        self.assertEqual(result["review_status"], "approved")
        self.assertEqual(result["review_reason"], "")
        self.assertFalse(result["page_outputs"][0]["human_review"])

    async def test_node_human_router_marks_blurry_signature_for_review(self):
        fields = {
            "档号": "DA-001",
            "文号": "",
            "责任者": "",
            "题名": "情况说明",
            "日期": "",
            "页数": "1",
            "密级": "",
            "备注": "",
        }
        issue = "签名模糊，无法辨认。"
        page = {
            "page_num": 1,
            "regions": [{"type": "text", "content": "情况说明"}],
            "lines": [
                {"line_num": 1, "text": "情况说明", "confidence": 0.95, "bbox": [], "bbox_type": "rect"},
                {"line_num": 2, "text": "末页签名模糊。", "confidence": 0.91, "bbox": [], "bbox_type": "rect"},
            ],
            "agent_meta": {},
        }
        result = await workflow.node_human_router(
            {
                "overall_confidence": 0.95,
                "issues": [issue],
                "merged_fields": fields,
                "combined_pages": [page],
                "consistency": {"status": "ok", "conflicts": {}},
                "page_outputs": [
                    {
                        "page_num": 1,
                        "page": page,
                        "fields": fields,
                        "confidence": 0.95,
                        "issues": [issue],
                    }
                ],
            }
        )

        self.assertTrue(result["human_review"])
        self.assertEqual(result["review_status"], "pending_human_review")
        self.assertIn("签名模糊", result["review_reason"])
        self.assertTrue(result["page_outputs"][0]["human_review"])

    async def test_node_human_router_allows_missing_archive_and_title_when_page_is_legible(self):
        fields = {
            "档号": "",
            "文号": "",
            "责任者": "",
            "题名": "",
            "日期": "",
            "页数": "1",
            "密级": "",
            "备注": "",
        }
        page = {
            "page_num": 1,
            "regions": [{"type": "text", "content": "正文内容"}],
            "lines": [
                {"line_num": 1, "text": "正文内容", "confidence": 0.96, "bbox": [], "bbox_type": "rect"},
                {"line_num": 2, "text": "本页只有正文，没有题名或文号。", "confidence": 0.94, "bbox": [], "bbox_type": "rect"},
            ],
            "agent_meta": {},
        }
        result = await workflow.node_human_router(
            {
                "overall_confidence": 0.96,
                "issues": [],
                "merged_fields": fields,
                "combined_pages": [page],
                "consistency": {"status": "ok", "conflicts": {}},
                "page_outputs": [
                    {
                        "page_num": 1,
                        "page": page,
                        "fields": fields,
                        "confidence": 0.96,
                        "issues": [],
                    }
                ],
            }
        )

        self.assertFalse(result["human_review"])
        self.assertEqual(result["review_status"], "approved")
        self.assertEqual(result["review_reason"], "")
        self.assertFalse(result["page_outputs"][0]["human_review"])

    async def test_node_human_router_does_not_require_review_for_low_confidence_alone(self):
        fields = {
            "档号": "DA-001",
            "文号": "",
            "责任者": "",
            "题名": "普通正文",
            "日期": "",
            "页数": "1",
            "密级": "",
            "备注": "",
        }
        page = {
            "page_num": 1,
            "regions": [{"type": "text", "content": "普通正文"}],
            "lines": [
                {"line_num": 1, "text": "普通正文", "confidence": 0.52, "bbox": [], "bbox_type": "rect"},
                {"line_num": 2, "text": "字迹清楚，但模型信心偏保守。", "confidence": 0.5, "bbox": [], "bbox_type": "rect"},
            ],
            "agent_meta": {},
        }
        result = await workflow.node_human_router(
            {
                "overall_confidence": 0.52,
                "issues": [],
                "merged_fields": fields,
                "combined_pages": [page],
                "consistency": {"status": "ok", "conflicts": {}},
                "page_outputs": [
                    {
                        "page_num": 1,
                        "page": page,
                        "fields": fields,
                        "confidence": 0.52,
                        "issues": [],
                        "review_reason": "",
                    }
                ],
            }
        )

        self.assertFalse(result["human_review"])
        self.assertEqual(result["review_status"], "approved")
        self.assertEqual(result["review_reason"], "")
        self.assertFalse(result["page_outputs"][0]["human_review"])

    def test_excel_export_extracts_contract_responsible_and_title(self):
        page = {
            "page_num": 1,
            "regions": [
                {"type": "text", "content": "重庆大剧院污染新风源垃圾房改造合同"},
                {"type": "text", "content": "甲方：重庆文化产业投资集团有限公司 （以下简称“甲方”）"},
                {"type": "text", "content": "乙方：重庆上水环境设计工程有限公司 （以下简称“乙方”）"},
            ],
            "lines": [
                {"line_num": 1, "text": "重庆大剧院污染新风源垃圾房改造合同", "confidence": 0.95, "bbox": [], "bbox_type": "rect"},
                {"line_num": 2, "text": "甲方：重庆文化产业投资集团有限公司 （以下简称“甲方”）", "confidence": 0.95, "bbox": [], "bbox_type": "rect"},
                {"line_num": 3, "text": "乙方：重庆上水环境设计工程有限公司 （以下简称“乙方”）", "confidence": 0.95, "bbox": [], "bbox_type": "rect"},
            ],
        }

        fields = excel_export.extract_fields(
            "KJ-JJ-2017-02-001-027.jpg",
            "\n".join(line["text"] for line in page["lines"]),
            [page],
            1,
        )

        self.assertEqual(fields["题名"], "重庆大剧院污染新风源垃圾房改造合同")
        self.assertEqual(fields["责任者"], "重庆文化产业投资集团有限公司")

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
