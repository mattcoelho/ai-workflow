"""Deterministic self-checks for scraped job results."""

import re
from typing import Any, Dict, List, Tuple
from urllib.parse import parse_qs, urlparse, urlunparse

from ai.analyzer import fit_tier_for_score

MIN_USEFUL_DESCRIPTION_CHARS = 300

GENERIC_CAREERS_PATH_RE = re.compile(
    r"(^|/)(careers|jobs|positions|openings|all-jobs)/?$",
    re.IGNORECASE,
)
CLOSED_ROLE_RE = re.compile(
    r"\b(no longer accepting applications|job is closed|position has been filled|"
    r"this posting is no longer available|not accepting applications|expired)\b",
    re.IGNORECASE,
)
TITLE_STOPWORDS = {
    "and",
    "for",
    "the",
    "with",
    "senior",
    "staff",
    "principal",
    "lead",
    "group",
    "product",
    "manager",
    "management",
    "remote",
}


def _canonical_url(url: str) -> str:
    parsed = urlparse(url or "")
    if not parsed.netloc:
        return (url or "").strip().lower()

    query = parse_qs(parsed.query)
    keep = {}
    for key in ("gh_jid", "jid", "job_id", "id", "pid"):
        if key in query:
            keep[key] = query[key]

    normalized_query = ""
    if keep:
        normalized_query = "&".join(
            f"{key}={value[0]}" for key, value in sorted(keep.items()) if value
        )

    return urlunparse(
        (
            parsed.scheme.lower(),
            parsed.netloc.lower(),
            parsed.path.rstrip("/"),
            "",
            normalized_query,
            "",
        )
    )


def _looks_generic_url(url: str) -> bool:
    parsed = urlparse(url or "")
    if not parsed.netloc:
        return True
    if parsed.query:
        query = parse_qs(parsed.query)
        if any(key in query for key in ("gh_jid", "jid", "job_id", "id")):
            return False
    return bool(GENERIC_CAREERS_PATH_RE.search(parsed.path or ""))


def _normalized_phrase(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip().lower()


def _mentions_exact_title(title: str, text: str) -> bool:
    normalized_title = _normalized_phrase(title)
    if not normalized_title:
        return True
    return normalized_title in _normalized_phrase(text)


def _title_terms(title: str) -> List[str]:
    terms = re.findall(r"[a-z0-9]{4,}", (title or "").lower())
    return [term for term in terms if term not in TITLE_STOPWORDS]


def _text_mentions_title(title: str, text: str) -> bool:
    terms = _title_terms(title)
    if not terms:
        return True
    lower_text = (text or "").lower()
    return any(term in lower_text for term in terms)


def verify_job(job: Dict[str, Any]) -> Dict[str, Any]:
    """Return URL/detail quality checks that can be audited and used for caps."""
    title = str(job.get("title", "") or "")
    company = str(job.get("company", "") or "")
    url = str(job.get("url", "") or "")
    description = str(job.get("description", "") or "")
    description_len = len(description.strip())

    issues: List[str] = []
    checks: List[str] = []
    score_cap = None

    looks_generic = _looks_generic_url(url)

    if not url:
        issues.append("Missing job URL.")
        score_cap = 4
    elif looks_generic and description_len < MIN_USEFUL_DESCRIPTION_CHARS:
        issues.append("URL looks like a generic careers/search page and detail text is weak.")
        score_cap = 5
    elif looks_generic and not _mentions_exact_title(title, description):
        issues.append("URL looks like a generic careers/search page and detail text does not contain the exact job title.")
        score_cap = 5
    elif looks_generic:
        checks.append("Generic-looking URL contains enough job-specific text to score.")
    else:
        checks.append("URL looks job-specific.")

    if description_len < MIN_USEFUL_DESCRIPTION_CHARS:
        issues.append("Description is missing or too short for evidence-backed scoring.")
    else:
        checks.append("Description is long enough for scoring.")

    if CLOSED_ROLE_RE.search(description):
        issues.append("Job detail page appears closed or unavailable.")
        score_cap = min(score_cap or 3, 3)

    if description and title and not _text_mentions_title(title, description):
        issues.append("Job detail text does not clearly mention distinctive title terms.")

    if description and company and company.lower() not in description.lower():
        checks.append("Company name not present in detail text; acceptable for many ATS pages.")

    quality = "passed"
    if any("Missing job URL" in issue or "closed" in issue.lower() for issue in issues):
        quality = "failed"
    elif issues:
        quality = "needs_review"

    return {
        "quality": quality,
        "issues": issues[:6],
        "checks": checks[:6],
        "score_cap": score_cap,
        "description_length": description_len,
        "canonical_url": _canonical_url(url),
    }


def apply_verification_caps(job: Dict[str, Any]) -> Dict[str, Any]:
    """Cap scores when self-checks show the result is not reliable enough."""
    verification = job.get("verification") or verify_job(job)
    job["verification"] = verification
    cap = verification.get("score_cap")
    if cap is None:
        return job

    try:
        cap_value = int(cap)
    except (TypeError, ValueError):
        return job

    score = int(job.get("score", 0) or 0)
    if score > cap_value:
        job["score"] = cap_value
        job["fit_tier"] = fit_tier_for_score(cap_value)
        concerns = job.get("concerns")
        if not isinstance(concerns, list):
            concerns = [concerns] if concerns else []
        concerns.append(
            f"Self-check capped score at {cap_value}: {'; '.join(verification.get('issues', []))}"
        )
        job["concerns"] = [str(item) for item in concerns if str(item).strip()][:6]
    return job


def collapse_duplicate_jobs(jobs: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], List[str]]:
    """Remove obvious duplicates from a scrape result and return audit notes."""
    seen = {}
    unique_jobs: List[Dict[str, Any]] = []
    duplicate_notes: List[str] = []

    for job in jobs:
        company = str(job.get("company", "") or "").lower()
        job_id = str(job.get("id", "") or "").strip().lower()
        canonical_url = _canonical_url(str(job.get("url", "") or ""))
        title = re.sub(r"\s+", " ", str(job.get("title", "") or "").strip().lower())
        location = re.sub(r"\s+", " ", str(job.get("location", "") or "").strip().lower())

        key = (company, job_id or canonical_url or f"{title}|{location}")
        if key in seen:
            duplicate_notes.append(
                f"{job.get('company', '')}: duplicate '{job.get('title', '')}' matched '{seen[key].get('title', '')}'."
            )
            continue

        seen[key] = job
        unique_jobs.append(job)

    return unique_jobs, duplicate_notes
