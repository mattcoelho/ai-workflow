"""Bounded URL repair loop for job postings."""

import json
import os
import re
from typing import Any, Callable, Dict, List, Tuple
from urllib.parse import parse_qs, urldefrag, urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from google import genai

from agent.verification import verify_job
from scrapers.job_details import MIN_USEFUL_DESCRIPTION_CHARS, fetch_job_description

DEFAULT_MAX_REPAIR_ATTEMPTS = 3
MAX_CANDIDATE_LINKS = 20

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
}

JOB_URL_HINT_RE = re.compile(
    r"(/jobs?/|/careers/job|/positions?/|/openings?/|job_id=|gh_jid=|jid=|pid=|lever\.co|greenhouse)",
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


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _max_attempts(value: int = None) -> int:
    if value is not None:
        return max(0, int(value))
    try:
        return max(0, int(os.getenv("JOB_URL_REPAIR_MAX_ATTEMPTS", DEFAULT_MAX_REPAIR_ATTEMPTS)))
    except (TypeError, ValueError):
        return DEFAULT_MAX_REPAIR_ATTEMPTS


def _title_terms(title: str) -> List[str]:
    terms = re.findall(r"[a-z0-9]{4,}", (title or "").lower())
    return [term for term in terms if term not in TITLE_STOPWORDS]


def _normalize_url(url: str) -> str:
    return urldefrag(url or "")[0].rstrip("/")


def _candidate_record(url: str, source: str, reason: str, text: str = "", score: int = 0) -> Dict[str, Any]:
    return {
        "url": _normalize_url(url),
        "source": source,
        "reason": reason,
        "text": re.sub(r"\s+", " ", text or "").strip()[:180],
        "score": score,
    }


def _known_url_repairs(job: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Generate deterministic URL transforms for known ATS quirks."""
    url = str(job.get("url", "") or "")
    parsed = urlparse(url)
    query = parse_qs(parsed.query)
    candidates: List[Dict[str, Any]] = []

    pid = (query.get("pid") or [""])[0]
    if parsed.netloc.lower() == "jobs.twilio.com" and parsed.path.rstrip("/") == "/careers" and pid:
        candidates.append(
            _candidate_record(
                f"{parsed.scheme or 'https'}://{parsed.netloc}/careers/job/{pid}",
                "known_transform",
                "Converted Twilio careers?pid URL to careers/job URL.",
                score=12,
            )
        )

    return candidates


def fetch_url_html(url: str, timeout: int = 15) -> str:
    """Fetch HTML from a URL for candidate-link extraction."""
    if not url:
        return ""

    try:
        response = requests.get(url, headers=_HEADERS, timeout=timeout)
        response.raise_for_status()
        return response.text
    except Exception as request_error:
        print(f"[WARN] requests repair fetch failed for {url}: {request_error}")

    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(url, timeout=60_000, wait_until="domcontentloaded")
            page.wait_for_timeout(2_000)
            html = page.content()
            browser.close()
        return html
    except Exception as playwright_error:
        print(f"[WARN] Playwright repair fetch failed for {url}: {playwright_error}")
        return ""


def extract_candidate_links(html: str, base_url: str, job: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Extract likely job-detail URLs from a generic careers/search page."""
    soup = BeautifulSoup(html or "", "html.parser")
    title = str(job.get("title", "") or "")
    exact_title = re.sub(r"\s+", " ", title).strip().lower()
    terms = _title_terms(title)
    job_id = str(job.get("id", "") or "").strip().lower()

    candidates: List[Dict[str, Any]] = []
    seen = set()

    for anchor in soup.find_all("a", href=True):
        href = str(anchor.get("href") or "").strip()
        if not href or href.startswith(("mailto:", "tel:", "javascript:")):
            continue

        absolute_url = _normalize_url(urljoin(base_url, href))
        if not absolute_url or absolute_url in seen:
            continue

        text = " ".join(
            value
            for value in (
                anchor.get_text(" ", strip=True),
                str(anchor.get("aria-label", "") or ""),
                str(anchor.get("title", "") or ""),
            )
            if value
        )
        haystack = f"{absolute_url} {text}".lower()
        score = 0
        reasons = []

        if JOB_URL_HINT_RE.search(absolute_url):
            score += 3
            reasons.append("URL looks job-specific")
        if job_id and job_id in haystack:
            score += 6
            reasons.append("matches job id")
        if exact_title and exact_title in haystack:
            score += 6
            reasons.append("mentions exact title")
        term_matches = sum(1 for term in terms if term in haystack)
        if term_matches:
            score += min(4, term_matches)
            reasons.append(f"matches {term_matches} title term(s)")

        if score >= 3:
            seen.add(absolute_url)
            candidates.append(
                _candidate_record(
                    absolute_url,
                    "page_link",
                    "; ".join(reasons) or "candidate page link",
                    text=text,
                    score=score,
                )
            )

    return sorted(candidates, key=lambda candidate: candidate["score"], reverse=True)[:MAX_CANDIDATE_LINKS]


def _dedupe_candidates(candidates: List[Dict[str, Any]], original_url: str) -> List[Dict[str, Any]]:
    seen = {_normalize_url(original_url)}
    unique = []
    for candidate in candidates:
        url = _normalize_url(str(candidate.get("url", "") or ""))
        if not url or url in seen:
            continue
        seen.add(url)
        candidate["url"] = url
        unique.append(candidate)
    return unique


def _rank_candidates_with_gemini(job: Dict[str, Any], candidates: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """Optionally use Gemini to rank deterministic candidate URLs."""
    meta = {"enabled": True, "used": False, "reason": ""}
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        meta["reason"] = "missing GEMINI_API_KEY"
        return candidates, meta
    if len(candidates) <= 1:
        meta["reason"] = "one or fewer candidates"
        return candidates, meta

    try:
        client = genai.Client(api_key=api_key)
        compact_candidates = [
            {
                "url": candidate.get("url", ""),
                "text": candidate.get("text", ""),
                "source": candidate.get("source", ""),
                "reason": candidate.get("reason", ""),
            }
            for candidate in candidates[:12]
        ]
        prompt = f"""Rank these deterministic candidate URLs for the exact job posting.

Job:
- Title: {job.get("title", "")}
- Company: {job.get("company", "")}
- Location: {job.get("location", "")}
- Original URL: {job.get("url", "")}

Candidates:
{json.dumps(compact_candidates, indent=2)}

Return ONLY JSON:
{{"ranked_urls": ["<best url first>"], "reason": "<brief reason>"}}"""
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
        )
        result = json.loads((response.text or "").strip().strip("`"))
        ranked_urls = [
            _normalize_url(url)
            for url in result.get("ranked_urls", [])
            if str(url).strip()
        ]
        rank = {url: index for index, url in enumerate(ranked_urls)}
        ordered = sorted(
            candidates,
            key=lambda candidate: rank.get(candidate.get("url", ""), len(rank) + candidates.index(candidate)),
        )
        meta = {
            "enabled": True,
            "used": True,
            "reason": str(result.get("reason", ""))[:180],
        }
        return ordered, meta
    except Exception as exc:
        meta["reason"] = f"Gemini ranking failed: {exc}"
        return candidates, meta


def _should_try_repair(verification: Dict[str, Any]) -> bool:
    if not verification:
        return False
    if verification.get("quality") == "passed" and verification.get("score_cap") is None:
        return False
    issues = " ".join(verification.get("issues") or []).lower()
    return any(
        phrase in issues
        for phrase in (
            "generic careers/search page",
            "missing or too short",
            "does not clearly mention",
            "exact job title",
        )
    )


def _accepted_repair(candidate_verification: Dict[str, Any]) -> bool:
    return (
        candidate_verification.get("quality") == "passed"
        and candidate_verification.get("score_cap") is None
        and int(candidate_verification.get("description_length", 0) or 0) >= MIN_USEFUL_DESCRIPTION_CHARS
    )


def repair_job_url(
    job: Dict[str, Any],
    max_attempts: int = None,
    use_gemini: bool = None,
    fetch_description_func: Callable[[str], str] = fetch_job_description,
    fetch_html_func: Callable[[str], str] = fetch_url_html,
) -> Dict[str, Any]:
    """Try to repair a suspect job URL with a bounded observe-act-verify loop."""
    original_url = str(job.get("url", "") or "")
    max_attempts = _max_attempts(max_attempts)
    use_gemini = _env_bool("JOB_URL_REPAIR_USE_GEMINI", False) if use_gemini is None else bool(use_gemini)
    original_verification = job.get("verification") or verify_job(job)

    loop = {
        "status": "not_needed",
        "original_url": original_url,
        "final_url": original_url,
        "max_attempts": max_attempts,
        "attempts": [],
        "gemini": {"enabled": use_gemini, "used": False, "reason": ""},
    }

    if max_attempts <= 0:
        loop["status"] = "disabled"
        job["url_repair"] = loop
        job["verification"] = original_verification
        return job

    if not original_url:
        loop["status"] = "skipped_no_url"
        job["url_repair"] = loop
        job["verification"] = original_verification
        return job

    if not _should_try_repair(original_verification):
        job["url_repair"] = loop
        job["verification"] = original_verification
        return job

    candidates = _known_url_repairs(job)
    if not candidates:
        html = fetch_html_func(original_url)
        candidates += extract_candidate_links(html, original_url, job)
    candidates = _dedupe_candidates(candidates, original_url)

    if use_gemini:
        candidates, gemini_meta = _rank_candidates_with_gemini(job, candidates)
        loop["gemini"] = gemini_meta

    if not candidates:
        loop["status"] = "unrepaired_no_candidates"
        job["url_repair"] = loop
        job["verification"] = original_verification
        return job

    loop["status"] = "attempted"
    for candidate in candidates:
        if len(loop["attempts"]) >= max_attempts:
            loop["status"] = "max_attempts_reached"
            break

        candidate_url = str(candidate.get("url", "") or "")
        description = fetch_description_func(candidate_url)
        candidate_job = dict(job)
        candidate_job["url"] = candidate_url
        candidate_job["description"] = description
        candidate_verification = verify_job(candidate_job)
        accepted = _accepted_repair(candidate_verification)
        attempt = {
            "attempt": len(loop["attempts"]) + 1,
            "url": candidate_url,
            "source": candidate.get("source", ""),
            "reason": candidate.get("reason", ""),
            "description_length": candidate_verification.get("description_length", 0),
            "quality": candidate_verification.get("quality", ""),
            "issues": candidate_verification.get("issues", []),
            "accepted": accepted,
        }
        loop["attempts"].append(attempt)

        if accepted:
            job["url"] = candidate_url
            job["description"] = description
            job["description_source"] = "url_repair"
            job["verification"] = candidate_verification
            loop["status"] = "repaired"
            loop["final_url"] = candidate_url
            break

    if loop["status"] == "attempted":
        loop["status"] = "unrepaired"

    if loop["status"] != "repaired":
        job["verification"] = original_verification
    loop["final_url"] = str(job.get("url", "") or original_url)
    job["url_repair"] = loop
    return job
