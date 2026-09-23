import unittest

from agent.evaluation import benchmark_examples, evaluate_examples, snapshot_from_ledger


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
            {"feedback_id": "A::1", "label": "strong_match", "snapshot": {"score": 9}},
            {"feedback_id": "B::2", "label": "bad_match", "snapshot": {"score": 8}},
            {"feedback_id": "C::3", "label": "maybe", "snapshot": {"score": 6}},
            {"feedback_id": "D::4", "label": "interviewed", "snapshot": {"score": 9}},
        ]

        report = evaluate_examples(examples)

        self.assertEqual(report["examples"], 4)
        self.assertEqual(report["range_accuracy"], 0.75)
        self.assertEqual(report["bullseye_precision"], 1.0)
        self.assertEqual(report["competitive_precision"], 0.667)
        self.assertEqual(report["competitive_recall"], 1.0)

    def test_bad_url_is_excluded_from_fit_benchmark(self):
        feedback = {"jobs": {"Example::123": {"label": "bad_url", "snapshot": {"score": 9}}}}

        self.assertEqual(benchmark_examples(feedback, {}), [])


if __name__ == "__main__":
    unittest.main()
