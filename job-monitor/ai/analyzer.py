"""Gemini AI analyzer for competitive job fit."""

import json
import os
import re
import time
from typing import Any, Dict, List, Tuple

from google import genai
from google.genai import types

from ai.candidate_profile import CANDIDATE_FIT_PROFILE

MAX_DESCRIPTION_CHARS = 12_000
ANALYZER_VARIANT = os.getenv("JOB_ANALYZER_VARIANT", "production")
ANALYZER_VERSION = (
    "competitive-fit-v3-structured-gates"
    if ANALYZER_VARIANT == "structured_gates_v3"
    else "competitive-fit-v2"
)
GEMINI_MODEL = "gemini-2.5-flash"

ROLE_TYPES = {
    "PM",
    "TPM",
    "Product Ops",
    "Program",
    "FDE",
    "Marketing",
    "Sales",
    "Engineering",
    "Finance",
    "Other",
    "Unknown",
}
COMPETITIVE_ROLE_TYPES = {"PM", "TPM", "Product Ops", "Program", "FDE"}
SENIORITIES = {
    "Intern",
    "Associate",
    "PM",
    "Senior",
    "Staff",
    "Principal",
    "Director",
    "VP",
    "Unknown",
}
DOMAIN_LANES = {
    "ai_support_agents",
    "customer_service_resolution",
    "enterprise_workflow",
    "internal_ai_tools",
    "agentic_automation",
    "human_ai_handoff",
    "evals_guardrails",
    "ai_platform_api",
    "enterprise_agent_infrastructure",
    "regulated_ai_ops",
    "consumer_marketplace",
    "ads_growth",
    "marketing_sales",
    "hardware",
    "devtools",
    "finance",
    "other",
}
LOCATION_FITS = {"remote_us", "bay_area", "compatible", "incompatible", "unclear"}
EVIDENCE_STRENGTHS = {"strong", "medium", "weak", "none"}
WORK_MODES = {"remote_us", "hybrid_bay_area", "onsite_bay_area", "incompatible", "unclear"}
GATE_KEYS = {
    "owns_product_strategy",
    "owns_support_resolution_platform",
    "role_is_program_delivery",
    "ai_is_core_scope",
    "serves_internal_operators",
    "candidate_has_direct_proof",
    "requires_specialist_domain_expertise",
}

ROLE_SIGNAL_RE = re.compile(
    r"\b(product manager|product lead|group product|head of product|director of product|"
    r"staff product|principal product|senior product|product operations|technical product manager|"
    r"director(?:,| of)?\s+(?:software\s+)?product management|product management director|"
    r"\btpm\b|technical program manager|program manager|forward deployed engineer|\bfde\b)\b",
    re.IGNORECASE,
)
NON_PRODUCT_ROLE_RE = re.compile(
    r"\b(product marketing|marketing manager|marketing analyst|sales representative|account executive|"
    r"business development|finance manager|financial analyst|software engineer|machine learning engineer|"
    r"data engineer|security engineer|designer|recruiter|customer success manager)\b",
    re.IGNORECASE,
)
AI_RE = re.compile(r"\b(ai|ml|llm|genai|generative ai|agentic|agent|machine learning|automation)\b", re.IGNORECASE)
SUPPORT_WORKFLOW_PLATFORM_RE = re.compile(
    r"\b(support|customer service|customer care|contact center|resolution|workflow|rules engine|"
    r"approval|internal tool|enterprise ai|platform|api|agent skill|eval|evaluation|guardrail|"
    r"human-in-the-loop|handoff|operator|crm|zendesk|salesforce|itsm|incident|automation)\b",
    re.IGNORECASE,
)
CONSUMER_MARKETPLACE_RE = re.compile(
    r"\b(consumer|marketplace|shopper|shopping|grocery|registry|merchant|delivery|restaurant|"
    r"dasher|host|guest|ads|advertising|growth|commerce)\b",
    re.IGNORECASE,
)
EXPLICIT_US_OR_BAY_LOCATION_RE = re.compile(
    r"\b(remote\s*[-,/]?\s*(us|u\.s\.|usa|united states)|"
    r"united states|u\.s\.|usa|us|"
    r"san francisco|sf bay|bay area|california|ca\s*,\s*(us|u\.s\.|usa|united states))\b",
    re.IGNORECASE,
)
REMOTE_LOCATION_RE = re.compile(
    r"\b(remote|distributed|work from anywhere|anywhere|worldwide)\b",
    re.IGNORECASE,
)
INCOMPATIBLE_LOCATION_RE = re.compile(
    r"\b(india|united kingdom|uk|singapore|colombia|canada|toronto|vancouver|"
    r"montreal|ontario|quebec|australia|germany|france|netherlands|poland|spain|"
    r"ireland|italy|greece|portugal|norway|hungary|sweden|denmark|finland|"
    r"belgium|switzerland|austria|czech|romania|bulgaria|croatia|serbia|turkey|"
    r"israel|brazil|argentina|chile|mexico|costa rica|japan|korea|china|"
    r"hong kong|taiwan|philippines|vietnam|thailand|indonesia|malaysia|"
    r"london|dublin|athens|lisbon|oslo|budapest|amsterdam|berlin|paris|madrid|"
    r"barcelona|warsaw|emea|europe|european|apac|latam)\b",
    re.IGNORECASE,
)


