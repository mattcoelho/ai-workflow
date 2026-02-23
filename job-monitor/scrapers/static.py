"""Static HTML job board scraper."""

import requests
import re
from bs4 import BeautifulSoup
from typing import List, Dict
from urllib.parse import urljoin, urlparse


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


def scrape_static(url: str, company_name: str) -> List[Dict[str, str]]:
    """
    Scrape Product Manager jobs from a static HTML career page.
    
    Args:
        url: URL of the career page
        company_name: Company name for the returned job dicts
        
    Returns:
        List of job dicts with keys: id, title, location, url, company
        
    Raises:
        Exception: If the page cannot be fetched or parsed
    """
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        raise Exception(f"Failed to fetch page: {e}")
    
    try:
        soup = BeautifulSoup(response.content, 'html.parser')
    except Exception as e:
        raise Exception(f"Failed to parse HTML: {e}")
    
    # Count raw "product manager" matches for debug logging
    text_nodes = soup.find_all(string=re.compile(r'product\s+manager', re.IGNORECASE))
    raw_pm_matches = len(text_nodes)
    
    # Debug logging
    print(f"[DEBUG] {company_name}: HTTP {response.status_code}, page length {len(response.text)} chars, raw PM matches found: {raw_pm_matches}")
    
    jobs = []
    # Strategy: Find all text nodes containing "product manager" (case-insensitive)
    # Then walk up the DOM tree to find the nearest ancestor <a> tag
    
    for text_node in text_nodes:
        # Walk up the DOM tree to find the nearest ancestor <a> tag with href
        anchor = text_node.find_parent('a', href=True)
        
        if anchor:
            # Extract title from anchor (includes all child text)
            title = anchor.get_text(strip=True)
            
            # Clean up title - remove extra whitespace
            title = re.sub(r'\s+', ' ', title).strip()
            
            # Only process if title actually contains "product manager"
            if "product manager" not in title.lower() or len(title) < 5:
                continue
            
            # Get URL
            href = anchor.get('href')
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
