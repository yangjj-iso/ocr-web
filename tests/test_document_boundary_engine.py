import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image, ImageDraw

from app.services.document_boundary_engine import (
    BoundaryFeedbackPriors,
    BoundaryFeedbackStats,
    SequencePage,
    build_boundary_result,
)


class DocumentBoundaryEngineTests(unittest.TestCase):
    def _make_image(self, path: Path, *, variant: str) -> None:
        image = Image.new("RGB", (800, 1200), "white")
        draw = ImageDraw.Draw(image)
        if variant == "same":
            draw.rectangle((80, 100, 720, 220), outline="black", width=8)
            draw.text((120, 320), "连续文档", fill="black")
            draw.text((120, 400), "甲方：测试单位", fill="black")
        elif variant == "different":
            draw.rectangle((100, 760, 700, 1100), fill="black")
            draw.text((140, 120), "附件页", fill="black")
        else:
            raise ValueError(f"Unknown variant: {variant}")
        image.save(path)

    def _make_page(self, *, task_id: int, path: Path, text: str, family: str = "") -> SequencePage:
        return SequencePage(
            task_id=task_id,
            filename=path.name,
            file_path=str(path),
            prefix="KJ-JJ-2017-02-001",
            page_no=int(path.stem.rsplit("-", 1)[-1]),
            created_at=datetime.now(timezone.utc),
            title_hint=text[:80],
            full_text=text,
            title_norm=text[:80],
            document_family=family,
        )

    def test_boundary_engine_merges_budget_sequence_even_with_visual_changes(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            page2 = Path(temp_dir) / "KJ-JJ-2017-02-001-002.jpg"
            page3 = Path(temp_dir) / "KJ-JJ-2017-02-001-003.jpg"
            page4 = Path(temp_dir) / "KJ-JJ-2017-02-001-004.jpg"
            self._make_image(page2, variant="same")
            self._make_image(page3, variant="different")
            self._make_image(page4, variant="different")

            result = build_boundary_result(
                [
                    self._make_page(task_id=2, path=page2, text="建筑装饰工程造价预算书", family="budget"),
                    self._make_page(task_id=3, path=page3, text="预算汇总表 建设单位 法人签字", family="budget"),
                    self._make_page(task_id=4, path=page4, text="装修工程预算表 第1页 共1页", family="budget"),
                ]
            )

            self.assertEqual(len(result.groups), 1)
            self.assertEqual(result.groups[0].task_ids, [2, 3, 4])

    def test_boundary_engine_splits_attachment_after_contract_tail(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            page27 = Path(temp_dir) / "KJ-JJ-2017-02-001-027.jpg"
            page28 = Path(temp_dir) / "KJ-JJ-2017-02-001-028.jpg"
            page29 = Path(temp_dir) / "KJ-JJ-2017-02-001-029.jpg"
            page30 = Path(temp_dir) / "KJ-JJ-2017-02-001-030.jpg"
            page31 = Path(temp_dir) / "KJ-JJ-2017-02-001-031.jpg"
            self._make_image(page27, variant="same")
            self._make_image(page28, variant="different")
            self._make_image(page29, variant="different")
            self._make_image(page30, variant="same")
            self._make_image(page31, variant="different")

            result = build_boundary_result(
                [
                    self._make_page(
                        task_id=27,
                        path=page27,
                        text=(
                            "重庆大剧院污染新风源垃圾房改造合同\n"
                            "甲方：重庆文化产业投资集团有限公司\n"
                            "乙方：重庆上水环境设计工程有限公司\n"
                            "本合同付款方式如下。"
                        ),
                        family="contract",
                    ),
                    self._make_page(
                        task_id=28,
                        path=page28,
                        text=(
                            "验收合格后支付工程款。\n"
                            "剩余质保金在质保期满后支付。\n"
                            "甲方通过银行转账方式向乙方支付，开户行如下。"
                        ),
                        family="contract",
                    ),
                    self._make_page(
                        task_id=29,
                        path=page29,
                        text=(
                            "第五条 双方责任及义务。\n"
                            "甲方负责按合同约定支付工程款。\n"
                            "乙方负责按双方约定完成施工。"
                        ),
                        family="contract",
                    ),
                    self._make_page(
                        task_id=30,
                        path=page30,
                        text=(
                            "第八条 本合同及附件一式四份，均具有同等法律效力。\n"
                            "本合同经甲、乙双方签字盖章后生效。\n"
                            "合同附件：《重庆大剧院污染新风源垃圾房改造实施要求》。"
                        ),
                        family="contract",
                    ),
                    self._make_page(
                        task_id=31,
                        path=page31,
                        text="附件：重庆大剧院污染新风源垃圾房改造实施要求",
                        family="instruction",
                    ),
                ]
            )

            self.assertEqual([group.task_ids for group in result.groups], [[27, 28, 29, 30], [31]])

    def test_boundary_engine_merges_minutes_sequence(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            page1 = Path(temp_dir) / "WS·2024·D30-0156-001.jpg"
            page2 = Path(temp_dir) / "WS·2024·D30-0156-002.jpg"
            page3 = Path(temp_dir) / "WS·2024·D30-0156-003.jpg"
            self._make_image(page1, variant="same")
            self._make_image(page2, variant="different")
            self._make_image(page3, variant="different")

            result = build_boundary_result(
                [
                    self._make_page(
                        task_id=1,
                        path=page1,
                        text=(
                            "2024年第13期 重庆两江新区文化传媒集团有限公司2024年5月安全生产工作会议纪要\n"
                            "2024年5月24日召开安全生产工作会议，纪要如下。"
                        ),
                        family="minutes",
                    ),
                    self._make_page(
                        task_id=2,
                        path=page2,
                        text=(
                            "会议传达学习了近期安全防范工作的紧急通知，进一步研究部署集团近期安全生产重点工作。\n"
                            "会议强调，要抓实抓细当前防汛抗旱各项工作。"
                        ),
                        family="minutes",
                    ),
                    self._make_page(
                        task_id=3,
                        path=page3,
                        text=(
                            "会议要求，一要瞄准重点环节，推动安全生产各项要求落实落细。\n"
                            "出席：罗杰、刘迪。请假：梁艳。"
                        ),
                        family="minutes",
                    ),
                ]
            )

            self.assertEqual(len(result.groups), 1)
            self.assertEqual(result.groups[0].task_ids, [1, 2, 3])

    def test_boundary_engine_uses_feedback_priors_to_stabilize_ambiguous_contract_jump_pages(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            page1 = Path(temp_dir) / "KJ-JJ-2017-02-001-040.jpg"
            page2 = Path(temp_dir) / "KJ-JJ-2017-02-001-042.jpg"
            self._make_image(page1, variant="same")
            self._make_image(page2, variant="different")

            pages = [
                SequencePage(
                    task_id=40,
                    filename=page1.name,
                    file_path=str(page1),
                    prefix="KJ-JJ-2017-02-001",
                    page_no=40,
                    created_at=datetime.now(timezone.utc),
                    title_hint="重庆大剧院污染新风源垃圾房改造合同",
                    full_text=(
                        "重庆大剧院污染新风源垃圾房改造合同\n"
                        "甲方：重庆文化产业投资集团有限公司\n"
                        "乙方：重庆上水环境设计工程有限公司\n"
                        "付款安排如下。"
                    ),
                    title_norm="重庆大剧院污染新风源垃圾房改造合同",
                    document_family="contract",
                    doc_no_norm="kjjj2024001",
                    responsible_norm="重庆文化产业投资集团有限公司",
                ),
                SequencePage(
                    task_id=42,
                    filename=page2.name,
                    file_path=str(page2),
                    prefix="KJ-JJ-2017-02-001",
                    page_no=42,
                    created_at=datetime.now(timezone.utc),
                    title_hint="重庆大剧院污染新风源垃圾房改造合同",
                    full_text=(
                        "重庆大剧院污染新风源垃圾房改造合同\n"
                        "甲方：重庆文化产业投资集团有限公司\n"
                        "乙方：重庆上水环境设计工程有限公司\n"
                        "双方违约责任如下。"
                    ),
                    title_norm="重庆大剧院污染新风源垃圾房改造合同",
                    document_family="contract",
                    doc_no_norm="kjjj2024001",
                    responsible_norm="重庆文化产业投资集团有限公司",
                ),
            ]

            baseline = build_boundary_result(pages)
            baseline_score = baseline.adjacent_decisions[0].same_document_score

            priors = BoundaryFeedbackPriors(
                family_page_gap={("contract", 2): BoundaryFeedbackStats(same_count=5, different_count=0)},
                page_gap={2: BoundaryFeedbackStats(same_count=8, different_count=1)},
            )
            learned = build_boundary_result(pages, feedback_priors=priors)
            learned_score = learned.adjacent_decisions[0].same_document_score

            self.assertGreater(learned_score, baseline_score)
            self.assertGreater(learned.adjacent_decisions[0].signals.get("feedback_bias", 0.0), 0.0)
            self.assertLessEqual(len(learned.groups), len(baseline.groups))

    def test_boundary_engine_exposes_applied_similarity_threshold(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            page1 = Path(temp_dir) / "KJ-JJ-2017-02-001-001.jpg"
            page2 = Path(temp_dir) / "KJ-JJ-2017-02-001-002.jpg"
            self._make_image(page1, variant="same")
            self._make_image(page2, variant="same")

            result = build_boundary_result(
                [
                    self._make_page(task_id=1, path=page1, text="连续文档第一页", family="contract"),
                    self._make_page(task_id=2, path=page2, text="连续文档第二页", family="contract"),
                ],
                similarity_threshold=9,
            )

            self.assertEqual(
                result.sequence_meta["KJ-JJ-2017-02-001"]["applied_similarity_threshold"],
                9,
            )
            self.assertEqual(result.group_meta[result.groups[0].group_id]["suggested_pdf_filename"], "KJ-JJ-2017-02-001-001-002.pdf")


if __name__ == "__main__":
    unittest.main()