def fit_tier_for_score(score: int) -> str:
    if score >= 9:
        return "Bullseye"
    if score >= 7:
        return "Competitive"
    if score >= 5:
        return "Watchlist"
    return "Low Fit"


def _combined_text(job: Dict[str, str]) -> str:
    return " ".join(
        str(job.get(key, "") or "")
        for key in ("title", "company", "location", "description")
    )


def _has_useful_description(job: Dict[str, str]) -> bool:
    return len(str(job.get("description", "") or "").strip()) >= 300


def _is_location_compatible(job: Dict[str, str]) -> bool:
    location = str(job.get("location", "") or "")
    if not location:
        return True
    if EXPLICIT_US_OR_BAY_LOCATION_RE.search(location):
        return True
    if INCOMPATIBLE_LOCATION_RE.search(location):
        return False
    if REMOTE_LOCATION_RE.search(location):
        return True
    return False


def apply_score_caps(job: Dict[str, str], raw_score: int) -> Tuple[int, List[str]]:
    """Apply deterministic caps so scores reflect evidence-backed competitiveness."""
    score = max(1, min(10, int(raw_score)))
    concerns: List[str] = []
    title = str(job.get("title", "") or "")
    text = _combined_text(job)

    if not _has_useful_description(job):
        score = min(score, 6)
        concerns.append("No useful job description available; title/company signal only.")

    if NON_PRODUCT_ROLE_RE.search(title):
        score = min(score, 4)
        concerns.append("Title appears non-product or non-adjacent.")
    elif not ROLE_SIGNAL_RE.search(text):
        score = min(score, 4)
        concerns.append("No direct PM, TPM, Product Ops, or FDE-adjacent role signal.")

    if AI_RE.search(text) and not SUPPORT_WORKFLOW_PLATFORM_RE.search(text):
        score = min(score, 7)
        concerns.append("AI signal is generic without support, workflow, or platform evidence.")

    if CONSUMER_MARKETPLACE_RE.search(text) and not SUPPORT_WORKFLOW_PLATFORM_RE.search(text):
        score = min(score, 6)
        concerns.append("Consumer/marketplace role lacks a clear support, workflow, or platform bridge.")

    if not _is_location_compatible(job):
        score = min(score, 5)
        concerns.append("Location appears outside remote US or SF Bay Area fit.")

    return score, concerns


def _parse_json_response(response_text: str) -> Dict[str, Any]:
    text = (response_text or "").strip()
    text = re.sub(r"^```[a-z]*\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    text = re.sub(r",\s*([}\]])", r"\1", text.strip())
    return json.loads(text)


def _listify(value: Any, max_items: int = 4) -> List[str]:
    if value is None:
        return []
    if isinstance(value, list):
        items = value
    else:
        items = [value]
    return [str(item).strip()[:180] for item in items if str(item).strip()][:max_items]


def _normalize_choice(value: Any, allowed_values: set, default: str) -> str:
    text = str(value or "").strip()
    for allowed in allowed_values:
        if text.lower() == allowed.lower():
            return allowed
    return default


def _normalize_confidence(value: Any) -> float:
    try:
        confidence = float(value)
    except (TypeError, ValueError):
        return 0.0
    return max(0.0, min(1.0, confidence))


def _normalize_gate(value: Any) -> Dict[str, Any]:
    gate = value if isinstance(value, dict) else {}
    raw_value = gate.get("value")
    if isinstance(raw_value, bool):
        normalized_value = raw_value
    elif str(raw_value).strip().lower() in {"true", "yes"}:
        normalized_value = True
    elif str(raw_value).strip().lower() in {"false", "no"}:
        normalized_value = False
    else:
        normalized_value = None
    return {
        "value": normalized_value,
        "evidence": str(gate.get("evidence", "") or "").strip()[:240],
    }


