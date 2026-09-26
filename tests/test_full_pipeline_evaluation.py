import unittest

from src.evals.application_evals.metrics import METRIC_NAMES, build_full_pipeline_metrics
from src.evals.application_evals.reporting import calculate_averages
from src.evals.application_evals.evaluate_full_pipeline import (
    empty_answer_metric,
    validate_goldens,
)


class FullPipelineEvaluationTests(unittest.TestCase):
    def test_metric_suite_contains_standard_and_custom_metrics(self) -> None:
        metrics = build_full_pipeline_metrics("gpt-5-mini-2025-08-07")
        self.assertEqual([metric.__name__ for metric in metrics], METRIC_NAMES)

    def test_validate_goldens_requires_expected_context(self) -> None:
        with self.assertRaisesRegex(ValueError, "expected_context"):
            validate_goldens([{"question": "Q", "expected_answer": "A"}])

    def test_calculate_averages_uses_every_metric(self) -> None:
        case = {
            "metrics": {
                name: {"score": 0.75, "success": True} for name in METRIC_NAMES
            }
        }
        self.assertEqual(
            calculate_averages([case]), {name: 0.75 for name in METRIC_NAMES}
        )

    def test_empty_answer_is_an_explicit_failed_metric(self) -> None:
        result = empty_answer_metric("Answer Correctness")
        self.assertEqual(result["score"], 0.0)
        self.assertFalse(result["success"])
        self.assertEqual(result["error"], "empty_actual_output")


if __name__ == "__main__":
    unittest.main()
