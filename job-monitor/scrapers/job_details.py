"""Job detail enrichment utilities."""

import re
from typing import Dict

import requests
from bs4 import BeautifulSoup

MAX_DESCRIPTION_CHARS = 12_000
MIN_USEFUL_DESCRIPTION_CHARS = 300

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
}


def normalize_description(text: str, max_chars: int = MAX_DESCRIPTION_CHARS) -> str:
    """Normalize readable job text and cap prompt size."""
    cleaned = re.sub(r"\s+", " ", text or "").strip()
    return cleaned[:max_chars]


def extract_readable_text(html: str, max_chars: int = MAX_DESCRIPTION_CHARS) -> str:
    """Extract readable text from a job-detail HTML page."""
    soup = BeautifulSoup(html or "", "html.parser")
    for tag in soup(["script", "style", "noscript", "svg", "header", "footer", "nav"]):
        tag.decompose()

    selectors = [
        '[data-qa="job-description"]',
        '[data-testid*="job"]',
        '[class*="job-description"]',
        '[class*="description"]',
        '[id*="job-description"]',
        "main",
        "article",
        "body",
    ]
    candidates = []
    for selector in selectors:
        for node in soup.select(selector):
            text = node.get_text(" ", strip=True)
            if text:
                candidates.append(text)

    if not candidates:
        candidates.append(soup.get_text(" ", strip=True))

    return normalize_description(max(candidates, key=len, default=""), max_chars)


def extract_greenhouse_description(content_html: str) -> str:
    """Normalize Greenhouse API content HTML."""
    return extract_readable_text(content_html)


def fetch_job_description(url: str, timeout: int = 15) -> str:
    """Fetch and extract readable job-description text from a public job URL."""
    if not url:
        return ""

    try:
        response = requests.get(url, headers=_HEADERS, timeout=timeout)
        response.raise_for_status()
        text = extract_readable_text(response.text)
        if len(text) >= MIN_USEFUL_DESCRIPTION_CHARS:
            return text
    except Exception as request_error:
        print(f"[WARN] requests detail fetch failed for {url}: {request_error}")

    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(url, timeout=60_000, wait_until="domcontentloaded")
            page.wait_for_timeout(2_000)
            html = page.content()
            browser.close()
        return extract_readable_text(html)
    except Exception as playwright_error:
        print(f"[WARN] Playwright detail fetch failed for {url}: {playwright_error}")
        return ""


def enrich_job_details(job: Dict[str, str]) -> Dict[str, str]:
    """Ensure a job dict has normalized description text for scoring."""
    existing_description = normalize_description(job.get("description", ""))
    if existing_description:
        job["description"] = existing_description
        job.setdefault("description_source", "scraper")
        return job

    description = fetch_job_description(job.get("url", ""))
    job["description"] = description
    job["description_source"] = "url_fetch" if description else "unavailable"
    return job