def _normalize_extraction(value: Any) -> Dict[str, Any]:
    extraction = value if isinstance(value, dict) else {}
    domain_lanes = [
        lane
        for lane in (
            _normalize_choice(item, DOMAIN_LANES, "")
            for item in _listify(extraction.get("domain_lanes"), max_items=8)
        )
        if lane
    ]

    raw_gates = extraction.get("gates") if isinstance(extraction.get("gates"), dict) else {}
    gates = {
        key: _normalize_gate(raw_gates.get(key))
        for key in GATE_KEYS
    }

    normalized = {
        "role_type": _normalize_choice(extraction.get("role_type"), ROLE_TYPES, "Unknown"),
        "seniority": _normalize_choice(extraction.get("seniority"), SENIORITIES, "Unknown"),
        "domain_lanes": domain_lanes[:6],
        "location_fit": _normalize_choice(extraction.get("location_fit"), LOCATION_FITS, "unclear"),
        "evidence_strength": _normalize_choice(extraction.get("evidence_strength"), EVIDENCE_STRENGTHS, "weak"),
        "red_flags": _listify(extraction.get("red_flags"), max_items=6),
        "confidence": _normalize_confidence(extraction.get("confidence")),
        "work_mode": _normalize_choice(extraction.get("work_mode"), WORK_MODES, "unclear"),
        "gates": gates,
    }
    return normalized


def apply_extraction_caps(score: int, extraction: Dict[str, Any]) -> Tuple[int, List[str]]:
    """Apply deterministic caps from Gemini's structured semantic extraction."""
    score = max(1, min(10, int(score)))
    concerns: List[str] = []
    role_type = extraction.get("role_type", "Unknown")
    seniority = extraction.get("seniority", "Unknown")
    location_fit = extraction.get("location_fit", "unclear")
    evidence_strength = extraction.get("evidence_strength", "weak")
    red_flags = " ".join(extraction.get("red_flags", [])).lower()
    work_mode = extraction.get("work_mode", "unclear")
    gates = extraction.get("gates") or {}

    def gate_value(name: str) -> Any:
        gate = gates.get(name) or {}
        return gate.get("value")

    if role_type not in COMPETITIVE_ROLE_TYPES and role_type != "Unknown":
        score = min(score, 4)
        concerns.append(f"Structured extraction classified role as {role_type}, not PM-adjacent.")

    if seniority == "Intern" or "intern" in red_flags or "internship" in red_flags:
        score = min(score, 2)
        concerns.append("Structured extraction flagged internship-level seniority.")
    elif seniority == "Associate":
        score = min(score, 5)
        concerns.append("Structured extraction flagged below-target seniority.")

    direct_support_pm = (
        role_type == "PM"
        and gate_value("owns_product_strategy") is True
        and gate_value("owns_support_resolution_platform") is True
        and gate_value("candidate_has_direct_proof") is True
        and gate_value("role_is_program_delivery") is False
    )
    if direct_support_pm:
        score = max(score, 8)

    external_non_ai_support_pm = (
        direct_support_pm
        and gate_value("ai_is_core_scope") is False
        and gate_value("serves_internal_operators") is False
    )
    if external_non_ai_support_pm:
        score = min(score, 8)
        concerns.append("External-customer support product lacks AI or internal-operator scope for Bullseye.")

    adjacent_program_role = (
        role_type in {"TPM", "Program"}
        and gate_value("role_is_program_delivery") is True
        and evidence_strength == "strong"
        and bool(set(extraction.get("domain_lanes", [])) & {"customer_service_resolution", "enterprise_workflow"})
        and location_fit != "incompatible"
    )
    if adjacent_program_role:
        score = max(score, 5)

    adjacent_external_ai_pm = (
        role_type == "PM"
        and gate_value("ai_is_core_scope") is True
        and gate_value("owns_support_resolution_platform") is False
        and gate_value("serves_internal_operators") is False
    )
    if adjacent_external_ai_pm:
        score = min(score, 7)
        concerns.append("AI platform role lacks direct support-platform or internal-operator alignment.")

    specialist_domain_gap = (
        gate_value("requires_specialist_domain_expertise") is True
        and gate_value("candidate_has_direct_proof") is False
    )
    if specialist_domain_gap:
        score = min(score, 6)
        concerns.append("Core specialist-domain expertise is required without direct candidate proof.")

    if location_fit == "incompatible":
        score = min(score, 5)
        concerns.append("Structured extraction flagged incompatible location.")

    if work_mode in {"hybrid_bay_area", "onsite_bay_area"}:
        score = min(score, 8)
        concerns.append("Required Bay Area office attendance keeps this below Bullseye.")

    if gate_value("role_is_program_delivery") is True and gate_value("owns_product_strategy") is False:
        score = min(score, 6)
        concerns.append("Program delivery without direct product strategy ownership caps this at Watchlist.")

    if evidence_strength == "none":
        score = min(score, 5)
        concerns.append("Structured extraction found no competitive-fit evidence.")
    elif evidence_strength == "weak":
        score = min(score, 7)
        concerns.append("Structured extraction found weak competitive-fit evidence.")

    return score, concerns


