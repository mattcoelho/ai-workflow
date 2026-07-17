import unittest

from scrapers.playwright_scraper import _generate_id, _is_company_specific_job_url


class PlaywrightScraperUrlTests(unittest.TestCase):
    def test_twilio_rejects_career_navigation_links(self):
        self.assertFalse(
            _is_company_specific_job_url("https://www.twilio.com/careers/dashboard", "Twilio")
        )
        self.assertTrue(
            _is_company_specific_job_url("https://www.twilio.com/careers/job/1099553537887", "Twilio")
        )

    def test_twilio_job_id_ignores_dynamic_card_text(self):
        url = "https://www.twilio.com/careers/job/1099553537887"

        self.assertEqual(
            _generate_id(
                url,
                "Staff Product Manager, Enterprise AIProduct ManagementRemote - USRemotePosted 2 days ago",
                "Twilio",
            ),
            "careers-job-1099553537887",
        )
        self.assertEqual(
            _generate_id(
                url,
                "Staff Product Manager, Enterprise AIProduct ManagementRemote - USRemotePosted 3 days ago",
                "Twilio",
            ),
            "careers-job-1099553537887",
        )


if __name__ == "__main__":
    unittest.main()
