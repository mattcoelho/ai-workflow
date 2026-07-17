"""Gemini AI analyzer for competitive job fit."""

import json
import os
import re
import time
from typing import Any, Dict, List, Tuple

from google import genai

from ai.candidate_profile import CANDIDATE_FIT_PROFILE

MAX_DESCRIPTION_CHARS = 12_000

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

ROLE_SIGNAL_RE = re.compile(
    r"\b(product manager|product lead|group product|head of product|director of product|"
    r"staff product|principal product|senior product|product operations|technical product manager|"
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
INCOMPATIBLE_LOCATION_RE = re.compile(
    r"\b(india|united kingdom|uk|singapore|colombia|canada|australia|germany|france|"
    r"netherlands|poland|spain|ireland|london|dublin|emea|europe|apac|latam)\b",
    re.IGNORECASE,
)
ACCEPTABLE_LOCATION_RE = re.compile(
    r"\b(remote( - us| us|, us| united states| - united states)?|united states|usa|us|"
    r"san francisco|sf bay|bay area|california)\b",
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
    if INCOMPATIBLE_LOCATION_RE.search(location):
        return False
    if ACCEPTABLE_LOCATION_RE.search(location):
        return True
    return True


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

    normalized = {
        "role_type": _normalize_choice(extraction.get("role_type"), ROLE_TYPES, "Unknown"),
        "seniority": _normalize_choice(extraction.get("seniority"), SENIORITIES, "Unknown"),
        "domain_lanes": domain_lanes[:6],
        "location_fit": _normalize_choice(extraction.get("location_fit"), LOCATION_FITS, "unclear"),
        "evidence_strength": _normalize_choice(extraction.get("evidence_strength"), EVIDENCE_STRENGTHS, "weak"),
        "red_flags": _listify(extraction.get("red_flags"), max_items=6),
        "confidence": _normalize_confidence(extraction.get("confidence")),
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

    if role_type not in COMPETITIVE_ROLE_TYPES and role_type != "Unknown":
        score = min(score, 4)
        concerns.append(f"Structured extraction classified role as {role_type}, not PM-adjacent.")

    if seniority == "Intern" or "intern" in red_flags or "internship" in red_flags:
        score = min(score, 2)
        concerns.append("Structured extraction flagged internship-level seniority.")
    elif seniority == "Associate":
        score = min(score, 5)
        concerns.append("Structured extraction flagged below-target seniority.")

    if location_fit == "incompatible":
        score = min(score, 5)
        concerns.append("Structured extraction flagged incompatible location.")

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

        prompt = f"""You are evaluating whether this Product/PM-adjacent job is an interview-ready, evidence-backed competitive fit for this candidate.

{CANDIDATE_FIT_PROFILE}

Scoring rules:
- 9-10: Direct evidence across seniority, location, domain, ownership, and candidate proof points. These are bullseye roles.
- 7-8: Competitive with one meaningful gap or bridge.
- 5-6: Interesting but not strongly competitive; watchlist only.
- 1-4: Poor fit, non-PM, wrong domain, wrong location, or unsupported title.

Do not score based on company prestige, remote location, or senior title alone.
Reward concrete evidence in the job description that maps to the candidate profile.
Penalize missing descriptions, generic AI roles, consumer/marketplace roles without workflow/platform/support fit, and non-product roles.

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
    "confidence": <number from 0 to 1>
  }}
}}"""

        for attempt in range(3):
            try:
                response = client.models.generate_content(
                    model="gemini-2.5-flash",
                    contents=prompt
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
