import unittest

from app.services.document_boundary_feedback_learning import (
    BoundaryFeedbackSample,
    build_boundary_feedback_priors,
)


class DocumentBoundaryFeedbackLearningTests(unittest.TestCase):
    def test_build_boundary_feedback_priors_accumulates_family_and_gap_stats(self):
        priors = build_boundary_feedback_priors(
            [
                BoundaryFeedbackSample(label="same", page_gap=1, left_family="contract", right_family="contract"),
                BoundaryFeedbackSample(label="same", page_gap=1, left_family="contract", right_family="contract"),
                BoundaryFeedbackSample(label="different", page_gap=1, left_family="contract", right_family="instruction"),
                BoundaryFeedbackSample(label="same", page_gap=2, left_family="minutes", right_family="minutes"),
            ]
        )

        contract_stats = priors.family_page_gap[("contract", 1)]
        self.assertEqual(contract_stats.same_count, 2)
        self.assertEqual(contract_stats.different_count, 0)

        transition_stats = priors.family_transition_gap[("contract", "instruction", 1)]
        self.assertEqual(transition_stats.same_count, 0)
        self.assertEqual(transition_stats.different_count, 1)

        gap_stats = priors.page_gap[1]
        self.assertEqual(gap_stats.same_count, 2)
        self.assertEqual(gap_stats.different_count, 1)


if __name__ == "__main__":
    unittest.main()
