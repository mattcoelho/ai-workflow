"""Ashby job board scraper."""

import requests
import re
from bs4 import BeautifulSoup
from typing import List, Dict
from urllib.parse import urljoin, urlparse


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


def scrape_ashby(board_token: str, company_name: str) -> List[Dict[str, str]]:
    """
    Scrape Product Manager jobs from Ashby job board.
    
    Args:
        board_token: Ashby board token
        company_name: Company name for the returned job dicts
        
    Returns:
        List of job dicts with keys: id, title, location, url, company
        
    Raises:
        Exception: If the page cannot be fetched or parsed
    """
    url = f"https://jobs.ashbyhq.com/{board_token}"
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
    # Find all anchor tags that link to job listings (/jobs/{job-id})
    all_links = soup.find_all('a', href=True)
    
    for link in all_links:
        href = link.get('href', '')
        link_text = link.get_text(strip=True)
        
        # Check if this is a job listing link (href contains /jobs/)
        if '/jobs/' in href:
            # Extract job ID from URL if possible
            job_id_match = re.search(r'/jobs/([^/?]+)', href)
            job_id = job_id_match.group(1) if job_id_match else href
            
            # Build full URL
            job_url = urljoin(url, href)
            
            # Extract title from link text
            title = link_text
            
            # Try to extract location from surrounding context
            location = ""
            parent = link.parent
            if parent:
                location_text = parent.get_text()
                location = _extract_location_from_text(location_text)
            
            jobs.append({
                "id": job_id,
                "title": title,
                "location": location,
                "url": job_url,
                "company": company_name
            })
    
    return jobs
