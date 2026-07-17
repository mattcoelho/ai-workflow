import unittest

from notifier.email import _append_agent_audit, _append_job, _format_extraction, _format_job_url, _tier_for_job


class FormatJobUrlTests(unittest.TestCase):
    def test_twilio_job_url_is_not_rewritten_to_stale_pid(self):
        url = "https://jobs.twilio.com/careers/job/1099553537887"

        self.assertEqual(_format_job_url(url, "Twilio"), url)

    def test_twilio_pid_url_is_preserved_when_scraper_returns_one(self):
        url = "https://jobs.twilio.com/careers?pid=1099553537887"

        self.assertEqual(_format_job_url(url, "Twilio"), url)

    def test_tier_for_job_falls_back_to_score(self):
        self.assertEqual(_tier_for_job({"score": 9}), "Bullseye")
        self.assertEqual(_tier_for_job({"score": 7}), "Competitive")
        self.assertEqual(_tier_for_job({"score": 5}), "Watchlist")
        self.assertEqual(_tier_for_job({"score": 4}), "Low Fit")

    def test_append_job_includes_competitive_fields(self):
        body_lines = []

        _append_job(
            body_lines,
            {
                "score": 10,
                "title": "Staff Product Manager, Support AI Platform",
                "location": "Remote - US",
                "summary": "Owns an agentic support platform.",
                "competitive_angle": "Direct match to Walmart support AI scale.",
                "evidence": ["AI support platform", "evals and guardrails"],
                "concerns": ["Fintech domain ramp"],
                "reason": "Direct support AI platform fit.",
                "url": "https://example.com/job",
            },
            "Stripe",
        )

        body = "\n".join(body_lines)
        self.assertIn("Direct match to Walmart support AI scale.", body)
        self.assertIn("AI support platform; evals and guardrails", body)
        self.assertIn("Fintech domain ramp", body)

    def test_append_job_includes_feedback_id(self):
        body_lines = []

        _append_job(
            body_lines,
            {
                "id": "job-123",
                "score": 8,
                "title": "Senior Product Manager",
                "location": "Remote - US",
                "url": "https://example.com/job",
                "company": "ExampleCo",
            },
            "ExampleCo",
        )

        self.assertIn("Feedback ID: ExampleCo::job-123", "\n".join(body_lines))

    def test_agent_audit_section_summarizes_feedback_loop(self):
        body_lines = []

        _append_agent_audit(
            body_lines,
            {
                "stats": {
                    "scraped_jobs": 12,
                    "evaluated_jobs": 3,
                    "sent_in_email": 1,
                    "held_jobs": 2,
                    "duplicate_jobs": 1,
                    "verification_issues": 1,
                    "calibrated_jobs": 1,
                    "url_repair_attempts": 2,
                    "url_repairs": 1,
                    "url_repair_failures": 1,
                },
                "issues": ["ExampleCo - bad URL"],
                "calibrations": ["ExampleCo - raised floor"],
                "feedback_file": "data/feedback.json",
            },
        )

        body = "\n".join(body_lines)
        self.assertIn("Agent self-check", body)
        self.assertIn("Scraped 12 job(s)", body)
        self.assertIn("URL repair: 2 attempt(s), 1 fixed, 1 unresolved.", body)
        self.assertIn("edit data/feedback.json", body)

    def test_format_extraction_summarizes_structured_fields(self):
        text = _format_extraction(
            {
                "role_type": "PM",
                "seniority": "Principal",
                "domain_lanes": ["ai_support_agents", "evals_guardrails"],
                "location_fit": "remote_us",
                "evidence_strength": "strong",
                "confidence": 0.91,
            }
        )

        self.assertIn("Role: PM", text)
        self.assertIn("Level: Principal", text)
        self.assertIn("Lanes: ai_support_agents; evals_guardrails", text)
        self.assertIn("Confidence: 0.91", text)


if __name__ == "__main__":
    unittest.main()