def _fallback(score: int, reason: str, summary: str = "", job: Dict[str, str] = None) -> Dict[str, Any]:
    job = job or {}
    capped_score, cap_concerns = apply_score_caps(job, score)
    return {
        "score": capped_score,
        "fit_tier": fit_tier_for_score(capped_score),
        "reason": reason[:200],
        "summary": summary[:500],
        "competitive_angle": "",
        "evidence": [],
        "concerns": cap_concerns,
        "extraction": {},
    }


def _normalize_result(result: Dict[str, Any], job: Dict[str, str]) -> Dict[str, Any]:
    raw_score = int(result.get("score", 5))
    raw_extraction = result.get("extraction")
    has_extraction = isinstance(raw_extraction, dict) and bool(raw_extraction)
    extraction = _normalize_extraction(raw_extraction)
    capped_score, cap_concerns = apply_score_caps(job, raw_score)
    extraction_concerns: List[str] = []
    if has_extraction:
        capped_score, extraction_concerns = apply_extraction_caps(capped_score, extraction)
    ai_concerns = _listify(result.get("concerns"))

    return {
        "score": capped_score,
        "fit_tier": fit_tier_for_score(capped_score),
        "reason": str(result.get("reason", ""))[:200],
        "summary": str(result.get("summary", ""))[:500],
        "competitive_angle": str(result.get("competitive_angle", ""))[:300],
        "evidence": _listify(result.get("evidence")),
        "concerns": (ai_concerns + cap_concerns + extraction_concerns)[:6],
        "extraction": extraction if has_extraction else {},
    }


