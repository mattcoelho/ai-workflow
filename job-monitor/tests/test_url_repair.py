import unittest

from agent.url_repair import extract_candidate_links, repair_job_url


def _long_description(title):
    return (
        f"{title}. Own support AI workflows, evals, guardrails, handoff, and resolution quality. "
        * 8
    )


class UrlRepairTests(unittest.TestCase):
    def test_twilio_pid_url_repairs_to_job_url(self):
        title = "Principal Product Manager"
        job = {
            "id": "1099549995199",
            "title": title,
            "company": "Twilio",
            "url": "https://jobs.twilio.com/careers?pid=1099549995199",
            "description": "Twilio careers Search all jobs Product Operations Engineering Sales " * 10,
        }

        def fake_description(url):
            if url == "https://jobs.twilio.com/careers/job/1099549995199":
                return _long_description(title)
            return ""

        repair_job_url(
            job,
            max_attempts=2,
            fetch_description_func=fake_description,
            fetch_html_func=lambda url: self.fail("known transform should not fetch generic page html"),
        )

        self.assertEqual(job["url"], "https://jobs.twilio.com/careers/job/1099549995199")
        self.assertEqual(job["description_source"], "url_repair")
        self.assertEqual(job["url_repair"]["status"], "repaired")
        self.assertEqual(len(job["url_repair"]["attempts"]), 1)
        self.assertTrue(job["url_repair"]["attempts"][0]["accepted"])

    def test_repair_respects_max_attempts(self):
        job = {
            "id": "abc",
            "title": "Senior Product Manager, Support AI",
            "company": "ExampleCo",
            "url": "https://example.com/careers",
            "description": "ExampleCo careers open roles " * 20,
        }
        html = """
        <a href="/jobs/abc-one">Senior Product Manager, Support AI</a>
        <a href="/jobs/abc-two">Senior Product Manager, Support AI</a>
        """

        repair_job_url(
            job,
            max_attempts=1,
            fetch_description_func=lambda url: "Wrong job page " * 40,
            fetch_html_func=lambda url: html,
        )

        self.assertEqual(job["url_repair"]["status"], "max_attempts_reached")
        self.assertEqual(len(job["url_repair"]["attempts"]), 1)
        self.assertEqual(job["url"], "https://example.com/careers")

    def test_no_repair_when_verification_passes(self):
        title = "Staff Product Manager, Support AI Platform"
        job = {
            "title": title,
            "company": "ExampleCo",
            "url": "https://example.com/jobs/123",
            "description": _long_description(title),
        }

        repair_job_url(job, fetch_html_func=lambda url: self.fail("should not fetch html"))

        self.assertEqual(job["url_repair"]["status"], "not_needed")
        self.assertEqual(job["url"], "https://example.com/jobs/123")

    def test_extract_candidate_links_scores_title_and_job_id(self):
        job = {
            "id": "123",
            "title": "Senior Product Manager, Support AI",
            "company": "ExampleCo",
        }
        html = """
        <a href="/jobs/123">Senior Product Manager, Support AI</a>
        <a href="/about">About us</a>
        """

        candidates = extract_candidate_links(html, "https://example.com/careers", job)

        self.assertEqual(candidates[0]["url"], "https://example.com/jobs/123")
        self.assertGreater(candidates[0]["score"], 6)


if __name__ == "__main__":
    unittest.main()
