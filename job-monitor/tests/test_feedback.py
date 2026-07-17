import unittest

from agent.feedback import apply_feedback_calibration, feedback_id


def _job(score=8):
    return {
        "id": "job-123",
        "company": "ExampleCo",
        "title": "Senior Product Manager, Support AI",
        "location": "Remote - US",
        "url": "https://example.com/jobs/job-123",
        "description": "Own support AI workflows, guardrails, evals, and customer resolution automation.",
        "score": score,
        "fit_tier": "Competitive",
        "evidence": [],
        "concerns": [],
    }


class FeedbackCalibrationTests(unittest.TestCase):
    def test_feedback_id_uses_company_and_job_id(self):
        self.assertEqual(feedback_id(_job()), "ExampleCo::job-123")

    def test_direct_bad_url_feedback_caps_score(self):
        job = _job(score=9)
        feedback = {"jobs": {feedback_id(job): {"label": "bad_url", "notes": "Opened careers page."}}}

        apply_feedback_calibration(job, feedback)

        self.assertEqual(job["score"], 3)
        self.assertEqual(job["fit_tier"], "Low Fit")
        self.assertIn("job URL as inaccurate", " ".join(job["concerns"]))

    def test_interview_feedback_raises_floor(self):
        job = _job(score=6)
        feedback = {"jobs": {feedback_id(job): {"label": "interviewed", "notes": "Recruiter screen."}}}

        apply_feedback_calibration(job, feedback)

        self.assertEqual(job["score"], 9)
        self.assertEqual(job["fit_tier"], "Bullseye")
        self.assertIn("Interview signal", " ".join(job["evidence"]))

    def test_rule_can_cap_recurring_pattern(self):
        job = _job(score=9)
        feedback = {
            "rules": [
                {
                    "name": "Cap generic consumer AI",
                    "title_contains": "Product Manager",
                    "description_contains": "customer resolution",
                    "cap": 6,
                    "concern": "Manual rule keeps this pattern on watchlist.",
                }
            ]
        }

        apply_feedback_calibration(job, feedback)

        self.assertEqual(job["score"], 6)
        self.assertEqual(job["fit_tier"], "Watchlist")
        self.assertIn("Manual rule", " ".join(job["concerns"]))


if __name__ == "__main__":
    unittest.main()
