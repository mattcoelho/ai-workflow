"""Playwright-based scraper for JS-rendered job boards."""

import re
from bs4 import BeautifulSoup
from typing import List, Dict
from urllib.parse import urljoin, urlparse
from playwright.sync_api import sync_playwright


def _slugify(text: str) -> str:
    """Convert text to a URL-friendly slug."""
    # Remove special characters, convert to lowercase, replace spaces with hyphens
    text = re.sub(r'[^\w\s-]', '', text.lower())
    text = re.sub(r'[-\s]+', '-', text)
    return text.strip('-')


def _generate_id(url: str, title: str) -> str:
    """Generate a unique ID from URL and title."""
    # Extract a meaningful part of the URL (path)
    parsed = urlparse(url)
    path_part = parsed.path.strip('/').replace('/', '-') or 'job'
    title_slug = _slugify(title)[:50]  # Limit length
    return f"{path_part}-{title_slug}"


def _is_valid_job_url(url: str) -> bool:
    """Check if URL is a valid job listing (excludes guide, blog, roadmapping, resources, about, pricing)."""
    excluded_segments = ['/guide', '/blog', '/roadmapping', '/resources', '/about', '/pricing']
    url_lower = url.lower()
    return not any(segment in url_lower for segment in excluded_segments)


def _extract_location_from_text(text: str) -> str:
    """Try to extract location from surrounding text."""
    # Common location patterns
    location_patterns = [
        r'(Remote|Remote\s*[–-]\s*\w+|Remote\s*\([^)]+\))',
        r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*,\s*[A-Z]{2})',  # City, State
        r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*,\s*[A-Z][a-z]+)',  # City, Country
    ]
    
    for pattern in location_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1).strip()
    
    return ""


def scrape_playwright(url: str, company_name: str) -> List[Dict[str, str]]:
    """
    Scrape Product Manager jobs from a JS-rendered career page using Playwright.
    
    Args:
        url: URL of the career page
        company_name: Company name for the returned job dicts
        
    Returns:
        List of job dicts with keys: id, title, location, url, company
        
    Raises:
        Exception: If the page cannot be fetched or parsed
    """
    with sync_playwright() as p:
        # Launch headless Chromium browser
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        
        try:
            # Navigate to URL with 60s timeout and wait for domcontentloaded, then wait 3s
            page.goto(url, timeout=60000, wait_until="domcontentloaded")
            page.wait_for_timeout(3000)
            
            # Get page content
            html_content = page.content()
            
        except Exception as e:
            browser.close()
            raise Exception(f"Failed to fetch page: {e}")
        finally:
            browser.close()
        
        try:
            # Parse HTML with BeautifulSoup
            soup = BeautifulSoup(html_content, 'html.parser')
        except Exception as e:
            raise Exception(f"Failed to parse HTML: {e}")
        
        jobs = []
        JOB_URL_KEYWORDS = ["/jobs/", "/job/", "/careers/", "/position", "/opening", "/role", "/apply"]
        all_anchors = soup.find_all('a', href=True)
        seen_hrefs = set()
        candidate_anchors = []
        for anchor in all_anchors:
            href = anchor.get('href', '')
            href_str = str(href).strip()
            if (
                href_str
                and not href_str.startswith('#')
                and href_str not in seen_hrefs
                and any(kw in href_str for kw in JOB_URL_KEYWORDS)
            ):
                seen_hrefs.add(href_str)
                candidate_anchors.append(('link', anchor))
        print(f"[DEBUG] {company_name}: page length {len(html_content)} chars, links found: {len(candidate_anchors)}")

        if len(candidate_anchors) == 0 and len(html_content) > 50000:
            sample_links = soup.find_all('a', href=True)[:5]
            for link in sample_links:
                print(f"[SAMPLE LINK] {company_name}: href={link.get('href','')[:80]} text={link.get_text(strip=True)[:60]}")

        for source, anchor in candidate_anchors:
            if source == 'aria':
                title = (anchor.get('aria-label', '') or '').strip()
                if not title:
                    title = anchor.get_text(strip=True)
            else:
                title = anchor.get_text(strip=True)
            title = re.sub(r'\s+', ' ', title).strip()
            if len(title) < 5:
                continue

            href = anchor.get('href')
            if not href or not str(href).strip() or str(href).strip().startswith('#'):
                continue
            job_url = urljoin(url, href)

            # Filter out non-job URLs (guide, blog, roadmapping, resources, about, pricing)
            if not _is_valid_job_url(job_url):
                continue

            # Try to extract location from anchor's parent context
            location = ""
            parent = anchor.parent
            if parent:
                location_text = parent.get_text()
                location = _extract_location_from_text(location_text)

            # Generate ID
            job_id = _generate_id(job_url, title)

            # Avoid duplicates
            if not any(job['id'] == job_id for job in jobs):
                jobs.append({
                    "id": job_id,
                    "title": title,
                    "location": location,
                    "url": job_url,
                    "company": company_name
                })

        return jobs
