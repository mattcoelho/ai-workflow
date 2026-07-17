import unittest

from agent.verification import apply_verification_caps, collapse_duplicate_jobs, verify_job


class VerificationTests(unittest.TestCase):
    def test_generic_careers_url_with_weak_description_gets_cap(self):
        job = {
            "title": "Principal Product Manager",
            "company": "Twilio",
            "url": "https://jobs.twilio.com/careers",
            "description": "Careers at Twilio",
        }

        verification = verify_job(job)

        self.assertEqual(verification["score_cap"], 5)
        self.assertEqual(verification["quality"], "needs_review")
        self.assertIn("generic careers/search page", " ".join(verification["issues"]))

    def test_apply_verification_caps_lowers_score(self):
        job = {
            "title": "Principal Product Manager",
            "company": "Twilio",
            "url": "https://jobs.twilio.com/careers",
            "description": "Careers at Twilio",
            "score": 9,
            "fit_tier": "Bullseye",
            "concerns": [],
        }

        apply_verification_caps(job)

        self.assertEqual(job["score"], 5)
        self.assertEqual(job["fit_tier"], "Watchlist")
        self.assertIn("Self-check capped score", " ".join(job["concerns"]))

    def test_pid_careers_url_must_contain_exact_job_title(self):
        job = {
            "title": "Principal Product Manager",
            "company": "Twilio",
            "url": "https://jobs.twilio.com/careers?pid=1099549995199",
            "description": "Twilio careers Search all jobs Product Operations Engineering Sales " * 10,
        }

        verification = verify_job(job)

        self.assertEqual(verification["score_cap"], 5)
        self.assertIn("exact job title", " ".join(verification["issues"]))

    def test_job_specific_url_and_description_pass(self):
        job = {
            "title": "Staff Product Manager, Support AI Platform",
            "company": "ExampleCo",
            "url": "https://job-boards.greenhouse.io/example/jobs/123",
            "description": (
                "Staff Product Manager, Support AI Platform. Own support AI workflows, "
                "agentic automation, evals, guardrails, handoff, and customer resolution. "
                * 6
            ),
        }

        verification = verify_job(job)

        self.assertIsNone(verification["score_cap"])
        self.assertEqual(verification["quality"], "passed")

    def test_collapse_duplicate_jobs_uses_job_id(self):
        jobs = [
            {"id": "123", "company": "ExampleCo", "title": "Senior Product Manager", "url": "https://example.com/jobs/123"},
            {"id": "123", "company": "ExampleCo", "title": "Senior Product Manager", "url": "https://example.com/jobs/123"},
        ]

        unique, duplicate_notes = collapse_duplicate_jobs(jobs)

        self.assertEqual(len(unique), 1)
        self.assertEqual(len(duplicate_notes), 1)


if __name__ == "__main__":
    unittest.main()