def analyze_job(job: Dict[str, str]) -> Dict[str, Any]:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return _fallback(5, "No API key", "", job)

    response_text = ""
    try:
        client = genai.Client(api_key=api_key)

        job_title = job.get("title", "")
        company = job.get("company", "")
        location = job.get("location", "") or "Not specified"
        description = str(job.get("description", "") or "")[:MAX_DESCRIPTION_CHARS]

        if ANALYZER_VARIANT == "structured_gates_v3":
            scoring_guidance = """Scoring rules:
- 9-10: Direct PM ownership of support/resolution platforms or AI support agents, remote-US fit, and direct candidate proof. Explicit AI language is not required when support-platform ownership is a direct match.
- 8: Strong direct fit with one meaningful constraint, including required Bay Area attendance or consumer-support scope without clear support-platform ownership.
- 7: Competitive adjacent PM role, such as AI/platform ownership without direct support, resolution, or internal-operator alignment.
- 5-6: Interesting but not strongly competitive; watchlist only.
- 1-4: Poor fit, non-PM, wrong domain, wrong location, or unsupported title.

Structured gating instructions:
- Answer every gate from explicit job-description evidence. Do not infer ownership from company, organization, title prestige, or phrases such as platform, workflow, customer experience, or AI.
- Distinguish owning product strategy, roadmap, prioritization, and product outcomes from coordinating programs or executing cross-functional initiatives.
- Program/TPM work without direct product-strategy ownership should score 5-6 even when the customer-support domain is relevant.
- Customer Success, CCO, GTM, or customer-experience proximity is not the same as owning a customer-support product.
- A direct support-platform PM can score 9-10 without explicit AI when the candidate has direct evidence at comparable scale.
- Direct PM ownership of a customer-support service or journey with direct candidate proof should score at least 8 even when users are external customers and AI is not explicit.
- External-customer support PM work without explicit AI or internal support-operator scope should score 8 rather than 9-10.
- AI/platform PM work with neither support-platform ownership nor internal-operator users should score 7, even when seniority and AI scope are strong.
- Roles requiring deep specialist-domain ownership, such as security architecture, IAM, risk management, finance, legal, or regulated clinical expertise, should score 5-6 when the candidate lacks direct proof in that specialty, even if AI or platform adjacency is strong.
- TPM/Program roles with strong customer-support or enterprise-workflow adjacency should remain 5-6 rather than falling to Low Fit.
- Required Bay Area hybrid or onsite attendance keeps an otherwise excellent role at 8. Remote-US roles do not receive this penalty."""
            gate_schema = """,
    "work_mode": "remote_us|hybrid_bay_area|onsite_bay_area|incompatible|unclear",
    "gates": {
      "owns_product_strategy": {"value": <true|false>, "evidence": "<quote or concise explicit evidence>"},
      "owns_support_resolution_platform": {"value": <true|false>, "evidence": "<quote or concise explicit evidence>"},
      "role_is_program_delivery": {"value": <true|false>, "evidence": "<quote or concise explicit evidence>"},
      "ai_is_core_scope": {"value": <true|false>, "evidence": "<quote or concise explicit evidence>"},
      "serves_internal_operators": {"value": <true|false>, "evidence": "<whether the hiring company's own support, operations, or business employees are primary users; external customer teams do not count>"},
      "candidate_has_direct_proof": {"value": <true|false>, "evidence": "<candidate proof point or missing bridge>"},
      "requires_specialist_domain_expertise": {"value": <true|false>, "evidence": "<explicit required expertise central to success, such as security architecture, IAM, risk management, finance, legal, or regulated clinical work>"}
    }"""
        else:
            scoring_guidance = """Scoring rules:
- 9-10: Direct evidence across seniority, location, domain, ownership, and candidate proof points. These are bullseye roles.
- 7-8: Competitive with one meaningful gap or bridge.
- 5-6: Interesting but not strongly competitive; watchlist only.
- 1-4: Poor fit, non-PM, wrong domain, wrong location, or unsupported title."""
            gate_schema = ""

        prompt = f"""You are evaluating whether this Product/PM-adjacent job is an interview-ready, evidence-backed competitive fit for this candidate.

{CANDIDATE_FIT_PROFILE}

{scoring_guidance}

Do not score based on company prestige, remote location, or senior title alone.
Reward concrete evidence in the job description that maps to the candidate profile.
Penalize missing descriptions, generic AI roles, consumer/marketplace roles without workflow/platform/support fit, and non-product roles.
Treat location as compatible only when it explicitly supports Remote US, United States, Bay Area/California, or remote with no country restriction.
International-only countries/cities such as Canada, Toronto, Greece, Portugal, Norway, Hungary, UK, Europe, or APAC are incompatible even when the role is otherwise strong.

Evaluate this job:
- Job Title: {job_title}
- Company: {company}
- Location: {location}
- Job Description: {description or "No description available"}

Return ONLY a JSON object, no markdown, no explanation:
{{
  "score": <integer 1-10>,
  "fit_tier": "Bullseye|Competitive|Watchlist|Low Fit",
  "reason": "<one sentence max 20 words>",
  "summary": "<two sentences about the role>",
  "competitive_angle": "<one sentence explaining Matthew's best angle>",
  "evidence": ["<specific job evidence>", "<specific candidate-match evidence>"],
  "concerns": ["<specific gap or risk>"],
  "extraction": {{
    "role_type": "PM|TPM|Product Ops|Program|FDE|Marketing|Sales|Engineering|Finance|Other|Unknown",
    "seniority": "Intern|Associate|PM|Senior|Staff|Principal|Director|VP|Unknown",
    "domain_lanes": ["<zero or more of: ai_support_agents, customer_service_resolution, enterprise_workflow, internal_ai_tools, agentic_automation, human_ai_handoff, evals_guardrails, ai_platform_api, enterprise_agent_infrastructure, regulated_ai_ops, consumer_marketplace, ads_growth, marketing_sales, hardware, devtools, finance, other>"],
    "location_fit": "remote_us|bay_area|compatible|incompatible|unclear",
    "evidence_strength": "strong|medium|weak|none",
    "red_flags": ["<internship, non-PM, incompatible location, vague description, or other flags>"],
    "confidence": <number from 0 to 1>{gate_schema}
  }}
}}"""

        for attempt in range(3):
            try:
                generation_options = {}
                if ANALYZER_VARIANT == "structured_gates_v3":
                    generation_options["config"] = types.GenerateContentConfig(
                        response_mime_type="application/json",
                        temperature=0,
                    )
                response = client.models.generate_content(
                    model=GEMINI_MODEL,
                    contents=prompt,
                    **generation_options,
                )
                break
            except Exception as e:
                if "429" in str(e) and attempt < 2:
                    time.sleep(35)
                    continue
                raise

        response_text = response.text.strip()
        result = _parse_json_response(response_text)
        return _normalize_result(result, job)

    except Exception as e:
        print(f"[AI RAW] {response_text[:500]}")
        print(f"[AI ERROR] analyze_job failed for '{job.get('title')}': {e}")
        return _fallback(5, "Analysis unavailable", "", job)
