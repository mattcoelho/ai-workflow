import os
import unittest
from unittest.mock import patch

from agent.evaluation import benchmark_examples, evaluate_examples, rescore_examples, snapshot_from_ledger


class EvaluationTests(unittest.TestCase):
    def test_snapshot_uses_uncalibrated_score(self):
        entry = {
            "feedback_id": "Example::123",
            "job_id": "123",
            "company": "Example",
            "title": "Staff Product Manager",
            "score": 9,
            "calibration": {"original_score": 6, "adjusted_score": 9},
        }

        snapshot = snapshot_from_ledger(entry)

        self.assertEqual(snapshot["score"], 6)
        self.assertEqual(snapshot["fit_tier"], "Watchlist")

    def test_benchmark_prefers_saved_snapshot(self):
        feedback = {
            "jobs": {
                "Example::123": {
                    "label": "strong_match",
                    "snapshot": {"score": 8, "title": "Saved title"},
                }
            }
        }
        ledger = {"Example::123": {"score": 2, "title": "New title"}}

        examples = benchmark_examples(feedback, ledger)

        self.assertEqual(examples[0]["snapshot"]["score"], 8)
        self.assertEqual(examples[0]["snapshot"]["title"], "Saved title")

    def test_metrics_report_precision_recall_and_range_accuracy(self):
        examples = [
            {"feedback_id": "A::1", "label": "strong_match", "snapshot": {"score": 8}},
            {"feedback_id": "B::2", "label": "bad_match", "snapshot": {"score": 8}},
            {"feedback_id": "C::3", "label": "maybe", "snapshot": {"score": 6}},
            {"feedback_id": "D::4", "label": "interviewed", "snapshot": {"score": 9}},
            {"feedback_id": "E::5", "label": "competitive_match", "snapshot": {"score": 7}},
        ]

        report = evaluate_examples(examples)

        self.assertEqual(report["examples"], 5)
        self.assertEqual(report["range_accuracy"], 0.8)
        self.assertEqual(report["bullseye_precision"], 1.0)
        self.assertEqual(report["competitive_precision"], 0.75)
        self.assertEqual(report["competitive_recall"], 1.0)

    def test_bad_url_is_excluded_from_fit_benchmark(self):
        feedback = {"jobs": {"Example::123": {"label": "bad_url", "snapshot": {"score": 9}}}}

        self.assertEqual(benchmark_examples(feedback, {}), [])

    def test_competitive_label_at_nine_counts_as_bullseye_false_positive(self):
        examples = [
            {"feedback_id": "A::1", "label": "competitive_match", "snapshot": {"score": 9}}
        ]

        report = evaluate_examples(examples)

        self.assertEqual(report["bullseye_precision"], 0.0)
        self.assertEqual(report["competitive_precision"], 1.0)
        self.assertEqual(report["competitive_recall"], 1.0)

    def test_candidate_report_preserves_reason_concerns_and_gates(self):
        examples = [
            {
                "feedback_id": "A::1",
                "label": "maybe",
                "snapshot": {"score": 8},
                "candidate": {
                    "score": 6,
                    "reason": "Program role.",
                    "concerns": ["No product ownership."],
                    "extraction": {
                        "role_type": "Program",
                        "gates": {
                            "owns_product_strategy": {
                                "value": False,
                                "evidence": "Coordinates delivery.",
                            }
                        },
                    },
                },
            }
        ]

        row = evaluate_examples(examples, prediction_key="candidate")["rows"][0]

        self.assertEqual(row["reason"], "Program role.")
        self.assertEqual(row["concerns"], ["No product ownership."])
        self.assertFalse(row["extraction"]["gates"]["owns_product_strategy"]["value"])

    def test_bullseye_label_requires_score_of_at_least_nine(self):
        examples = [
            {"feedback_id": "A::1", "label": "bullseye", "snapshot": {"score": 8}}
        ]

        report = evaluate_examples(examples)

        self.assertEqual(report["range_accuracy"], 0.0)
        self.assertEqual(report["competitive_recall"], 1.0)

    def test_unscored_import_is_replayable_but_excluded_from_baseline_metrics(self):
        feedback = {
            "jobs": {
                "Example::external": {
                    "label": "strong_match",
                    "snapshot": {
                        "score": None,
                        "description": "A replayable job description " * 20,
                    },
                }
            }
        }

        examples = benchmark_examples(feedback, {})
        report = evaluate_examples(examples)

        self.assertEqual(len(examples), 1)
        self.assertEqual(report["examples"], 0)

    def test_rescore_requires_gemini_key(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(RuntimeError, "GEMINI_API_KEY"):
                rescore_examples([])

    def test_analysis_failure_is_excluded_and_reported(self):
        examples = [
            {
                "feedback_id": "A::1",
                "label": "maybe",
                "snapshot": {
                    "job_id": "1",
                    "company": "A",
                    "title": "Program Manager",
                    "location": "Remote - US",
                    "url": "https://example.com/1",
                    "description": "Long job description " * 30,
                },
            }
        ]

        with patch.dict(os.environ, {"GEMINI_API_KEY": "test"}, clear=True):
            with patch("agent.evaluation.analyze_job", return_value={"score": 5, "reason": "Analysis unavailable"}):
                rescored, errors = rescore_examples(examples)

        self.assertNotIn("candidate", rescored[0])
        self.assertIn("Analysis unavailable", errors[0])


if __name__ == "__main__":
    unittest.main()
