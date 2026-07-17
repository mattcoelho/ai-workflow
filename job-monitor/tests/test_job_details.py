import unittest

from scrapers.job_details import extract_greenhouse_description, extract_readable_text


class JobDetailsTests(unittest.TestCase):
    def test_extract_readable_text_prefers_job_description_content(self):
        html = """
        <html>
          <body>
            <nav>Careers Home Profile Login</nav>
            <main>
              <section class="job-description">
                <h1>Staff Product Manager</h1>
                <p>Own the AI support workflow platform.</p>
                <p>Build evals, guardrails, handoff, and resolution metrics.</p>
              </section>
            </main>
          </body>
        </html>
        """

        text = extract_readable_text(html)

        self.assertIn("Staff Product Manager", text)
        self.assertIn("AI support workflow platform", text)
        self.assertNotIn("Careers Home Profile Login", text)

    def test_extract_greenhouse_description_strips_html(self):
        content = """
        <div>
          <h2>About the role</h2>
          <p>Build agentic customer support automation for enterprise teams.</p>
        </div>
        """

        text = extract_greenhouse_description(content)

        self.assertEqual(
            text,
            "About the role Build agentic customer support automation for enterprise teams.",
        )


if __name__ == "__main__":
    unittest.main()
