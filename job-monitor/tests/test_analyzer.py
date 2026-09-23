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

    def generate_content(self, model, contents, **kwargs):
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

    def test_program_delivery_without_product_ownership_caps_at_six(self):
        description = _long_description(
            "Lead cross-functional customer support programs across contact center technology, "
            "operations, engineering, and platform teams."
        )

        result = self._analyze_with_response(
            {
                "title": "Program Manager, Community Support",
                "company": "ExampleCo",
                "location": "Remote - US",
                "description": description,
            },
            {
                "score": 9,
                "reason": "Support domain match.",
                "summary": "Coordinates support technology programs.",
                "extraction": {
                    "role_type": "Program",
                    "seniority": "Senior",
                    "domain_lanes": ["customer_service_resolution", "enterprise_workflow"],
                    "location_fit": "remote_us",
                    "work_mode": "remote_us",
                    "evidence_strength": "strong",
                    "red_flags": [],
                    "confidence": 0.95,
                    "gates": {
                        "owns_product_strategy": {"value": False, "evidence": "Executes programs."},
                        "owns_support_resolution_platform": {"value": False, "evidence": "No product ownership."},
                        "role_is_program_delivery": {"value": True, "evidence": "Cross-functional programs."},
                        "ai_is_core_scope": {"value": False, "evidence": "AI is not named."},
                        "serves_internal_operators": {"value": True, "evidence": "Contact center teams."},
                        "candidate_has_direct_proof": {"value": True, "evidence": "Support scale."},
                    },
                },
            },
        )

        self.assertEqual(result["score"], 6)
        self.assertEqual(result["fit_tier"], "Watchlist")
        self.assertIn("Program delivery", " ".join(result["concerns"]))

    def test_required_bay_area_attendance_caps_at_eight(self):
        description = _long_description(
            "Own AI support quality, automated resolution, human escalation, and support agent "
            "platform strategy. This hybrid role requires commuting to the Bay Area office."
        )

        result = self._analyze_with_response(
            {
                "title": "Staff Product Manager, Intelligent Customer Experience",
                "company": "ExampleCo",
                "location": "San Francisco, California",
                "description": description,
            },
            {
                "score": 10,
                "reason": "Direct support AI fit.",
                "summary": "Owns AI support products.",
                "extraction": {
                    "role_type": "PM",
                    "seniority": "Staff",
                    "domain_lanes": ["ai_support_agents", "customer_service_resolution"],
                    "location_fit": "bay_area",
                    "work_mode": "hybrid_bay_area",
                    "evidence_strength": "strong",
                    "red_flags": [],
                    "confidence": 0.98,
                    "gates": {
                        "owns_product_strategy": {"value": True, "evidence": "Own strategy and roadmap."},
                        "owns_support_resolution_platform": {"value": True, "evidence": "Automated resolution."},
                        "role_is_program_delivery": {"value": False, "evidence": "Product role."},
                        "ai_is_core_scope": {"value": True, "evidence": "AI support quality."},
                        "serves_internal_operators": {"value": True, "evidence": "Human support escalation."},
                        "candidate_has_direct_proof": {"value": True, "evidence": "Direct candidate evidence."},
                    },
                },
            },
        )

        self.assertEqual(result["score"], 8)
        self.assertEqual(result["fit_tier"], "Competitive")
        self.assertIn("office attendance", " ".join(result["concerns"]))

    def test_direct_remote_support_platform_can_be_bullseye_without_ai(self):
        description = _long_description(
            "Own product strategy and roadmap for platforms powering end-to-end customer support "
            "journeys, resolution capabilities, and support experiences."
        )

        result = self._analyze_with_response(
            {
                "title": "Senior Product Manager, Community Support Experience",
                "company": "ExampleCo",
                "location": "Remote - US",
                "description": description,
            },
            {
                "score": 9,
                "reason": "Direct support platform ownership.",
                "summary": "Owns support experience platforms.",
                "extraction": {
                    "role_type": "PM",
                    "seniority": "Senior",
                    "domain_lanes": ["customer_service_resolution", "enterprise_workflow"],
                    "location_fit": "remote_us",
                    "work_mode": "remote_us",
                    "evidence_strength": "strong",
                    "red_flags": [],
                    "confidence": 0.96,
                    "gates": {
                        "owns_product_strategy": {"value": True, "evidence": "Own strategy and roadmap."},
                        "owns_support_resolution_platform": {"value": True, "evidence": "Support journeys."},
                        "role_is_program_delivery": {"value": False, "evidence": "PM ownership."},
                        "ai_is_core_scope": {"value": False, "evidence": "AI not explicit."},
                        "serves_internal_operators": {"value": True, "evidence": "Support experience."},
                        "candidate_has_direct_proof": {"value": True, "evidence": "Comparable support scale."},
                    },
                },
            },
        )

        self.assertEqual(result["score"], 9)
        self.assertEqual(result["fit_tier"], "Bullseye")
        self.assertFalse(result["extraction"]["gates"]["ai_is_core_scope"]["value"])

    def test_direct_support_product_pm_has_floor_of_eight(self):
        description = _long_description(
            "Own product vision, strategy, and roadmap for a foundational customer support "
            "service used by external customers."
        )

        result = self._analyze_with_response(
            {
                "title": "Product Manager, Community Support",
                "company": "ExampleCo",
                "location": "Remote - US",
                "description": description,
            },
            {
                "score": 7,
                "reason": "External consumer support product.",
                "summary": "Owns a customer support service.",
                "extraction": {
                    "role_type": "PM",
                    "seniority": "Senior",
                    "domain_lanes": ["customer_service_resolution"],
                    "location_fit": "remote_us",
                    "work_mode": "remote_us",
                    "evidence_strength": "strong",
                    "red_flags": [],
                    "confidence": 0.95,
                    "gates": {
                        "owns_product_strategy": {"value": True, "evidence": "Owns strategy."},
                        "owns_support_resolution_platform": {"value": True, "evidence": "Support service."},
                        "role_is_program_delivery": {"value": False, "evidence": "PM role."},
                        "ai_is_core_scope": {"value": False, "evidence": "No AI."},
                        "serves_internal_operators": {"value": False, "evidence": "External users."},
                        "candidate_has_direct_proof": {"value": True, "evidence": "Direct support proof."},
                    },
                },
            },
        )

        self.assertEqual(result["score"], 8)

    def test_external_ai_platform_without_support_or_internal_users_caps_at_seven(self):
        description = _long_description(
            "Own product strategy for custom AI models and self-hosted agent orchestration "
            "for external DevSecOps customers."
        )

        result = self._analyze_with_response(
            {
                "title": "Principal Product Manager, AI Custom Models",
                "company": "ExampleCo",
                "location": "Remote - US",
                "description": description,
            },
            {
                "score": 8,
                "reason": "Strong adjacent AI platform role.",
                "summary": "Owns custom AI model products.",
                "extraction": {
                    "role_type": "PM",
                    "seniority": "Principal",
                    "domain_lanes": ["ai_platform_api", "enterprise_agent_infrastructure"],
                    "location_fit": "remote_us",
                    "work_mode": "remote_us",
                    "evidence_strength": "strong",
                    "red_flags": [],
                    "confidence": 0.98,
                    "gates": {
                        "owns_product_strategy": {"value": True, "evidence": "Owns strategy."},
                        "owns_support_resolution_platform": {"value": False, "evidence": "DevSecOps."},
                        "role_is_program_delivery": {"value": False, "evidence": "PM role."},
                        "ai_is_core_scope": {"value": True, "evidence": "AI models."},
                        "serves_internal_operators": {"value": False, "evidence": "External customers."},
                        "candidate_has_direct_proof": {"value": True, "evidence": "Agentic AI proof."},
                    },
                },
            },
        )

        self.assertEqual(result["score"], 7)

    def test_director_software_product_management_is_recognized_as_product_role(self):
        description = _long_description(
            "Develop customer service product strategy, roadmaps, and requirements for AI chatbots, "
            "agent assist, CRM, and omnichannel support infrastructure."
        )

        result = self._analyze_with_response(
            {
                "title": "Director, Software Product Management, Customer Support",
                "company": "ExampleCo",
                "location": "South San Francisco, California",
                "description": description,
            },
            {
                "score": 9,
                "reason": "Direct support product ownership.",
                "summary": "Owns AI support product portfolio.",
                "extraction": {
                    "role_type": "PM",
                    "seniority": "Director",
                    "domain_lanes": ["ai_support_agents", "customer_service_resolution"],
                    "location_fit": "bay_area",
                    "work_mode": "onsite_bay_area",
                    "evidence_strength": "strong",
                    "red_flags": [],
                    "confidence": 1.0,
                    "gates": {
                        "owns_product_strategy": {"value": True, "evidence": "Owns strategy."},
                        "owns_support_resolution_platform": {"value": True, "evidence": "Support portfolio."},
                        "role_is_program_delivery": {"value": False, "evidence": "PM role."},
                        "ai_is_core_scope": {"value": True, "evidence": "AI chatbots."},
                        "serves_internal_operators": {"value": True, "evidence": "Agent assist."},
                        "candidate_has_direct_proof": {"value": True, "evidence": "Direct proof."},
                    },
                },
            },
        )

        self.assertEqual(result["score"], 8)
        self.assertNotIn("No direct PM", " ".join(result["concerns"]))

    def test_external_non_ai_support_product_caps_at_eight(self):
        description = _long_description(
            "Own product vision and roadmap for a foundational customer support service serving "
            "external guests and hosts."
        )

        result = self._analyze_with_response(
            {
                "title": "Product Manager, Community Support",
                "company": "ExampleCo",
                "location": "Remote - US",
                "description": description,
            },
            {
                "score": 9,
                "reason": "Direct support PM.",
                "summary": "Owns external customer support product.",
                "extraction": {
                    "role_type": "PM",
                    "seniority": "Senior",
                    "domain_lanes": ["customer_service_resolution"],
                    "location_fit": "remote_us",
                    "work_mode": "remote_us",
                    "evidence_strength": "strong",
                    "red_flags": [],
                    "confidence": 0.96,
                    "gates": {
                        "owns_product_strategy": {"value": True, "evidence": "Owns roadmap."},
                        "owns_support_resolution_platform": {"value": True, "evidence": "Support service."},
                        "role_is_program_delivery": {"value": False, "evidence": "PM role."},
                        "ai_is_core_scope": {"value": False, "evidence": "No AI."},
                        "serves_internal_operators": {"value": False, "evidence": "External users."},
                        "candidate_has_direct_proof": {"value": True, "evidence": "Support proof."},
                    },
                },
            },
        )

        self.assertEqual(result["score"], 8)

    def test_strong_enterprise_workflow_tpm_has_floor_of_five(self):
        description = _long_description(
            "Lead technical programs for enterprise platform services, operational tooling, "
            "distributed systems, and cross-organization execution."
        )

        result = self._analyze_with_response(
            {
                "title": "Senior Technical Program Manager, Platform Services",
                "company": "ExampleCo",
                "location": "San Francisco, California",
                "description": description,
            },
            {
                "score": 3,
                "reason": "Adjacent TPM role.",
                "summary": "Leads enterprise platform programs.",
                "extraction": {
                    "role_type": "TPM",
                    "seniority": "Senior",
                    "domain_lanes": ["enterprise_workflow"],
                    "location_fit": "bay_area",
                    "work_mode": "hybrid_bay_area",
                    "evidence_strength": "strong",
                    "red_flags": [],
                    "confidence": 0.98,
                    "gates": {
                        "owns_product_strategy": {"value": False, "evidence": "Executes strategy."},
                        "owns_support_resolution_platform": {"value": False, "evidence": "Logistics platform."},
                        "role_is_program_delivery": {"value": True, "evidence": "TPM execution."},
                        "ai_is_core_scope": {"value": False, "evidence": "No AI."},
                        "serves_internal_operators": {"value": False, "evidence": "External users."},
                        "candidate_has_direct_proof": {"value": False, "evidence": "Adjacent proof."},
                    },
                },
            },
        )

        self.assertEqual(result["score"], 5)


if __name__ == "__main__":
    unittest.main()
