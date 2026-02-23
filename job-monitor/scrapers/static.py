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
    
    jobs = []
    # Strategy: Find all text nodes containing "product manager" (case-insensitive)
    # Then look for nearby anchor tags or list items
    
    # Find all text nodes that contain "product manager"
    text_nodes = soup.find_all(string=re.compile(r'product\s+manager', re.IGNORECASE))
    
    for text_node in text_nodes:
        # Navigate up the tree to find containing element
        parent = text_node.parent
        
        # Try to find an anchor tag in the parent or nearby
        anchor = None
        title = None
        job_url = None
        location = ""
        
        # Strategy 1: Check if parent is an anchor
        if parent and parent.name == 'a':
            anchor = parent
        # Strategy 2: Find anchor in parent
        elif parent:
            anchor = parent.find('a', recursive=False)
            if not anchor:
                # Look for anchor in siblings
                for sibling in parent.find_next_siblings():
                    if sibling.name == 'a':
                        anchor = sibling
                        break
                # Or check parent's parent
                if not anchor and parent.parent:
                    anchor = parent.parent.find('a', recursive=False)
        
        if anchor and anchor.get('href'):
            # Extract title from anchor text or nearby text
            title = anchor.get_text(strip=True)
            if not title or len(title) < 5:
                # Try to get title from parent or nearby
                if parent:
                    title = parent.get_text(strip=True)
                if not title or len(title) < 5:
                    title = text_node.strip()
            
            # Clean up title - remove extra whitespace
            title = re.sub(r'\s+', ' ', title).strip()
            
            # Only process if title actually contains "product manager"
            if "product manager" not in title.lower():
                continue
            
            # Get URL
            href = anchor.get('href')
            job_url = urljoin(url, href)
            
            # Try to extract location from surrounding context
            location_text = ""
            if parent:
                # Get text from parent element
                location_text = parent.get_text()
            if not location_text and parent and parent.parent:
                location_text = parent.parent.get_text()
            
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
    
    # Alternative strategy: Look for common job listing patterns
    # Some sites structure jobs in lists or divs
    if not jobs:
        # Look for links containing "product manager" in href or text
        all_links = soup.find_all('a', href=True)
        for link in all_links:
            link_text = link.get_text(strip=True)
            href = link.get('href', '').lower()
            
            if "product manager" in link_text.lower() or "product manager" in href:
                title = link_text
                if not title or len(title) < 5:
                    continue
                
                job_url = urljoin(url, link.get('href'))
                location = _extract_location_from_text(link.get_text())
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
