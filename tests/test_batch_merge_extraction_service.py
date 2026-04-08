import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image, ImageDraw

from app.db.models import OCRTask
from app.services import batch_merge_extraction_service as merge_service


class BatchMergeExtractionServiceTests(unittest.TestCase):
    def _make_task(self, *, task_id: int, filename: str, file_path: Path, full_text: str = "") -> OCRTask:
        task = OCRTask(
            id=task_id,
            filename=filename,
            file_path=str(file_path),
            file_type=file_path.suffix.lower(),
            mode="vl",
            status="done",
            full_text=full_text,
            page_count=1,
        )
        task.created_at = datetime.now(timezone.utc)
        return task

    def _make_image(self, path: Path, *, variant: str) -> None:
        image = Image.new("RGB", (800, 1200), "white")
        draw = ImageDraw.Draw(image)
        if variant == "same":
            draw.rectangle((80, 100, 720, 220), outline="black", width=8)
            draw.text((120, 320), "合同续页", fill="black")
            draw.text((120, 400), "甲方：测试单位", fill="black")
        elif variant == "different":
            draw.rectangle((100, 760, 700, 1100), fill="black")
            draw.text((140, 120), "营业执照", fill="black")
        else:
            raise ValueError(f"Unknown variant: {variant}")
        image.save(path)

    def test_visual_sequence_candidate_is_merge_eligible_even_without_text(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            image_path = Path(temp_dir) / "KJ-JJ-2017-02-001-000.jpg"
            self._make_image(image_path, variant="same")
            task = self._make_task(task_id=1, filename=image_path.name, file_path=image_path, full_text="")

            self.assertTrue(merge_service._is_visual_sequence_candidate(task))
            self.assertTrue(merge_service._task_is_merge_eligible(task))

    def test_visual_group_hints_merge_only_continuous_pages(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            page0 = Path(temp_dir) / "KJ-JJ-2017-02-001-000.jpg"
            page1 = Path(temp_dir) / "KJ-JJ-2017-02-001-001.jpg"
            page2 = Path(temp_dir) / "KJ-JJ-2017-02-001-002.jpg"
            self._make_image(page0, variant="same")
            self._make_image(page1, variant="same")
            self._make_image(page2, variant="different")

            candidates = [
                merge_service._build_task_candidate(
                    self._make_task(task_id=1, filename=page0.name, file_path=page0, full_text="")
                ),
                merge_service._build_task_candidate(
                    self._make_task(task_id=2, filename=page1.name, file_path=page1, full_text="")
                ),
                merge_service._build_task_candidate(
                    self._make_task(task_id=3, filename=page2.name, file_path=page2, full_text="")
                ),
            ]

            visual_group_by_task_id, visual_group_meta = merge_service._build_visual_group_hints(candidates)

            self.assertEqual(visual_group_by_task_id[1], visual_group_by_task_id[2])
            self.assertNotEqual(visual_group_by_task_id[1], visual_group_by_task_id[3])
            self.assertIn("视觉分页判定", visual_group_meta[visual_group_by_task_id[1]]["reason"])

    def test_rule_decision_respects_visual_group_boundaries(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            page0 = Path(temp_dir) / "KJ-JJ-2017-02-001-000.jpg"
            page1 = Path(temp_dir) / "KJ-JJ-2017-02-001-001.jpg"
            page2 = Path(temp_dir) / "KJ-JJ-2017-02-001-002.jpg"
            self._make_image(page0, variant="same")
            self._make_image(page1, variant="same")
            self._make_image(page2, variant="different")

            candidate0 = merge_service._build_task_candidate(
                self._make_task(task_id=1, filename=page0.name, file_path=page0, full_text="")
            )
            candidate1 = merge_service._build_task_candidate(
                self._make_task(task_id=2, filename=page1.name, file_path=page1, full_text="")
            )
            candidate2 = merge_service._build_task_candidate(
                self._make_task(task_id=3, filename=page2.name, file_path=page2, full_text="")
            )

            visual_group_by_task_id, visual_group_meta = merge_service._build_visual_group_hints(
                [candidate0, candidate1, candidate2]
            )

            merge, confidence, reason = merge_service._rule_decision(
                candidate0,
                candidate1,
                visual_group_by_task_id=visual_group_by_task_id,
                visual_group_meta=visual_group_meta,
            )
            self.assertTrue(merge)
            self.assertGreaterEqual(confidence, 0.9)
            self.assertIn("视觉", reason)

            merge, confidence, reason = merge_service._rule_decision(
                candidate1,
                candidate2,
                visual_group_by_task_id=visual_group_by_task_id,
                visual_group_meta=visual_group_meta,
            )
            self.assertFalse(merge)
            self.assertEqual(confidence, 0.0)
            self.assertIn("切换到下一份原始文件", reason)

    def test_same_document_acceptance_threshold_is_lower_for_adjacent_visual_pages(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            page0 = Path(temp_dir) / "KJ-JJ-2017-02-001-000.jpg"
            page1 = Path(temp_dir) / "KJ-JJ-2017-02-001-001.jpg"
            other = Path(temp_dir) / "demo-other.jpg"
            self._make_image(page0, variant="same")
            self._make_image(page1, variant="same")
            self._make_image(other, variant="different")

            candidate0 = merge_service._build_task_candidate(
                self._make_task(task_id=1, filename=page0.name, file_path=page0, full_text="")
            )
            candidate1 = merge_service._build_task_candidate(
                self._make_task(task_id=2, filename=page1.name, file_path=page1, full_text="")
            )
            candidate_other = merge_service._build_task_candidate(
                self._make_task(task_id=3, filename=other.name, file_path=other, full_text="其他材料")
            )

            self.assertEqual(
                merge_service._same_document_acceptance_threshold(
                    candidate0,
                    candidate1,
                    left_index=0,
                    right_index=1,
                ),
                merge_service.ADJACENT_PAGE_SAME_DOCUMENT_CONFIDENCE_THRESHOLD,
            )
            self.assertEqual(
                merge_service._same_document_acceptance_threshold(
                    candidate0,
                    candidate_other,
                    left_index=0,
                    right_index=2,
                ),
                merge_service.SAME_DOCUMENT_CONFIDENCE_THRESHOLD,
            )

    def test_budget_pages_can_override_visual_split_boundary(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            page1 = Path(temp_dir) / "KJ-JJ-2017-02-001-001.jpg"
            page2 = Path(temp_dir) / "KJ-JJ-2017-02-001-002.jpg"
            page3 = Path(temp_dir) / "KJ-JJ-2017-02-001-003.jpg"
            self._make_image(page1, variant="same")
            self._make_image(page2, variant="different")
            self._make_image(page3, variant="different")

            candidate1 = merge_service._build_task_candidate(
                self._make_task(task_id=1, filename=page1.name, file_path=page1, full_text="建筑装饰工程造价预算书")
            )
            candidate2 = merge_service._build_task_candidate(
                self._make_task(task_id=2, filename=page2.name, file_path=page2, full_text="预算汇总表")
            )
            candidate3 = merge_service._build_task_candidate(
                self._make_task(task_id=3, filename=page3.name, file_path=page3, full_text="装修工程预算表")
            )
            visual_group_by_task_id = {1: "visual-1", 2: "visual-2", 3: "visual-3"}
            visual_group_meta = {}

            merge, confidence, reason = merge_service._rule_decision(
                candidate1,
                candidate2,
                visual_group_by_task_id=visual_group_by_task_id,
                visual_group_meta=visual_group_meta,
            )
            self.assertTrue(merge)
            self.assertGreaterEqual(confidence, 0.86)
            self.assertIn("预算类材料", reason)

    def test_contract_pages_can_override_visual_split_boundary(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            page27 = Path(temp_dir) / "KJ-JJ-2017-02-001-027.jpg"
            page28 = Path(temp_dir) / "KJ-JJ-2017-02-001-028.jpg"
            self._make_image(page27, variant="same")
            self._make_image(page28, variant="different")

            candidate27 = merge_service._build_task_candidate(
                self._make_task(
                    task_id=27,
                    filename=page27.name,
                    file_path=page27,
                    full_text=(
                        "重庆大剧院污染新风源垃圾房改造合同\n"
                        "甲方：重庆文化产业投资集团有限公司\n"
                        "乙方：重庆上水环境设计工程有限公司\n"
                        "本合同付款方式如下。"
                    ),
                )
            )
            candidate28 = merge_service._build_task_candidate(
                self._make_task(
                    task_id=28,
                    filename=page28.name,
                    file_path=page28,
                    full_text=(
                        "验收合格后支付工程款。\n"
                        "剩余质保金在质保期满后支付。\n"
                        "甲方通过银行转账方式向乙方支付，开户行如下。"
                    ),
                )
            )

            visual_group_by_task_id = {27: "visual-27", 28: "visual-28"}
            visual_group_meta = {}

            merge, confidence, reason = merge_service._rule_decision(
                candidate27,
                candidate28,
                visual_group_by_task_id=visual_group_by_task_id,
                visual_group_meta=visual_group_meta,
            )
            self.assertTrue(merge)
            self.assertGreaterEqual(confidence, 0.86)
            self.assertIn("合同类材料", reason)

    def test_skip_non_adjacent_visual_pair_when_intermediate_page_exists(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            page1 = Path(temp_dir) / "WS·2024·D30-0156-001.jpg"
            page2 = Path(temp_dir) / "WS·2024·D30-0156-002.jpg"
            page3 = Path(temp_dir) / "WS·2024·D30-0156-003.jpg"
            self._make_image(page1, variant="same")
            self._make_image(page2, variant="different")
            self._make_image(page3, variant="different")

            candidate1 = merge_service._build_task_candidate(
                self._make_task(
                    task_id=1,
                    filename=page1.name,
                    file_path=page1,
                    full_text="2024年5月安全生产工作会议纪要",
                )
            )
            candidate2 = merge_service._build_task_candidate(
                self._make_task(
                    task_id=2,
                    filename=page2.name,
                    file_path=page2,
                    full_text="会议传达学习了近期安全防范工作通知，会议强调安全责任落实。",
                )
            )
            candidate3 = merge_service._build_task_candidate(
                self._make_task(
                    task_id=3,
                    filename=page3.name,
                    file_path=page3,
                    full_text="会议要求抓实抓细安全生产工作。出席：罗杰、刘迪。",
                )
            )

            self.assertTrue(
                merge_service._has_intermediate_visual_candidate(
                    candidate1,
                    candidate3,
                    [candidate1, candidate2, candidate3],
                )
            )
            self.assertFalse(
                merge_service._has_intermediate_visual_candidate(
                    candidate1,
                    candidate2,
                    [candidate1, candidate2, candidate3],
                )
            )

    def test_truth_mapping_overrides_auto_groups(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            page1 = Path(temp_dir) / "WS·2024·D30-0156-001.jpg"
            page2 = Path(temp_dir) / "WS·2024·D30-0156-002.jpg"
            page3 = Path(temp_dir) / "WS·2024·D30-0156-003.jpg"
            self._make_image(page1, variant="same")
            self._make_image(page2, variant="different")
            self._make_image(page3, variant="different")

            candidates = [
                merge_service._build_task_candidate(
                    self._make_task(task_id=1, filename=page1.name, file_path=page1, full_text="会议纪要首页")
                ),
                merge_service._build_task_candidate(
                    self._make_task(task_id=2, filename=page2.name, file_path=page2, full_text="会议传达学习有关通知")
                ),
                merge_service._build_task_candidate(
                    self._make_task(task_id=3, filename=page3.name, file_path=page3, full_text="会议要求压实工作责任")
                ),
            ]

            union_find = merge_service._UnionFind(len(candidates))
            group_specs = merge_service._build_group_specs(
                candidates=candidates,
                union_find=union_find,
                truth_task_to_doc_key={1: "doc-1", 2: "doc-1", 3: "doc-1"},
            )

            self.assertEqual(len(group_specs), 1)
            self.assertEqual([member.task.id for member in group_specs[0][0]], [1, 2, 3])
            self.assertEqual(group_specs[0][1], "doc-1")


if __name__ == "__main__":
    unittest.main()
