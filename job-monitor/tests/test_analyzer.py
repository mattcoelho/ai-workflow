import json
import os
import unittest

from ai import analyzer


class _FakeResponse:
    def __init__(self, text):
        self.text = text


class _FakeModels:
    def __init__(self, response_text):
        self.response_text = response_text

    def generate_content(self, model, contents):
        return _FakeResponse(self.response_text)


class _FakeClient:
    def __init__(self, response_text):
        self.models = _FakeModels(response_text)


def _long_description(text):
    return (text + " ") * 25


class AnalyzerScoringTests(unittest.TestCase):
    def setUp(self):
        self.original_client = analyzer.genai.Client
        self.original_api_key = os.environ.get("GEMINI_API_KEY")
        os.environ["GEMINI_API_KEY"] = "test-key"

    def tearDown(self):
        analyzer.genai.Client = self.original_client
        if self.original_api_key is None:
            os.environ.pop("GEMINI_API_KEY", None)
        else:
            os.environ["GEMINI_API_KEY"] = self.original_api_key

    def _analyze_with_response(self, job, payload):
        analyzer.genai.Client = lambda api_key: _FakeClient(json.dumps(payload))
        return analyzer.analyze_job(job)

    def test_generic_twilio_principal_pm_without_description_caps_at_six(self):
        result = self._analyze_with_response(
            {
                "title": "Principal Product Manager",
                "company": "Twilio",
                "location": "Remote - US",
                "description": "",
            },
            {"score": 10, "reason": "Strong title", "summary": "Generic senior PM role."},
        )

        self.assertEqual(result["score"], 6)
        self.assertEqual(result["fit_tier"], "Watchlist")
        self.assertIn("No useful job description", " ".join(result["concerns"]))

    def test_support_agent_platform_role_can_score_bullseye(self):
        description = _long_description(
            "Own the AI support agent platform for enterprise customer service teams. "
            "Build agent skills, evals, guardrails, workflow automation, CRM handoff, "
            "human-in-the-loop escalation, and resolution quality for contact center operators."
        )

        result = self._analyze_with_response(
            {
                "title": "Staff Product Manager, Support AI Platform",
                "company": "Stripe",
                "location": "Remote - United States",
                "description": description,
            },
            {
                "score": 10,
                "reason": "Direct support AI platform fit.",
                "summary": "Owns support AI platform.",
                "competitive_angle": "Maps directly to Walmart support AI scale.",
                "evidence": ["AI support platform", "evals and guardrails"],
                "concerns": [],
            },
        )

        self.assertEqual(result["score"], 10)
        self.assertEqual(result["fit_tier"], "Bullseye")
        self.assertEqual(result["evidence"], ["AI support platform", "evals and guardrails"])

    def test_consumer_ai_without_support_workflow_or_platform_caps_at_six(self):
        description = _long_description(
            "Own AI experiences for a consumer baby registry and ecommerce shopping journey. "
            "Improve recommendations, personalization, discovery, conversion, and growth for shoppers."
        )

        result = self._analyze_with_response(
            {
                "title": "Staff Product Manager, AI Builder",
                "company": "Babylist",
                "location": "Remote - US",
                "description": description,
            },
            {"score": 9, "reason": "AI PM role", "summary": "Consumer AI role."},
        )

        self.assertEqual(result["score"], 6)
        self.assertEqual(result["fit_tier"], "Watchlist")
        self.assertIn("Consumer/marketplace", " ".join(result["concerns"]))

    def test_product_marketing_role_caps_at_four(self):
        description = _long_description(
            "Own product launches, positioning, sales enablement, campaigns, and marketing strategy "
            "for an enterprise SaaS product."
        )

        result = self._analyze_with_response(
            {
                "title": "Product Marketing Manager",
                "company": "ExampleCo",
                "location": "Remote - US",
                "description": description,
            },
            {"score": 9, "reason": "Enterprise SaaS", "summary": "Marketing role."},
        )

        self.assertEqual(result["score"], 4)
        self.assertEqual(result["fit_tier"], "Low Fit")

    def test_incompatible_location_caps_at_five(self):
        description = _long_description(
            "Own an AI support workflow platform with agentic automation, evals, guardrails, "
            "human handoff, CRM integration, and contact center resolution quality."
        )

        result = self._analyze_with_response(
            {
                "title": "Senior Product Manager, Support AI",
                "company": "ExampleCo",
                "location": "Remote - United Kingdom",
                "description": description,
            },
            {"score": 10, "reason": "Strong fit", "summary": "Support AI role."},
        )

        self.assertEqual(result["score"], 5)
        self.assertEqual(result["fit_tier"], "Watchlist")

    def test_international_only_locations_cap_even_when_extraction_says_compatible(self):
        description = _long_description(
            "Own an AI support workflow platform with agentic automation, evals, guardrails, "
            "human handoff, CRM integration, and contact center resolution quality."
        )

        for location in ("Greece", "Portugal", "Norway", "Hungary", "Toronto, ON, CA"):
            with self.subTest(location=location):
                result = self._analyze_with_response(
                    {
                        "title": "Senior Product Manager, Support AI",
                        "company": "ExampleCo",
                        "location": location,
                        "description": description,
                    },
                    {
                        "score": 9,
                        "reason": "Strong AI workflow fit.",
                        "summary": "Owns support AI workflow systems.",
                        "extraction": {
                            "role_type": "PM",
                            "seniority": "Senior",
                            "domain_lanes": ["enterprise_workflow", "agentic_automation"],
                            "location_fit": "compatible",
                            "evidence_strength": "strong",
                            "red_flags": [],
                            "confidence": 0.9,
                        },
                    },
                )

                self.assertEqual(result["score"], 5)
                self.assertEqual(result["fit_tier"], "Watchlist")
                self.assertIn("outside remote US", " ".join(result["concerns"]))

    def test_remote_us_and_bay_area_locations_remain_eligible(self):
        description = _long_description(
            "Own an AI support workflow platform with agentic automation, evals, guardrails, "
            "human handoff, CRM integration, and contact center resolution quality."
        )

        for location in ("United States", "Remote, US", "San Francisco, California, United States"):
            with self.subTest(location=location):
                result = self._analyze_with_response(
                    {
                        "title": "Senior Product Manager, Support AI",
                        "company": "ExampleCo",
                        "location": location,
                        "description": description,
                    },
                    {
                        "score": 9,
                        "reason": "Strong AI workflow fit.",
                        "summary": "Owns support AI workflow systems.",
                        "extraction": {
                            "role_type": "PM",
                            "seniority": "Senior",
                            "domain_lanes": ["enterprise_workflow", "agentic_automation"],
                            "location_fit": "remote_us",
                            "evidence_strength": "strong",
                            "red_flags": [],
                            "confidence": 0.9,
                        },
                    },
                )

                self.assertEqual(result["score"], 9)
                self.assertEqual(result["fit_tier"], "Bullseye")

    def test_structured_extraction_is_preserved_for_bullseye_role(self):
        description = _long_description(
            "Own AI support agents for enterprise customer service workflows with evals, "
            "guardrails, human handoff, and resolution automation."
        )

        result = self._analyze_with_response(
            {
                "title": "Principal Product Manager, AI Support Agents",
                "company": "ExampleCo",
                "location": "Remote - US",
                "description": description,
            },
            {
                "score": 10,
                "reason": "Direct bullseye.",
                "summary": "Owns support AI agents.",
                "competitive_angle": "Maps to support AI scale.",
                "evidence": ["AI support agents", "evals and guardrails"],
                "concerns": [],
                "extraction": {
                    "role_type": "PM",
                    "seniority": "Principal",
                    "domain_lanes": ["ai_support_agents", "enterprise_workflow", "evals_guardrails"],
                    "location_fit": "remote_us",
                    "evidence_strength": "strong",
                    "red_flags": [],
                    "confidence": 0.92,
                },
            },
        )

        self.assertEqual(result["score"], 10)
        self.assertEqual(result["extraction"]["role_type"], "PM")
        self.assertEqual(result["extraction"]["seniority"], "Principal")
        self.assertEqual(result["extraction"]["domain_lanes"], ["ai_support_agents", "enterprise_workflow", "evals_guardrails"])
        self.assertEqual(result["extraction"]["confidence"], 0.92)

    def test_structured_extraction_caps_intern_role(self):
        description = _long_description(
            "Internship supporting product and AI experiments for a four month fall program."
        )

        result = self._analyze_with_response(
            {
                "title": "Product & AI Intern 4 Months - Fall 2026",
                "company": "Dayforce",
                "location": "Remote - US",
                "description": description,
            },
            {
                "score": 8,
                "reason": "AI product exposure.",
                "summary": "Internship on AI product work.",
                "extraction": {
                    "role_type": "PM",
                    "seniority": "Intern",
                    "domain_lanes": ["other"],
                    "location_fit": "remote_us",
                    "evidence_strength": "weak",
                    "red_flags": ["internship"],
                    "confidence": 0.98,
                },
            },
        )

        self.assertEqual(result["score"], 2)
        self.assertEqual(result["fit_tier"], "Low Fit")
        self.assertIn("internship-level", " ".join(result["concerns"]))

    def test_structured_extraction_caps_non_pm_role(self):
        description = _long_description(
            "Own launch messaging, sales enablement, campaign planning, and positioning."
        )

        result = self._analyze_with_response(
            {
                "title": "Product Marketing Manager",
                "company": "ExampleCo",
                "location": "Remote - US",
                "description": description,
            },
            {
                "score": 8,
                "reason": "Product-adjacent.",
                "summary": "Marketing role.",
                "extraction": {
                    "role_type": "Marketing",
                    "seniority": "Senior",
                    "domain_lanes": ["marketing_sales"],
                    "location_fit": "remote_us",
                    "evidence_strength": "medium",
                    "red_flags": ["non-PM"],
                    "confidence": 0.87,
                },
            },
        )

        self.assertEqual(result["score"], 4)
        self.assertEqual(result["fit_tier"], "Low Fit")
        self.assertIn("Marketing", " ".join(result["concerns"]))


if __name__ == "__main__":
    unittest.main()
